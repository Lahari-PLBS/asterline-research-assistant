# test_retrieval.py - checks that search finds the right chunks
from retrieval import hybrid_search

questions = [
    'How long is cold storage kept after searchable retention ends?',
    'What happened in INC-2025-12?',
    'What is the on-call stipend?',
]
for q in questions:
    print()
    print(q)
    for c in hybrid_search(q):
        print('  ', c['chunk_id'], '|', c['published'], '|', c['title'])