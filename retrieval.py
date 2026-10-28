# retrieval.py - loads the corpus, builds the vector index, and does hybrid search.
import json
import re
from functools import lru_cache

import chromadb
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

CORPUS_PATH = 'data/corpus.jsonl'
CHROMA_PATH = 'storage/chroma'
COLLECTION_NAME = 'asterline_chunks'
EMBED_MODEL = 'BAAI/bge-small-en-v1.5'
# bge models work better when the QUESTION (not the documents) starts with this sentence
QUERY_PREFIX = 'Represent this sentence for searching relevant passages: '


def get_text(raw):
    '''Find the paragraph text, whatever the field is called.'''
    for key in ('text', 'content', 'body', 'chunk_text'):
        if key in raw:
            return raw[key]
    # fallback: the longest string value in the record is the paragraph
    return max((v for v in raw.values() if isinstance(v, str)), key=len)


def normalize(raw):
    '''Return a clean, flat dictionary. Also works if metadata is stored inside a 'metadata' field.'''
    flat = dict(raw)
    if isinstance(raw.get('metadata'), dict):
        flat.update(raw['metadata'])
    return {
        'chunk_id': str(flat.get('chunk_id')),
        'doc_id': str(flat.get('doc_id')),
        'title': str(flat.get('title')),
        'category': str(flat.get('category')),
        'published': str(flat.get('published')),
        'version': str(flat.get('version')),
        'text': get_text(raw),
    }


def load_chunks():
    chunks = []
    with open(CORPUS_PATH, encoding='utf-8') as f:
        for line in f:
            if line.strip():
                chunks.append(normalize(json.loads(line)))
    return chunks


CHUNKS = load_chunks()
CHUNKS_BY_ID = {c['chunk_id']: c for c in CHUNKS}


def tokenize(text):
    '''Lower-case words and numbers. INC-2025-12 becomes inc, 2025, 12 (same for questions and chunks).'''
    return re.findall('[a-z0-9]+', text.lower())


# BM25 (keyword search) is built in memory. It is tiny (75 chunks) and takes milliseconds.
BM25 = BM25Okapi([tokenize(c['title'] + ' ' + c['text']) for c in CHUNKS])


@lru_cache(maxsize=1)
def get_embedder():
    return SentenceTransformer(EMBED_MODEL)   # downloaded once (about 130 MB), then cached


def build_index():
    '''(Re)build the vector index from the corpus. Safe to run many times.'''
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    try:
        client.delete_collection(COLLECTION_NAME)   # start fresh so we never create duplicates
    except Exception:
        pass
    collection = client.create_collection(COLLECTION_NAME, metadata={'hnsw:space': 'cosine'})

    texts = [c['title'] + ': ' + c['text'] for c in CHUNKS]
    vectors = get_embedder().encode(texts, normalize_embeddings=True).tolist()
    collection.add(
        ids=[c['chunk_id'] for c in CHUNKS],
        embeddings=vectors,
        documents=texts,
        metadatas=[{'doc_id': c['doc_id'], 'title': c['title'], 'published': c['published']} for c in CHUNKS],
    )
    return collection


@lru_cache(maxsize=1)
def get_collection():
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = client.get_or_create_collection(COLLECTION_NAME, metadata={'hnsw:space': 'cosine'})
    if collection.count() != len(CHUNKS):   # first run (or corpus changed): build the index
        collection = build_index()
    return collection


def hybrid_search(query, k=6, pool=10):
    '''Return the k best chunks for the query, combining meaning search and keyword search.'''
    # 1) Meaning search (embeddings)
    query_vector = get_embedder().encode([QUERY_PREFIX + query], normalize_embeddings=True).tolist()
    result = get_collection().query(query_embeddings=query_vector, n_results=pool)
    dense_ids = result['ids'][0]

    # 2) Keyword search (BM25)
    scores = BM25.get_scores(tokenize(query))
    best_positions = sorted(range(len(CHUNKS)), key=lambda i: scores[i], reverse=True)[:pool]
    keyword_ids = [CHUNKS[i]['chunk_id'] for i in best_positions]

    # 3) Reciprocal Rank Fusion: a chunk ranked high in either list gets a high combined score
    combined = {}
    for ranking in (dense_ids, keyword_ids):
        for position, chunk_id in enumerate(ranking):
            combined[chunk_id] = combined.get(chunk_id, 0) + 1 / (60 + position)

    best = sorted(combined, key=combined.get, reverse=True)[:k]
    return [CHUNKS_BY_ID[chunk_id] for chunk_id in best]