AI-use disclosure
Tools used: Claude by Anthropic for planning and generating starter code and documents; no other AI coding tools.

What it helped produce: project plan, first versions of the Python files, the evaluation cases, document templates.

How I checked the output: I ran every module with its test script, read each file and can explain it, ran my own evaluation suite, inspected LangSmith traces, and corrected the following issues: (list real ones you fixed.)

Runtime AI: the application itself uses a Gemini model through the Google AI Studio free tier. Ollama was also used during development to generate and verify answers locally when Gemini API usage limits were reached.