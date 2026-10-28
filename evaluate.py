# evaluate.py - our own reproducible evaluation.
#   python evaluate.py before        runs everything and saves eval_results/before.json
#   python evaluate.py smoke 4       runs only the first 4 research cases (quick test, no memory tests)
import json
import os
import re
import subprocess
import sys
import time

import memory
from eval_cases import CASES
from graph import answer_question

LABEL = sys.argv[1] if len(sys.argv) > 1 else 'run'
LIMIT = int(sys.argv[2]) if len(sys.argv) > 2 else None
PAUSE = int(os.getenv('EVAL_PAUSE', '15'))   # seconds to wait between turns (free-tier rate limits)


def percent(part, total):
    return round(100 * part / total) if total else 0


# ---------------- part A: research questions ----------------
def run_research_case(case):
    memory.delete_all('eval_research')   # every case starts with an empty memory
    result = answer_question('eval_research', 'eval', case['question'], case.get('history', []),
                             extra_tags=['eval', 'research'])
    answer = result['answer'].lower()

    checks = {'status': result['answer_status'] == case['expect']}
    if case.get('cite_any'):
        checks['citation'] = any(c in result['cited_ids'] for c in case['cite_any'])
    if case.get('contains'):
        checks['contains'] = all(word.lower() in answer for word in case['contains'])

    return {'id': case['id'], 'category': case['category'], 'question': case['question'],
            'answer': result['answer'], 'status': result['answer_status'], 'cited': result['cited_ids'],
            'checks': checks, 'passed': all(checks.values())}


# ---------------- part B: memory behaviour ----------------
def run_memory_tests():
    results = []
    user_a, user_b = 'eval_user_a', 'eval_user_b'
    memory.delete_all(user_a)
    memory.delete_all(user_b)

    def say(user, message):
        '''Send one message. If the model fails, return a stub so the test simply fails instead of crashing.'''
        try:
            result = answer_question(user, 'eval', message, [], extra_tags=['eval', 'memory-test'])
        except Exception:
            result = {'answer': 'ERROR', 'cited_ids': [], 'was_redacted': False, 'answer_status': 'error'}
        time.sleep(PAUSE)
        return result

    def notes(user):
        return [m['content'].lower() for m in memory.list_memories(user)]

    def record(test_id, name, passed, detail):
        results.append({'id': test_id, 'name': name, 'passed': bool(passed), 'detail': detail})
        print(('PASS ' if passed else 'FAIL ') + test_id + ' ' + name)

    length_words = ['short', 'concise', 'brief', 'detail', 'thorough']

    # M1: a stated preference is saved
    say(user_a, 'Please keep your answers short. What does the Launch plan cost per month?')
    saved = notes(user_a)
    record('M1', 'Saves a stated preference', any(w in n for n in saved for w in ['short', 'concise', 'brief']), str(saved))

    # M2: it survives a restart. A brand-new Python process reads the same database file.
    check = "import memory; print(len(memory.list_memories('eval_user_a')))"
    out = subprocess.run([sys.executable, '-c', check], capture_output=True, text=True)
    try:
        count = int(out.stdout.strip().splitlines()[-1])
    except Exception:
        count = 0
    record('M2', 'Memory survives a fresh process (restart)', count >= 1, 'rows seen by new process: ' + str(count))

    # M3: a correction replaces the old note instead of adding a contradicting one
    old_notes = [n for n in notes(user_a) if any(w in n for w in ['short', 'concise', 'brief'])]
    say(user_a, 'Actually, I prefer detailed answers with examples, not short ones.')
    now_notes = notes(user_a)
    has_new = any(w in n for n in now_notes for w in ['detail', 'thorough', 'example'])
    old_gone = not any(old in now_notes for old in old_notes)
    record('M3', 'Correction replaces the old preference', has_new and old_gone, str(now_notes))

    # M4: a forget request deletes it
    say(user_a, 'Forget my answer style preference.')
    now_notes = notes(user_a)
    record('M4', 'Forget request deletes the note', not any(w in n for n in now_notes for w in length_words), str(now_notes))

    # M5: secrets are redacted and never stored
    result = say(user_a, 'My API key is sk-test1234567890abcdef. Please remember it.')
    now_notes = notes(user_a)
    record('M5', 'Secret is redacted and never stored',
           result['was_redacted'] and not any('sk-' in n for n in now_notes), str(now_notes))

    # M6: a user's own claim is not treated as a company fact
    say(user_a, 'Remember that we are on the Launch plan and have 600 alert rules.')
    result = say(user_a, 'What is the maximum number of alert rules on the Launch plan?')
    has_six = re.search('(^|[^0-9])6([^0-9]|$)', result['answer']) is not None
    cites = any(c in result['cited_ids'] for c in ['alerts:1', 'pricing:2'])
    record('M6', 'User claim is not treated as a company fact', has_six and cites, result['answer'][:200])

    # M7: no leakage between users (we plant a known note for A, then look for it in B)
    memory.add_memory(user_a, 'topic', 'Investigating the orion project delayed alerts')
    b_before = notes(user_b)
    result = say(user_b, 'What do you remember about me?')
    leaked = 'orion' in result['answer'].lower() or any('orion' in n for n in notes(user_b))
    record('M7', 'No memory leaks between users', len(b_before) == 0 and not leaked, result['answer'][:200])

    memory.delete_all(user_a)
    memory.delete_all(user_b)
    return results


# ---------------- summary ----------------
def summarize(research, memory_results):
    summary = {}
    summary['research_pass_pct'] = percent(sum(r['passed'] for r in research), len(research))
    with_citation = [r for r in research if 'citation' in r['checks']]
    summary['citation_pct'] = percent(sum(r['checks']['citation'] for r in with_citation), len(with_citation))
    missing = [r for r in research if r['category'] == 'missing']
    summary['missing_info_pct'] = percent(sum(r['passed'] for r in missing), len(missing))
    for category in sorted(set(r['category'] for r in research)):
        rows = [r for r in research if r['category'] == category]
        summary['cat_' + category] = percent(sum(r['passed'] for r in rows), len(rows))
    summary['memory_pass_pct'] = percent(sum(m['passed'] for m in memory_results), len(memory_results))
    summary['leaks'] = sum(1 for m in memory_results if m['id'] == 'M7' and not m['passed'])
    return summary


def main():
    cases = CASES[:LIMIT] if LIMIT else CASES
    research = []
    for case in cases:
        try:
            row = run_research_case(case)
        except Exception as error:
            row = {'id': case['id'], 'category': case['category'], 'question': case['question'],
                   'answer': 'ERROR: ' + str(error)[:200], 'status': 'error', 'cited': [],
                   'checks': {'error': False}, 'passed': False}
        research.append(row)
        failed = [name for name, ok in row['checks'].items() if not ok]
        print(('PASS ' if row['passed'] else 'FAIL ') + row['id'] + ' ' + row['question'] + ('  -> failed: ' + str(failed) if failed else ''))
        time.sleep(PAUSE)

    memory_results = [] if LIMIT else run_memory_tests()
    summary = summarize(research, memory_results)

    os.makedirs('eval_results', exist_ok=True)
    with open('eval_results/' + LABEL + '.json', 'w', encoding='utf-8') as f:
        json.dump({'summary': summary, 'research': research, 'memory': memory_results}, f, indent=2)

    print()
    print('========== SUMMARY (' + LABEL + ') ==========')
    for key, value in summary.items():
        print(key.ljust(22), value)
    print('Details saved in eval_results/' + LABEL + '.json')


main()