AI-use disclosure
Tools used: Claude by Anthropic for planning and generating starter code and documents; no other AI coding tools.

What it helped produce: project plan, first versions of the Python files, the evaluation cases, document templates.

How I checked the output: I ran every module with its test script, ran my own evaluation suite, inspected LangSmith traces, and corrected the following issues:
1.  in ANALYST_PROMPT in agents.py, added this as rule 7: 7. If the documents only say that a fact is unpublished, unannounced or must be requested from someone, the specific fact was NOT found: set fact_found to false.
2. in ANALYST_PROMPT, added: 8. When one chunk says it supersedes or replaces another, or a later dated document covers the same topic more specifically, the newer chunk is current and the other is outdated.
3. in ROUTER_PROMPT, added: Always include the subject of the previous question in search_query (for example the metric and the plan names).
4.  in MEMORY_PROMPT, added a short worked example, for instance: Example: existing memory id=2 'Prefers short answers'; the user says 'actually I prefer detailed answers' -> one update action on id 2, not a new add.

Runtime AI: the application itself uses a Gemini model through the Google AI Studio free tier. Ollama was also used during development to generate and verify answers locally when Gemini API usage limits were reached.