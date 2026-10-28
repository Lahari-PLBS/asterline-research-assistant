# eval_cases.py - our evaluation questions.
# expect   : 'found' if the documents contain the fact, 'not_found' if they do not
# cite_any : the answer must cite at least one of these chunk ids (the CURRENT, correct source)
# contains : words or numbers that must all appear in the answer
# history  : earlier chat messages, for follow-up questions
CASES = [
    # ---- simple lookups ----
    {'id': 'L1', 'category': 'lookup', 'question': 'How much does the Launch plan cost per month?',
     'expect': 'found', 'cite_any': ['pricing:0'], 'contains': ['59']},
    {'id': 'L2', 'category': 'lookup', 'question': 'What is the maximum number of run records in one POST /v2/runs request?',
     'expect': 'found', 'cite_any': ['ingest:0'], 'contains': ['400']},
    {'id': 'L3', 'category': 'lookup', 'question': 'How long does the Team plan retain searchable run records?',
     'expect': 'found', 'cite_any': ['pricing:1'], 'contains': ['180']},
    {'id': 'L4', 'category': 'lookup', 'question': 'Which alert destinations does Signals support?',
     'expect': 'found', 'cite_any': ['alerts:1'], 'contains': ['PagerDuty', 'Slack']},
    {'id': 'L5', 'category': 'lookup', 'question': 'How many complete days of history does seasonal anomaly alerting need?',
     'expect': 'found', 'cite_any': ['alerts:0', 'onboarding:1'], 'contains': ['21']},
    {'id': 'L6', 'category': 'lookup', 'question': 'At what error rate does a canary deployment roll back automatically?',
     'expect': 'found', 'cite_any': ['deploy:1'], 'contains': ['0.8']},
    {'id': 'L7', 'category': 'lookup', 'question': 'What is the contractual monthly uptime SLA for Enterprise?',
     'expect': 'found', 'cite_any': ['sla:0'], 'contains': ['99.92']},

    # ---- documents disagree or describe different times ----
    {'id': 'C1', 'category': 'conflict', 'question': 'How long is cold recovery storage kept after the searchable retention period ends?',
     'expect': 'found', 'cite_any': ['retention:0'], 'contains': ['20']},
    {'id': 'C2', 'category': 'conflict', 'question': 'What is the weekly on-call stipend?',
     'expect': 'found', 'cite_any': ['handbook:1'], 'contains': ['175']},
    {'id': 'C3', 'category': 'conflict', 'question': 'What is the current Launch ingestion rate limit per project?',
     'expect': 'found', 'cite_any': ['ingest:1', 'release-21:0'], 'contains': ['300']},
    {'id': 'C4', 'category': 'conflict', 'question': 'What is the AQL query timeout in the current version?',
     'expect': 'found', 'cite_any': ['query:0', 'release-23:0'], 'contains': ['50']},
    {'id': 'C5', 'category': 'conflict', 'question': 'What was the Launch ingestion rate limit in version 2.0?',
     'expect': 'found', 'cite_any': ['release-20:0', 'release-21:0'], 'contains': ['180']},

    # ---- answers that need two or more chunks ----
    {'id': 'M1', 'category': 'multihop', 'question': 'Which plan can export to Redshift, and in which version did that start?',
     'expect': 'found', 'cite_any': ['export:0', 'release-22:0'], 'contains': ['Enterprise', '2.2']},
    {'id': 'M2', 'category': 'multihop', 'question': 'Can a Launch workspace create an EU project?',
     'expect': 'found', 'cite_any': ['pricing:2', 'regions:0'], 'contains': ['US']},
    {'id': 'M3', 'category': 'multihop', 'question': 'I need Run Explorer timelines kept for 45 days. Which plan do I need?',
     'expect': 'found', 'cite_any': ['traces:1'], 'contains': ['Enterprise']},
    {'id': 'M4', 'category': 'multihop', 'question': 'A Team customer wants an EU project and Redshift export. What is possible?',
     'expect': 'found', 'cite_any': ['export:0', 'regions:0', 'pricing:2'], 'contains': ['Redshift', 'EU']},

    # ---- look-alike traps ----
    {'id': 'D1', 'category': 'distractor', 'question': 'Does Run Explorer record what users see on their screens?',
     'expect': 'found', 'cite_any': ['traces:0', 'faq:0'], 'contains': []},
    {'id': 'D2', 'category': 'distractor', 'question': 'What is the query concurrency limit per workspace on Team?',
     'expect': 'found', 'cite_any': ['query:1'], 'contains': ['30']},
    {'id': 'D3', 'category': 'distractor', 'question': 'Was the Warehouse Export duplicate-row problem caused by INC-2025-08?',
     'expect': 'found', 'cite_any': ['incident-08:2'], 'contains': ['ingestion']},
    {'id': 'D4', 'category': 'distractor', 'question': 'How many customers did INC-2025-12 affect?',
     'expect': 'found', 'cite_any': ['incident-12:0'], 'contains': ['29']},

    # ---- information the documents do not contain ----
    {'id': 'X1', 'category': 'missing', 'question': 'What is the monthly list price of the Enterprise plan?', 'expect': 'not_found'},
    {'id': 'X2', 'category': 'missing', 'question': 'On what date will the Asia-Pacific region launch?', 'expect': 'not_found'},
    {'id': 'X3', 'category': 'missing', 'question': 'Who is the CEO of Asterline Labs?', 'expect': 'not_found'},
    {'id': 'X4', 'category': 'missing', 'question': 'Is Asterline HIPAA certified?', 'expect': 'not_found'},

    # ---- follow-up questions that need the chat history ----
    {'id': 'F1', 'category': 'followup', 'question': 'And Team?',
     'history': [{'role': 'user', 'content': 'How long does Launch retain searchable run records?'},
                 {'role': 'assistant', 'content': 'Launch retains searchable run records for 21 days [pricing:1].'}],
     'expect': 'found', 'cite_any': ['pricing:1'], 'contains': ['180']},
    {'id': 'F2', 'category': 'followup', 'question': 'And on Enterprise?',
     'history': [{'role': 'user', 'content': 'What is the Launch ingestion rate limit?'},
                 {'role': 'assistant', 'content': 'Launch allows 300 requests per second per project [ingest:1].'}],
     'expect': 'found', 'cite_any': ['ingest:1'], 'contains': ['6000']},
]