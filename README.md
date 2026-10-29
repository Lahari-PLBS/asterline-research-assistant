College MINT Project

# Asterline Research Assistant

A multi-agent assistant that answers questions from the Asterline documentation (75 chunks) with citations, and remembers each user's preferences across sessions.

## What it does
- Answers only from the supplied documents and cites chunk IDs and titles.
- Resolves conflicting or outdated documents using dates, scope and supersession.
- Says clearly when the documents do not contain an answer.
- Remembers preferences, ongoing topics and user-stated context per user (separate from company evidence), with correction, forgetting and a memory manager screen.
- Six agents with distinct roles, traced step by step in LangSmith.

## Requirements and costs
- Python 3.12 and Git.
- A free Google AI Studio API key for Gemini (no payment needed, rate limited).  Ollama can also be used to run local language models on your machine.
- A free LangSmith account and API key.
- Embeddings and the vector store run locally. No other paid services.

## Setup
```
git clone (https://github.com/Lahari-PLBS/asterline-research-assistant)
cd asterline-research-assistant
python -m venv .venv
```
Activate the environment: Windows `.venv\Scripts\Activate.ps1`, Mac or Linux `source .venv/bin/activate`. Then:
```
pip install -r requirements.txt
```
Copy `.env.example` to `.env` (Windows: `copy .env.example .env`, Mac: `cp .env.example .env`) and put in your two keys.

## Run (one command)
```
streamlit run app.py
```
Open http://localhost:8501. The first start builds the local vector index and downloads the embedding model (about 130 MB).

## Evaluation
```
python evaluate.py before
```
See EVALUATION.md for results. Use `EVAL_PAUSE` (seconds) to slow down on free-tier rate limits.

## LangSmith
Project name: asterline-assistant. Representative runs: (table of links from Step 8.4)
```markdown
| Scenario | Link | What to notice |
|---|---|---|
| Success | (https://apac.smith.langchain.com/public/188bf1da-b511-4f6a-8cb4-d91514a84e9b/r/01a18338-6115-7298-a331-4c2f5fc08674?start_time=2026-10-28T15%3A54%3A32.595128Z) | All six agents ran, answer cites pricing:1 |
| Conflict | (https://apac.smith.langchain.com/public/871624f7-7002-4640-8eda-b34a397722fd/r/01a1834c-009a-76ea-b49b-55288e45091b?start_time=2026-10-28T16%3A15%3A58.61756Z) | Analyst marks security:1 as outdated and picks retention:0 |
| Not found | (https://apac.smith.langchain.com/public/871624f7-7002-4640-8eda-b34a397722fd/r/01a1834c-009a-76ea-b49b-55288e45091b?start_time=2026-10-28T16%3A15%3A58.61756Z) | `fact_found = false`, honest answer |
| Memory | (https://apac.smith.langchain.com/public/9940dcea-1014-43c3-811a-180dab2bd49a/r/01a18358-a8d0-72af-a62d-fb66bcbb288f?start_time=2026-10-28T16%3A29%3A48.112977Z) | Memory manager updates and deletes rows |
| Difficult or failed | () | What went wrong and in which agent |
```

## Documents
DESIGN.md (architecture, memory, trade-offs, limitations), EVALUATION.md, AI_USE.md.

## Notes
- `data/corpus.jsonl` is unchanged from the supplied package.
- All users are synthetic. Memory is stored in `storage/memory.db` (ignored by Git).