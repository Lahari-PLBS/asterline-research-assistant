# test_memory.py - checks isolation and the privacy filter
import memory

memory.delete_all('test_a')
memory.delete_all('test_b')
memory.add_memory('test_a', 'preference', 'Prefers short answers')

print('A sees:', memory.list_memories('test_a'))
print('B sees:', memory.list_memories('test_b'))
print(memory.redact('my api key = sk-abcdefghijklmnop and email me at x@y.com'))
print(memory.redact('Which API key is required for ingestion?'))
print(memory.is_unsafe_to_store('Has a medical condition'))

memory.delete_all('test_a')