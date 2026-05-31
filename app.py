import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning, module="langchain_community")

import streamlit as st
from db import get_db
from chain import ask

# ── Page Config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI SQL Assistant",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Syne:wght@400;600;700;800&display=swap');

    /* Base */
    html, body, [class*="css"] {
        font-family: 'Syne', sans-serif;
    }

    /* Background */
    .stApp {
        background-color: #0d0f14;
        color: #e2e8f0;
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #111318;
        border-right: 1px solid #1e2130;
    }

    /* Header */
    .app-header {
        padding: 2rem 0 1.5rem 0;
        border-bottom: 1px solid #1e2130;
        margin-bottom: 2rem;
    }
    .app-title {
        font-size: 2.2rem;
        font-weight: 800;
        background: linear-gradient(135deg, #6ee7f7 0%, #a78bfa 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin: 0;
        line-height: 1.2;
    }
    .app-subtitle {
        color: #64748b;
        font-size: 0.95rem;
        margin-top: 0.4rem;
        font-family: 'JetBrains Mono', monospace;
    }

    /* Input area */
    .stTextArea textarea {
        background-color: #111318 !important;
        border: 1px solid #1e2130 !important;
        border-radius: 10px !important;
        color: #e2e8f0 !important;
        font-family: 'Syne', sans-serif !important;
        font-size: 1rem !important;
        padding: 1rem !important;
    }
    .stTextArea textarea:focus {
        border-color: #6ee7f7 !important;
        box-shadow: 0 0 0 2px rgba(110, 231, 247, 0.1) !important;
    }

    /* Buttons */
    .stButton > button {
        background: linear-gradient(135deg, #6ee7f7, #a78bfa);
        color: #0d0f14;
        font-family: 'Syne', sans-serif;
        font-weight: 700;
        font-size: 0.95rem;
        border: none;
        border-radius: 8px;
        padding: 0.6rem 2rem;
        cursor: pointer;
        transition: opacity 0.2s ease;
        width: 100%;
    }
    .stButton > button:hover {
        opacity: 0.88;
    }

    /* Result cards */
    .result-card {
        background-color: #111318;
        border: 1px solid #1e2130;
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1rem;
    }
    .result-card-label {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.7rem;
        color: #6ee7f7;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        margin-bottom: 0.75rem;
        font-weight: 600;
    }
    .sql-block {
        background-color: #0d0f14;
        border: 1px solid #1e2130;
        border-left: 3px solid #6ee7f7;
        border-radius: 6px;
        padding: 1rem;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.88rem;
        color: #a78bfa;
        white-space: pre-wrap;
        word-break: break-word;
    }
    .result-block {
        background-color: #0d0f14;
        border: 1px solid #1e2130;
        border-left: 3px solid #a78bfa;
        border-radius: 6px;
        padding: 1rem;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.85rem;
        color: #94a3b8;
        white-space: pre-wrap;
        word-break: break-word;
    }

    /* History items */
    .history-item {
        background-color: #111318;
        border: 1px solid #1e2130;
        border-radius: 8px;
        padding: 0.75rem 1rem;
        margin-bottom: 0.5rem;
        cursor: pointer;
        font-size: 0.88rem;
        color: #94a3b8;
        transition: border-color 0.2s;
    }
    .history-item:hover {
        border-color: #6ee7f7;
        color: #e2e8f0;
    }

    /* Status badges */
    .badge-success {
        display: inline-block;
        background: rgba(110, 231, 247, 0.1);
        color: #6ee7f7;
        border: 1px solid rgba(110, 231, 247, 0.2);
        border-radius: 20px;
        padding: 0.2rem 0.8rem;
        font-size: 0.75rem;
        font-family: 'JetBrains Mono', monospace;
        font-weight: 600;
    }
    .badge-error {
        display: inline-block;
        background: rgba(248, 113, 113, 0.1);
        color: #f87171;
        border: 1px solid rgba(248, 113, 113, 0.2);
        border-radius: 20px;
        padding: 0.2rem 0.8rem;
        font-size: 0.75rem;
        font-family: 'JetBrains Mono', monospace;
        font-weight: 600;
    }

    /* Divider */
    hr {
        border-color: #1e2130;
    }

    /* Sidebar labels */
    .sidebar-label {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.7rem;
        color: #6ee7f7;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        font-weight: 600;
        margin-bottom: 0.5rem;
    }

    /* Toggle */
    .stCheckbox label {
        color: #94a3b8 !important;
        font-size: 0.88rem !important;
    }

    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
</style>
""", unsafe_allow_html=True)


# ── Session State Init ─────────────────────────────────────────────────────────
if "db" not in st.session_state:
    st.session_state.db = None
if "db_connected" not in st.session_state:
    st.session_state.db_connected = False
if "history" not in st.session_state:
    st.session_state.history = []
if "current_result" not in st.session_state:
    st.session_state.current_result = None


# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<p class="sidebar-label">Connection</p>', unsafe_allow_html=True)

    # DB Connection button
    if not st.session_state.db_connected:
        if st.button("🔌 Connect to Database"):
            with st.spinner("Connecting..."):
                try:
                    st.session_state.db = get_db()
                    st.session_state.db_connected = True
                    st.success("Connected!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Connection failed: {e}")
    else:
        st.markdown('<span class="badge-success">● Connected</span>', unsafe_allow_html=True)
        st.markdown("")

        # Show available tables
        try:
            tables = st.session_state.db.get_usable_table_names()
            if tables:
                st.markdown('<p class="sidebar-label" style="margin-top:1rem;">Tables</p>', unsafe_allow_html=True)
                for table in tables:
                    st.markdown(f"`{table}`")
            else:
                st.caption("No tables found in database.")
        except Exception:
            pass

        # Disconnect
        st.markdown("---")
        if st.button("🔌 Disconnect"):
            st.session_state.db = None
            st.session_state.db_connected = False
            st.session_state.history = []
            st.session_state.current_result = None
            st.rerun()

    st.markdown("---")

    # Settings
    st.markdown('<p class="sidebar-label">Settings</p>', unsafe_allow_html=True)
    use_few_shot = st.checkbox("Use few-shot examples", value=False,
                               help="Adds example Q&A pairs to the prompt for better accuracy on complex queries.")
    show_sql = st.checkbox("Always show SQL", value=True,
                           help="Display the generated SQL query alongside the result.")

    st.markdown("---")

    # History
    if st.session_state.history:
        st.markdown('<p class="sidebar-label">History</p>', unsafe_allow_html=True)
        for i, item in enumerate(reversed(st.session_state.history[-8:])):
            truncated = item["question"][:45] + "..." if len(item["question"]) > 45 else item["question"]
            st.markdown(f'<div class="history-item">↗ {truncated}</div>', unsafe_allow_html=True)

        if st.button("🗑 Clear History"):
            st.session_state.history = []
            st.session_state.current_result = None
            st.rerun()

    st.markdown("---")
    st.markdown('<p style="font-size:0.75rem;color:#334155;font-family:JetBrains Mono,monospace;">Mistral Large 3 · 675B<br>NVIDIA NIM Free Tier</p>', unsafe_allow_html=True)


# ── Main Area ──────────────────────────────────────────────────────────────────
st.markdown("""
<div class="app-header">
    <h1 class="app-title">AI SQL Assistant</h1>
    <p class="app-subtitle">natural language → postgresql · powered by mistral large 3</p>
</div>
""", unsafe_allow_html=True)

# Connection gate
if not st.session_state.db_connected:
    st.info("👈 Connect to your database using the sidebar to get started.")
    st.stop()

# Question input
question = st.text_area(
    "Ask a question about your data",
    placeholder="e.g. How many users signed up last month? · Show the top 5 products by revenue",
    height=100,
    label_visibility="collapsed"
)

col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    run_btn = st.button("⚡ Generate & Run SQL")
with col2:
    clear_btn = st.button("✕ Clear")

if clear_btn:
    st.session_state.current_result = None
    st.rerun()

# ── Run the chain ──────────────────────────────────────────────────────────────
if run_btn:
    if not question.strip():
        st.warning("Please enter a question first.")
    else:
        with st.spinner("Thinking..."):
            try:
                output = ask(
                    question=question.strip(),
                    db=st.session_state.db,
                    use_few_shot=use_few_shot
                )
                st.session_state.current_result = output
                st.session_state.history.append(output)
            except Exception as e:
                st.error(f"Something went wrong: {e}")

# ── Display Results ────────────────────────────────────────────────────────────
if st.session_state.current_result:
    output = st.session_state.current_result

    st.markdown("---")

    # SQL block
    if show_sql or output["sql"] == "None":
        st.markdown(f"""
        <div class="result-card">
            <div class="result-card-label">Generated SQL</div>
            <div class="sql-block">{output["sql"]}</div>
        </div>
        """, unsafe_allow_html=True)

    # Result block
    is_error = output["result"].startswith("❌")
    st.markdown(f"""
    <div class="result-card">
        <div class="result-card-label">Result &nbsp;
            {"<span class='badge-error'>Error</span>" if is_error else "<span class='badge-success'>Success</span>"}
        </div>
        <div class="result-block">{output["result"]}</div>
    </div>
    """, unsafe_allow_html=True)