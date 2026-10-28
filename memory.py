# memory.py - per-user memory stored in SQLite.
# RULE: every function takes user_id and every SQL query filters by user_id,
# so one user can never read or change another user's memory.
import os
import re
import sqlite3
from datetime import datetime

DB_PATH = 'storage/memory.db'


def connect():
    os.makedirs('storage', exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # lets us read columns by name
    return conn


def init_db():
    '''Create the memories table if it does not exist yet.'''
    conn = connect()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()


init_db()  # runs once when this file is imported


# ---------------- privacy filter ----------------
# Patterns that look like secrets or private contact details.
SECRET_PATTERNS = [
    'sk-[A-Za-z0-9_-]{10,}',                    # OpenAI-style keys
    'AIza[A-Za-z0-9_-]{20,}',                   # Google API keys
    'lsv2_[A-Za-z0-9_]{10,}',                   # LangSmith keys
    'Bearer [A-Za-z0-9_.-]{10,}',               # bearer tokens
    '(password|passwd|secret|token|api[ _-]?key)[ ]*[=:][ ]*[^ ]{6,}',   # key = value
    '(password|passwd)[ ]+is[ ]+[^ ]+',         # password is xyz
    '[A-Za-z0-9_.+-]+@[A-Za-z0-9-]+[.][A-Za-z0-9.-]+',   # email addresses
    '[+]?[0-9][0-9 -]{8,}[0-9]',                # phone-number-like numbers
]

# Topics we do not want in memory (the handbook says to keep private medical details out of shared notes)
SENSITIVE_WORDS = ['diagnos', 'medical', 'medication', 'illness', 'surgery',
                   'pregnan', 'therapy', 'salary', 'religion', 'visa status']


def redact(text):
    '''Replace anything that looks like a secret with [REDACTED].'''
    for pattern in SECRET_PATTERNS:
        text = re.sub(pattern, '[REDACTED]', text, flags=re.IGNORECASE)
    return text


def is_unsafe_to_store(text):
    '''True if the text contains a secret or a sensitive personal topic.'''
    if redact(text) != text:
        return True
    lowered = text.lower()
    return any(word in lowered for word in SENSITIVE_WORDS)


# ---------------- basic operations ----------------
def now():
    return datetime.now().isoformat(timespec='seconds')


def list_memories(user_id):
    conn = connect()
    rows = conn.execute('SELECT * FROM memories WHERE user_id = ? ORDER BY id', (user_id,)).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def add_memory(user_id, kind, content):
    conn = connect()
    conn.execute(
        'INSERT INTO memories (user_id, kind, content, created_at, updated_at) VALUES (?, ?, ?, ?, ?)',
        (user_id, kind, content, now(), now()),
    )
    conn.commit()
    conn.close()


def update_memory(user_id, memory_id, content):
    conn = connect()
    # 'AND user_id = ?' makes sure a user can only change their own rows
    conn.execute('UPDATE memories SET content = ?, updated_at = ? WHERE id = ? AND user_id = ?',
                 (content, now(), memory_id, user_id))
    conn.commit()
    conn.close()


def delete_memory(user_id, memory_id):
    conn = connect()
    conn.execute('DELETE FROM memories WHERE id = ? AND user_id = ?', (memory_id, user_id))
    conn.commit()
    conn.close()


def delete_all(user_id):
    conn = connect()
    conn.execute('DELETE FROM memories WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()


# ---------------- applying the memory agent's plan ----------------
def apply_actions(user_id, actions):
    '''Apply the memory agent's plan safely. Returns a list of plain-English changes.'''
    changes = []
    current = {m['id']: m for m in list_memories(user_id)}   # only THIS user's memories

    for a in actions:
        content = a.content.strip()[:200]   # keep notes short

        # Safety net in code, in case the AI model makes a mistake
        if a.action in ('add', 'update'):
            if not content or is_unsafe_to_store(content):
                changes.append('Skipped one item because it looked sensitive')
                continue

        if a.action == 'add':
            already_saved = [m['content'].lower() for m in current.values()]
            if content.lower() in already_saved:
                continue   # do not save the same note twice
            add_memory(user_id, a.kind, content)
            changes.append('Remembered: ' + content)

        elif a.action == 'update' and a.memory_id in current:   # id must belong to this user
            old_text = current[a.memory_id]['content']
            update_memory(user_id, a.memory_id, content)
            changes.append('Updated: ' + old_text + '  ->  ' + content)

        elif a.action == 'delete' and a.memory_id in current:
            delete_memory(user_id, a.memory_id)
            changes.append('Forgot: ' + current[a.memory_id]['content'])

    return changes