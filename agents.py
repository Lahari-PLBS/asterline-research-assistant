# agents.py - the agents. Each one is a plain function:
# it receives the shared 'state' dictionary and returns the keys it wants to update.
from typing import Literal
from pydantic import BaseModel, Field

from llm import ask
from memory import list_memories, apply_actions
from retrieval import hybrid_search, CHUNKS_BY_ID


# ---------------- helpers that turn data into text for the model ----------------
def format_chunks(chunks):
    '''Chunk text with its ID, title, publication date and version on top.'''
    parts = []
    for c in chunks:
        header = '[' + c['chunk_id'] + '] ' + c['title'] + ' | published ' + c['published'] + ' | version ' + c['version']
        parts.append(header + '\n' + c['text'])
    return '\n\n'.join(parts) if parts else '(none)'


def format_memories(memories):
    if not memories:
        return '(nothing remembered yet)'
    lines = []
    for m in memories:
        lines.append('- id=' + str(m['id']) + ' [' + m['kind'] + '] ' + m['content'])
    return '\n'.join(lines)


def format_history(history):
    '''The last few chat messages, so follow-up questions make sense.'''
    lines = []
    for message in history[-6:]:
        lines.append(message['role'] + ': ' + message['content'])
    return '\n'.join(lines) if lines else '(no earlier messages)'


# =====================================================================
# AGENT 1: ROUTER
# =====================================================================
class Route(BaseModel):
    intent: Literal['company_question', 'memory_request', 'small_talk'] = Field(
        description='What kind of message this is')
    search_query: str = Field(
        description='A complete, standalone search query for company questions')


ROUTER_PROMPT = '''You are the Router for an assistant that answers questions about Asterline Labs, a workflow-monitoring software company.
Look at the newest user message (and the earlier chat) and decide:

intent:
- company_question: the user asks about Asterline products, pricing, policies, incidents, releases and so on. Also use this when a message mixes a question with personal details.
- memory_request: the user ONLY asks you to remember, correct, forget or show what you remember about THEM, with no company question inside.
- small_talk: greetings, thanks, or anything unrelated to Asterline.

search_query: for a company_question, rewrite the newest message as a complete standalone search query. Resolve words like 'it', 'that plan' or 'and for Team?' using the earlier chat. Keep exact names and numbers (for example INC-2025-12). For the other intents, just repeat the message.
Always include the subject of the previous question in search_query (for example the metric and the plan names).'''


def router_agent(state):
    user_prompt = ('Remembered about this user (use only to understand context):\n' + format_memories(state['memories'])
                   + '\n\nEarlier chat:\n' + format_history(state['history'])
                   + '\n\nNewest message:\n' + state['question'])
    route = ask(Route, ROUTER_PROMPT, user_prompt)
    return {'intent': route.intent,
            'search_query': route.search_query,
            'notes': ['Router: intent = ' + route.intent + ' | query = ' + route.search_query]}


# =====================================================================
# AGENT 2: RETRIEVER (no AI model here, just search)
# =====================================================================
def retriever_agent(state):
    chunks = hybrid_search(state['search_query'], k=6)
    ids = [c['chunk_id'] for c in chunks]
    return {'chunks': chunks, 'notes': ['Retriever: found ' + ', '.join(ids)]}


# =====================================================================
# AGENT 3: EVIDENCE ANALYST (handles conflicts and missing information)
# =====================================================================
class Analysis(BaseModel):
    use_chunk_ids: list[str] = Field(
        description='IDs of chunks holding current, relevant evidence. Also include chunks that explain why a fact is unavailable.')
    outdated_chunk_ids: list[str] = Field(
        description='IDs of chunks whose information is superseded or describes an older point in time')
    fact_found: bool = Field(
        description='True only if the chunks directly state the specific fact the user asked for')
    conflict_note: str = Field(
        description='One or two sentences on any disagreement between chunks and which one wins and why. Empty string if none.')


ANALYST_PROMPT = '''You are the Evidence Analyst. You receive a question and retrieved document chunks (each with an ID, title, publication date and version). Decide which chunks to trust.
Rules:
1. Only the chunk text is evidence. Never use outside knowledge.
2. When chunks disagree, compare the topic, the effective date, the scope, and any explicit statement that something supersedes or replaces an older value.
3. A newer, specific document beats an older one. A general overview does NOT override a specific policy.
4. Old release notes describe the past. Use them as current evidence only if the question asks about that time.
5. Do not mix up similar things (ingestion limits are per project, query concurrency limits are per workspace, and one incident is not another).
6. If the chunks do not contain the specific fact asked, set fact_found to false. Still list in use_chunk_ids any chunk that explains the situation (for example, a price that is not published and must be requested from sales).
7. If the documents only say that a fact is unpublished, unannounced or must be requested from someone, the specific fact was NOT found: set fact_found to false.
8. When one chunk says it supersedes or replaces another, or a later dated document covers the same topic more specifically, the newer chunk is current and the other is outdated.'''


def analyst_agent(state):
    user_prompt = ('Question: ' + state['question'] + '\nStandalone query: ' + state['search_query']
                   + '\n\nChunks:\n' + format_chunks(state['chunks']))
    result = ask(Analysis, ANALYST_PROMPT, user_prompt)

    # Safety check in code: keep only IDs that really were retrieved (the model may invent IDs)
    retrieved_ids = [c['chunk_id'] for c in state['chunks']]
    use_ids = [i for i in result.use_chunk_ids if i in retrieved_ids]
    outdated_ids = [i for i in result.outdated_chunk_ids if i in retrieved_ids]
    if result.fact_found and not use_ids:
        use_ids = retrieved_ids[:3]   # fallback so the writer always has evidence

    analysis = {'use_chunk_ids': use_ids, 'outdated_chunk_ids': outdated_ids,
                'fact_found': result.fact_found, 'conflict_note': result.conflict_note}
    note = ('Analyst: use ' + ', '.join(use_ids) + ' | outdated ' + (', '.join(outdated_ids) or 'none')
            + ' | fact found = ' + str(result.fact_found))
    if result.conflict_note:
        note = note + ' | conflict: ' + result.conflict_note
    return {'analysis': analysis, 'notes': [note]}


# =====================================================================
# AGENT 4: WRITER
# =====================================================================
class Draft(BaseModel):
    answer: str = Field(description='The answer, with chunk IDs in square brackets after each fact, like [pricing:1]')
    cited_chunk_ids: list[str] = Field(description='IDs of the chunks actually used')


WRITER_PROMPT = '''You are the Answer Writer for an Asterline documentation assistant.
Rules:
1. Use ONLY the EVIDENCE chunks you are given. Never use outside knowledge and never guess.
2. After every fact, add the chunk ID in square brackets, for example [pricing:1].
3. If OUTDATED chunks are provided, never present their values as current. When useful, add a short note like: An older document says X, but it was superseded by Y [chunk id].
4. If the status is NOT FOUND, say clearly that the documentation does not contain the requested fact. Then add related facts or guidance from the evidence (for example, where to get the information). Never invent a number or date.
5. If only part of a multi-part question is covered, answer that part and say what is missing.
6. 'Remembered about the user' is for tone and context only. It is NOT evidence. If you mention something the user told you, say 'you mentioned' and never treat it as a company fact.
7. Follow the user's remembered style preferences (short answers, bullets, and so on).
8. Be clear and concise.'''


def writer_agent(state):
    analysis = state['analysis']
    evidence = [CHUNKS_BY_ID[i] for i in analysis['use_chunk_ids']]
    outdated = [CHUNKS_BY_ID[i] for i in analysis['outdated_chunk_ids'] if i not in analysis['use_chunk_ids']]
    found = analysis['fact_found']

    user_prompt = ('Question: ' + state['question']
                   + '\n\nStatus: ' + ('FOUND' if found else 'NOT FOUND')
                   + '\nConflict note from the analyst: ' + (analysis['conflict_note'] or 'none')
                   + '\n\nEVIDENCE:\n' + format_chunks(evidence)
                   + '\n\nOUTDATED chunks (do not present as current):\n' + format_chunks(outdated)
                   + '\n\nRemembered about the user (NOT evidence):\n' + format_memories(state['memories']))

    # If the verifier rejected the first draft, show the problems so the writer can fix them
    if state.get('verifier_feedback') and not state.get('verifier_ok', True):
        user_prompt = (user_prompt + '\n\nYour previous draft was:\n' + state['answer']
                       + '\nA reviewer found these problems. Fix them:\n' + state['verifier_feedback'])

    draft = ask(Draft, WRITER_PROMPT, user_prompt)
    cited = [i for i in draft.cited_chunk_ids if i in CHUNKS_BY_ID]   # drop invented IDs
    return {'answer': draft.answer,
            'cited_ids': cited,
            'answer_status': 'answered' if found else 'not_found',
            'notes': ['Writer: wrote answer citing ' + (', '.join(cited) or 'nothing')]}


# =====================================================================
# AGENT 5: VERIFIER
# =====================================================================
class Verdict(BaseModel):
    supported: bool = Field(description='True only if every fact in the answer is supported by the evidence')
    problems: str = Field(description='What is wrong, or an empty string')


VERIFIER_PROMPT = '''You are the Verifier. Check an ANSWER against the EVIDENCE chunks.
Set supported = false if: a number, date, name or claim in the answer is not in the evidence; an outdated value is presented as current; a cited chunk ID does not support the sentence it follows; or something remembered about the user is presented as a company fact.
Set supported = true if everything is backed by the evidence. Describe what is wrong in problems.'''


def verifier_agent(state):
    analysis = state['analysis']
    ids = set(analysis['use_chunk_ids']) | set(analysis['outdated_chunk_ids']) | set(state['cited_ids'])
    evidence = [CHUNKS_BY_ID[i] for i in ids if i in CHUNKS_BY_ID]
    user_prompt = 'ANSWER:\n' + state['answer'] + '\n\nEVIDENCE:\n' + format_chunks(evidence)
    verdict = ask(Verdict, VERIFIER_PROMPT, user_prompt)

    retries = state.get('retries', 0)
    if not verdict.supported:
        retries = retries + 1   # count the failure; the graph allows one retry
    return {'verifier_ok': verdict.supported,
            'verifier_feedback': verdict.problems,
            'retries': retries,
            'notes': ['Verifier: ' + ('answer supported' if verdict.supported else 'PROBLEM - ' + verdict.problems)]}


# =====================================================================
# AGENT 6: MEMORY MANAGER
# =====================================================================
class MemoryAction(BaseModel):
    action: Literal['add', 'update', 'delete']
    memory_id: int = Field(description='ID of the existing memory to update or delete. Use 0 when adding.')
    kind: Literal['preference', 'topic', 'user_claim']
    content: str = Field(description='Short note in third person, for example: Prefers short answers')


class MemoryPlan(BaseModel):
    actions: list[MemoryAction] = Field(description='Changes to make. Empty list if nothing should change.')


MEMORY_PROMPT = '''You are the Memory Manager. You decide what to remember about ONE user between conversations.

SAVE (action add):
- preference: stable wishes about answer style (length, format, language).
- topic: what the user is working on or investigating, useful for continuing later.
- user_claim: facts the user states about their OWN situation (for example, that their workspace is on the Team plan). These stay unverified.

UPDATE (action update, with the memory id) when the user corrects something already remembered.
DELETE (action delete, with the memory id) when the user asks you to forget something. If they ask to forget everything, delete every memory.

NEVER save: passwords, API keys, tokens, emails, phone numbers, health or other private personal details, customer data, one-off questions, or company facts (those come from the documents, not from memory).
Do not save duplicates. Write each note in third person, under 150 characters.
If nothing should change, return an empty list.

Example: existing memory id=2 'Prefers short answers'; the user says 'actually I prefer detailed answers' -> one update action on id 2, not a new add.'''


def memory_agent(state):
    user_id = state['user_id']
    user_prompt = ('Existing memories:\n' + format_memories(list_memories(user_id))
                   + '\n\nUser message:\n' + state['question']
                   + '\n\nAssistant answer (context only, never save facts from it):\n' + state.get('answer', '(none)'))
    try:
        plan = ask(MemoryPlan, MEMORY_PROMPT, user_prompt)
        changes = apply_actions(user_id, plan.actions)
    except Exception:
        # If memory fails we still want to deliver the answer we already wrote
        return {'memory_changes': [], 'memory_failed': True, 'notes': ['Memory manager: FAILED (answer still delivered)']}
    return {'memory_changes': changes, 'memory_failed': False,
            'notes': ['Memory manager: ' + ('; '.join(changes) if changes else 'no changes')]}


# =====================================================================
# Two fixed replies (no AI call, so they are fast and predictable)
# =====================================================================
def confirm_node(state):
    '''Reply after a memory request: say what changed, or list what is remembered.'''
    if state.get('memory_failed'):
        reply = 'Sorry, I could not update your memory right now. Please try again in a minute.'
    elif state['memory_changes']:
        reply = 'Done:\n' + '\n'.join('- ' + c for c in state['memory_changes'])
    else:
        memories = list_memories(state['user_id'])
        if memories:
            reply = ('Here is what I remember about you (you can edit or delete it on the My memory page):\n'
                     + '\n'.join('- ' + m['content'] for m in memories))
        else:
            reply = 'I do not have anything stored about you yet.'
    return {'answer': reply, 'cited_ids': [], 'answer_status': 'memory'}


def small_talk_node(state):
    reply = ('Hi! I answer questions about Asterline from its documentation: pricing, products, policies, '
             'releases and incidents. I can also remember your preferences between conversations. '
             'What would you like to know?')
    return {'answer': reply, 'cited_ids': [], 'answer_status': 'small_talk'}