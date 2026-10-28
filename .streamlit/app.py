# app.py - the Streamlit user interface. Start it with:  streamlit run app.py
import uuid
import streamlit as st

import memory
from graph import answer_question
from retrieval import CHUNKS_BY_ID

st.set_page_config(page_title='Asterline Research Assistant', page_icon='🔎', layout='wide')

USERS = ['alice', 'bob', 'carol']   # synthetic users that simulate separate people
KIND_LABELS = {
    'preference': 'Preference',
    'topic': 'Ongoing topic',
    'user_claim': 'Stated by you (unverified)',
}
EXAMPLES = [
    'How long does Team keep searchable run records?',
    'What is the Launch ingestion rate limit now, and what was it before version 2.1?',
    'How long is cold recovery storage kept after searchable retention ends?',
    'What is the monthly price of the Enterprise plan?',
]

# A little CSS for the coloured badges and a tidier page width
st.markdown('''
<style>
.block-container {padding-top: 2rem; max-width: 1000px;}
.badge {display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 12px;
        font-weight: 600; margin-right: 6px;}
.badge-green {background: #e6f4ea; color: #137333;}
.badge-amber {background: #fef7e0; color: #8a5a00;}
.badge-blue {background: #e8f0fe; color: #174ea6;}
.badge-grey {background: #eceff1; color: #37474f;}
</style>
''', unsafe_allow_html=True)


@st.cache_resource(show_spinner='Loading the search index (first run only)...')
def warm_up():
    '''Load the embedding model and the vector index once, so the first question is not slow.'''
    from retrieval import get_embedder, get_collection
    get_embedder()
    get_collection()
    return True


warm_up()


# ---------------- session state (Streamlit forgets variables on every click unless we keep them here) ----------------
def reset_chat():
    st.session_state.messages = []
    st.session_state.session_id = uuid.uuid4().hex[:8]
    st.session_state.pending = None


if 'user' not in st.session_state:
    st.session_state.user = USERS[0]
    reset_chat()


# ---------------- sidebar ----------------
with st.sidebar:
    st.title('🔎 Asterline Assistant')
    st.caption('Answers from company documentation, with citations.')

    chosen = st.selectbox('Signed in as (demo user)', USERS, index=USERS.index(st.session_state.user))
    if chosen != st.session_state.user:   # switching user starts a fresh chat
        st.session_state.user = chosen
        reset_chat()
        st.rerun()
    user_id = st.session_state.user

    page = st.radio('Go to', ['💬 Chat', '🧠 My memory'], label_visibility='collapsed')
    if st.button('➕ New conversation'):
        reset_chat()
        st.rerun()

    st.caption(str(len(memory.list_memories(user_id))) + ' items remembered about ' + user_id)
    with st.expander('How it works'):
        st.markdown(
            '1. **Router** understands your message.  \n'
            '2. **Retriever** searches the documents.  \n'
            '3. **Evidence analyst** resolves conflicts between documents.  \n'
            '4. **Writer** answers with citations.  \n'
            '5. **Verifier** checks the answer against the sources.  \n'
            '6. **Memory manager** keeps your preferences, separate from company facts.'
        )


# ---------------- chat page ----------------
def show_details(msg):
    '''Badges, sources and agent steps shown under an assistant message.'''
    badges = ''
    status = msg.get('status')
    if status == 'answered':
        badges += '<span class="badge badge-green">Answered from documents</span>'
        if msg.get('verified'):
            badges += '<span class="badge badge-green">Verified</span>'
        else:
            badges += '<span class="badge badge-amber">Not fully verified</span>'
    elif status == 'not_found':
        badges += '<span class="badge badge-amber">Not in the documents</span>'
    elif status == 'memory':
        badges += '<span class="badge badge-blue">Memory</span>'
    elif status == 'error':
        badges += '<span class="badge badge-grey">Temporary problem</span>'
    if badges:
        st.markdown(badges, unsafe_allow_html=True)

    if msg.get('redacted'):
        st.caption('🔒 Something that looked like a secret was removed from your message before it was processed.')
    if status != 'memory' and msg.get('memory_changes'):
        st.caption('🧠 Memory updated: ' + '; '.join(msg['memory_changes']))

    if msg.get('sources'):
        with st.expander('📚 Sources (' + str(len(msg['sources'])) + ')'):
            for chunk_id in msg['sources']:
                c = CHUNKS_BY_ID[chunk_id]
                st.markdown('**' + c['title'] + '** · `' + chunk_id + '` · published ' + c['published']
                            + ' · version ' + c['version'])
                st.caption(c['text'])
    if msg.get('notes'):
        with st.expander('🧭 Agent steps'):
            for note in msg['notes']:
                st.caption(note)


def chat_page(user_id):
    st.header('Ask about Asterline')
    st.caption('Answers come only from the documentation. What I remember about you is kept separate '
               'and never counts as evidence for a company fact.')

    # Empty chat: show example questions as buttons
    if not st.session_state.messages:
        st.markdown('**Try one of these:**')
        columns = st.columns(2)
        for i, example in enumerate(EXAMPLES):
            if columns[i % 2].button(example, key='example_' + str(i)):
                st.session_state.pending = example
                st.rerun()

    # Show the conversation so far
    for msg in st.session_state.messages:
        with st.chat_message(msg['role']):
            st.markdown(msg['content'])
            if msg['role'] == 'assistant':
                show_details(msg)

    question = st.chat_input('Ask a question, or tell me something to remember...')
    if st.session_state.pending:   # an example button was clicked
        question = st.session_state.pending
        st.session_state.pending = None

    if question:
        with st.chat_message('user'):
            st.markdown(question)
        history = [{'role': m['role'], 'content': m['content']} for m in st.session_state.messages]
        st.session_state.messages.append({'role': 'user', 'content': question})

        with st.chat_message('assistant'):
            with st.spinner('Searching the documentation...'):
                try:
                    result = answer_question(user_id, st.session_state.session_id, question, history)
                    reply = {
                        'role': 'assistant',
                        'content': result['answer'],
                        'status': result['answer_status'],
                        'verified': result.get('verifier_ok', False),
                        'sources': result['cited_ids'],
                        'notes': result['notes'],
                        'memory_changes': result.get('memory_changes', []),
                        'redacted': result['was_redacted'],
                    }
                except Exception:
                    # Provider down, rate limit after all retries, and so on: show a calm message, keep the app alive
                    reply = {
                        'role': 'assistant',
                        'content': 'Sorry, the language model is busy or unavailable right now. '
                                   'Nothing was lost. Please try again in a minute.',
                        'status': 'error',
                    }
        st.session_state.messages.append(reply)
        st.rerun()   # redraw so the sidebar memory counter is up to date


# ---------------- memory page ----------------
def memory_page(user_id):
    st.header('My memory')
    st.caption('Everything the assistant remembers about ' + user_id + '. Only this user sees it. You can edit or '
               'delete any item. Memory is used for personalisation only, never as proof of a company fact.')

    items = memory.list_memories(user_id)
    if not items:
        st.info('Nothing is stored yet. In the chat you could say: I prefer short answers.')

    for m in items:
        with st.container(border=True):
            left, middle, right = st.columns([2, 6, 2])
            left.markdown('<span class="badge badge-blue">' + KIND_LABELS[m['kind']] + '</span>',
                          unsafe_allow_html=True)
            left.caption('Updated ' + m['updated_at'])
            new_text = middle.text_input('Note', value=m['content'], key='text_' + str(m['id']),
                                         label_visibility='collapsed')
            if right.button('Save', key='save_' + str(m['id'])):
                if not new_text.strip() or memory.is_unsafe_to_store(new_text):
                    st.error('That note is empty or looks sensitive, so it was not saved.')
                else:
                    memory.update_memory(user_id, m['id'], new_text.strip()[:200])
                    st.rerun()
            if right.button('Delete', key='delete_' + str(m['id'])):
                memory.delete_memory(user_id, m['id'])
                st.rerun()

    st.subheader('Add a note')
    with st.form('add_note', clear_on_submit=True):
        kind = st.selectbox('Type', list(KIND_LABELS.keys()), format_func=lambda k: KIND_LABELS[k])
        text = st.text_input('Note', placeholder='For example: Prefers short answers')
        submitted = st.form_submit_button('Add')
    if submitted:
        if not text.strip() or memory.is_unsafe_to_store(text):
            st.error('That note is empty or looks sensitive, so it was not saved.')
        else:
            memory.add_memory(user_id, kind, text.strip()[:200])
            st.rerun()

    st.subheader('Forget everything')
    confirm = st.checkbox('Yes, delete everything remembered about ' + user_id)
    if st.button('Delete all my memory', disabled=not confirm):
        memory.delete_all(user_id)
        st.rerun()


# ---------------- show the selected page ----------------
if page == '💬 Chat':
    chat_page(user_id)
else:
    memory_page(user_id)