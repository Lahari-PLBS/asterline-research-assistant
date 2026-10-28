# Evaluation

## What was measured and why
```markdown
| Metric | How it is checked | Why it matters |
|---|---|---|
| Answer pass rate | Status is right, the right chunk ID is cited, the key number or word appears | Overall research quality |
| Citation hit rate | The answer cites at least one of the correct, current chunks | The brief demands citations that really support the answer |
| Conflict handling | Questions where documents disagree (retention 20 vs 60 days, stipend 175 vs 140, and so on) | The corpus is built with these traps |
| Missing-info accuracy | Questions the documents cannot answer must end as `not_found` | Honest uncertainty, no invented facts |
| Follow-up accuracy | A short follow-up like 'And Team?' is understood from history | Conversation continuity |
| Memory pass rate | Scripted conversations: save, survive a restart, correct, forget, block secrets | Memory design is the biggest grade item (25%) |
| Leaks | User B must never see user A's memory | Must be zero |
```

## How to reproduce
`python evaluate.py before`, then `python compare.py before after`. Cases are in eval_cases.py. Checks are rule-based.

## Improvement
I have changed:
1.  in ANALYST_PROMPT in agents.py, added this as rule 7: 7. If the documents only say that a fact is unpublished, unannounced or must be requested from someone, the specific fact was NOT found: set fact_found to false.
2. n ANALYST_PROMPT, added: 8. When one chunk says it supersedes or replaces another, or a later dated document covers the same topic more specifically, the newer chunk is current and the other is outdated.
3. in ROUTER_PROMPT, added: Always include the subject of the previous question in search_query (for example the metric and the plan names).
4.  in MEMORY_PROMPT, added a short worked example, for instance: Example: existing memory id=2 'Prefers short answers'; the user says 'actually I prefer detailed answers' -> one update action on id 2, not a new add.

