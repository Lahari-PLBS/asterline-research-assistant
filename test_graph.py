# test_graph.py - runs a few turns through the whole system
import memory
from graph import answer_question

memory.delete_all('demo')

# Part A: company questions (one has a conflict, one has a missing fact)
questions = [
    'How long does cold recovery storage keep raw run records after searchable retention ends?',
    'What is the weekly on-call stipend?',
    'What is the monthly price of the Enterprise plan?',
]
for q in questions:
    result = answer_question('demo', 'test-session', q, [])
    print('Q:', q)
    print('A:', result['answer'])
    print('Status:', result['answer_status'], '| Cited:', result['cited_ids'])
    print('Steps:', result['notes'])
    print()

# Part B: memory (save, then forget)
for message in ['Please keep your answers short. I am investigating delayed alerts.',
                'Forget my answer-length preference.']:
    result = answer_question('demo', 'test-session', message, [])
    print('User:', message)
    print('Assistant:', result['answer'])
    print('Memory now:', [m['content'] for m in memory.list_memories('demo')])
    print()

memory.delete_all('demo')