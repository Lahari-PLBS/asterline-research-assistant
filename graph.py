# graph.py - connects the agents into one flow using LangGraph.
import operator
from typing import Annotated, TypedDict

from langgraph.graph import StateGraph, START, END

from agents import (router_agent, retriever_agent, analyst_agent, writer_agent,
                    verifier_agent, memory_agent, confirm_node, small_talk_node)
from memory import list_memories, redact


class State(TypedDict, total=False):
    '''The shared notebook that every agent reads from and writes to.'''
    user_id: str
    question: str
    history: list
    memories: list
    intent: str
    search_query: str
    chunks: list
    analysis: dict
    answer: str
    cited_ids: list
    answer_status: str        # answered | not_found | memory | small_talk
    verifier_ok: bool
    verifier_feedback: str
    retries: int
    memory_changes: list
    memory_failed: bool
    # Every agent ADDS a line here. The UI shows it as 'agent steps'.
    notes: Annotated[list, operator.add]


# ---------------- decision functions: they pick the next step ----------------
def choose_path(state):
    if state['intent'] == 'company_question':
        return 'company'
    if state['intent'] == 'memory_request':
        return 'memory'
    return 'chat'


def after_writer(state):
    # If the documents did not contain the fact, there is nothing to verify
    return 'verify' if state['answer_status'] == 'answered' else 'memory'


def after_verifier(state):
    # The verifier counts failures in 'retries'. One failure = one more try for the writer.
    if not state['verifier_ok'] and state.get('retries', 0) < 2:
        return 'retry'
    return 'memory'


def after_memory(state):
    return 'confirm' if state['intent'] == 'memory_request' else 'end'


def build_graph():
    g = StateGraph(State)

    g.add_node('router', router_agent)
    g.add_node('retriever', retriever_agent)
    g.add_node('analyst', analyst_agent)
    g.add_node('writer', writer_agent)
    g.add_node('verifier', verifier_agent)
    g.add_node('memory_agent', memory_agent)
    g.add_node('confirm', confirm_node)
    g.add_node('small_talk', small_talk_node)

    g.add_edge(START, 'router')
    g.add_conditional_edges('router', choose_path,
                            {'company': 'retriever', 'memory': 'memory_agent', 'chat': 'small_talk'})
    g.add_edge('retriever', 'analyst')
    g.add_edge('analyst', 'writer')
    g.add_conditional_edges('writer', after_writer, {'verify': 'verifier', 'memory': 'memory_agent'})
    g.add_conditional_edges('verifier', after_verifier, {'retry': 'writer', 'memory': 'memory_agent'})
    g.add_conditional_edges('memory_agent', after_memory, {'confirm': 'confirm', 'end': END})
    g.add_edge('confirm', END)
    g.add_edge('small_talk', END)
    return g.compile()


GRAPH = build_graph()


def answer_question(user_id, session_id, question, history, extra_tags=None):
    '''Run one conversation turn and return the final state (a dictionary).'''
    clean_question = redact(question)   # secrets never reach the model, the memory or LangSmith
    clean_history = [{'role': m['role'], 'content': redact(m['content'])} for m in history]

    start_state = {
        'user_id': user_id,
        'question': clean_question,
        'history': clean_history,
        'memories': list_memories(user_id),
        'retries': 0,
        'notes': [],
    }
    # These show up in LangSmith so we can filter runs by user, session and purpose
    config = {
        'run_name': 'asterline_turn',
        'tags': ['asterline'] + (extra_tags or []),
        'metadata': {'user_id': user_id, 'session_id': session_id},
    }
    result = GRAPH.invoke(start_state, config=config)
    result['was_redacted'] = (clean_question != question)
    return result