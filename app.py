import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning, module="langchain_community")

import html
import logging
import re
import pandas as pd
import streamlit as st
from db import get_db
from chain import ask

logger = logging.getLogger(__name__)

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

    html, body, [class*="css"] { font-family: 'Syne', sans-serif; }
    .stApp { background-color: #0d0f14; color: #e2e8f0; }
    [data-testid="stSidebar"] { background-color: #111318; border-right: 1px solid #1e2130; }

    .app-header { padding: 2rem 0 1.5rem 0; border-bottom: 1px solid #1e2130; margin-bottom: 2rem; }
    .app-title {
        font-size: 2.2rem; font-weight: 800;
        background: linear-gradient(135deg, #6ee7f7 0%, #a78bfa 100%);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        background-clip: text; margin: 0; line-height: 1.2;
    }
    .app-subtitle { color: #64748b; font-size: 0.95rem; margin-top: 0.4rem; font-family: 'JetBrains Mono', monospace; }

    .stTextArea textarea {
        background-color: #111318 !important; border: 1px solid #1e2130 !important;
        border-radius: 10px !important; color: #e2e8f0 !important;
        font-family: 'Syne', sans-serif !important; font-size: 1rem !important; padding: 1rem !important;
    }
    .stTextArea textarea:focus { border-color: #6ee7f7 !important; box-shadow: 0 0 0 2px rgba(110,231,247,.1) !important; }

    .stButton > button {
        background: linear-gradient(135deg, #6ee7f7, #a78bfa);
        color: #0d0f14; font-family: 'Syne', sans-serif; font-weight: 700;
        font-size: 0.95rem; border: none; border-radius: 8px;
        padding: 0.6rem 2rem; cursor: pointer; transition: opacity .2s ease; width: 100%;
    }
    .stButton > button:hover { opacity: .88; }

    /* ── Result panels ──────────────────────────────────────────── */
    .panel-label {
        font-family: 'JetBrains Mono', monospace; font-size: .7rem; color: #6ee7f7;
        text-transform: uppercase; letter-spacing: .12em; font-weight: 600;
        margin-bottom: .75rem; display: flex; align-items: center; gap: .5rem;
    }
    .panel-label .icon { font-size: .9rem; }

    /* ── Status bar ─────────────────────────────────────────────── */
    .status-bar {
        display: flex; align-items: center; gap: .6rem;
        margin-bottom: .75rem; flex-wrap: wrap;
    }
    .badge-success {
        display:inline-flex; align-items:center; gap:.3rem;
        background:rgba(110,231,247,.08); color:#6ee7f7;
        border:1px solid rgba(110,231,247,.18); border-radius:20px;
        padding:.25rem .85rem; font-size:.75rem;
        font-family:'JetBrains Mono',monospace; font-weight:600;
    }
    .badge-error {
        display:inline-flex; align-items:center; gap:.3rem;
        background:rgba(248,113,113,.08); color:#f87171;
        border:1px solid rgba(248,113,113,.18); border-radius:20px;
        padding:.25rem .85rem; font-size:.75rem;
        font-family:'JetBrains Mono',monospace; font-weight:600;
    }
    .badge-rows {
        display:inline-flex; align-items:center; gap:.3rem;
        background:rgba(167,139,250,.08); color:#a78bfa;
        border:1px solid rgba(167,139,250,.18); border-radius:20px;
        padding:.25rem .85rem; font-size:.75rem;
        font-family:'JetBrains Mono',monospace; font-weight:600;
    }
    .badge-empty {
        display:inline-flex; align-items:center; gap:.3rem;
        background:rgba(100,116,139,.08); color:#94a3b8;
        border:1px solid rgba(100,116,139,.18); border-radius:20px;
        padding:.25rem .85rem; font-size:.75rem;
        font-family:'JetBrains Mono',monospace; font-weight:600;
    }
    .badge-category {
        display:inline-flex; align-items:center; gap:.3rem;
        background:rgba(251,191,36,.08); color:#fbbf24;
        border:1px solid rgba(251,191,36,.18); border-radius:20px;
        padding:.25rem .85rem; font-size:.75rem;
        font-family:'JetBrains Mono',monospace; font-weight:600;
    }

    /* ── History ────────────────────────────────────────────────── */
    .history-item {
        background-color: #111318; border: 1px solid #1e2130; border-radius: 8px;
        padding: .75rem 1rem; margin-bottom: .5rem; font-size: .88rem; color: #94a3b8;
    }
    .sidebar-label {
        font-family:'JetBrains Mono',monospace; font-size:.7rem; color:#6ee7f7;
        text-transform:uppercase; letter-spacing:.12em; font-weight:600; margin-bottom:.5rem;
    }
    .stCheckbox label { color:#94a3b8 !important; font-size:.88rem !important; }
    hr { border-color: #1e2130; }
    #MainMenu {visibility:hidden;} footer {visibility:hidden;} header {visibility:hidden;}
</style>
""", unsafe_allow_html=True)


# ── Error Classification ──────────────────────────────────────────────────────

# Each pattern maps to (category_label, friendly_message, suggestion)
_ERROR_PATTERNS: list[tuple[re.Pattern, str, str, str]] = [
    (
        re.compile(r"SyntaxError|syntax error", re.IGNORECASE),
        "Syntax Error",
        "The generated SQL query contains a syntax error and could not be executed.",
        "Try rephrasing your question with simpler language, or click **Regenerate SQL** below.",
    ),
    (
        re.compile(r"UndefinedColumn|column .+ does not exist|unknown column", re.IGNORECASE),
        "Unknown Column",
        "The generated SQL references a column that does not exist in the database.",
        "The AI may have guessed a column name. Try asking about specific table fields, or rephrase your question.",
    ),
    (
        re.compile(r"UndefinedTable|relation .+ does not exist|unknown table", re.IGNORECASE),
        "Unknown Table",
        "The generated SQL references a table that does not exist in the database.",
        "Check the available tables in the sidebar. The AI may have hallucinated a table name.",
    ),
    (
        re.compile(r"AmbiguousColumn|ambiguous column|column reference .+ is ambiguous", re.IGNORECASE),
        "Ambiguous Column",
        "The generated SQL contains an ambiguous column reference that exists in multiple tables.",
        "Try specifying which table you're asking about in your question.",
    ),
    (
        re.compile(r"PermissionDenied|permission denied|access denied|insufficient privilege", re.IGNORECASE),
        "Permission Denied",
        "The database user does not have permission to execute this query.",
        "Contact your database administrator to grant the required permissions.",
    ),
    (
        re.compile(r"ConnectionError|connection refused|could not connect|broken pipe", re.IGNORECASE),
        "Connection Error",
        "The database connection was lost or could not be established.",
        "Click **Disconnect** and then reconnect to the database.",
    ),
    (
        re.compile(r"timeout|timed out|504|ReadTimeout|request timed out", re.IGNORECASE),
        "Timeout",
        "The query or the AI API took too long to respond.",
        "The NVIDIA free tier can be slow under load. Try again in a few moments or simplify your question.",
    ),
    (
        re.compile(r"DivisionByZero|division by zero", re.IGNORECASE),
        "Division by Zero",
        "The generated SQL attempted to divide by zero during calculation.",
        "Try rephrasing your question to avoid calculations that may produce zero denominators.",
    ),
    (
        re.compile(r"DataError|invalid input syntax|numeric value out of range", re.IGNORECASE),
        "Data Type Error",
        "The generated SQL uses a value with the wrong data type for the target column.",
        "Try being more specific about the data you're querying (e.g., use quotes around text values).",
    ),
    (
        re.compile(r"Blocked statement|not permitted|blocked keyword|SQL execution blocked", re.IGNORECASE),
        "Blocked Query",
        "The generated SQL contains a statement that is not permitted (e.g., DROP, DELETE, UPDATE).",
        "Only read-only SELECT queries are allowed. Rephrase your question to request data retrieval only.",
    ),
]


def _classify_error(raw_result: str) -> tuple[str, str, str, str]:
    """
    Classify a raw error string into a user-friendly representation.

    Returns:
        (category, friendly_message, suggestion, technical_detail)
    """
    # Strip the leading emoji prefix for the technical detail
    technical = raw_result
    for prefix in ("❌ ", "🚫 ", "⚠️ "):
        if technical.startswith(prefix):
            technical = technical[len(prefix):]
            break

    for pattern, category, friendly, suggestion in _ERROR_PATTERNS:
        if pattern.search(raw_result):
            return category, friendly, suggestion, technical

    # Fallback for unrecognized errors
    return (
        "Execution Error",
        "The generated SQL query could not be executed.",
        "Try rephrasing your question or click **Regenerate SQL** below.",
        technical,
    )


# ── SQL Pre-Validation ────────────────────────────────────────────────────────

def _validate_sql_structure(sql: str) -> str | None:
    """
    Lightweight structural validation on generated SQL.
    Returns a warning message if issues are found, or None if OK.
    Does NOT prevent execution — just flags potential problems.
    """
    if not sql or sql.strip().upper() == "NONE":
        return None

    upper = sql.upper().strip()
    warnings_list = []

    # Detect incomplete WHERE (e.g. "WHERE" at end with nothing after)
    if re.search(r'\bWHERE\s*$', upper):
        warnings_list.append("Incomplete WHERE clause detected.")

    # Detect duplicated JOINs on the same table
    join_tables = re.findall(r'\bJOIN\s+(\w+)', upper)
    seen = set()
    for t in join_tables:
        if t in seen:
            warnings_list.append(f"Duplicate JOIN on table `{t}` detected.")
        seen.add(t)

    # Detect ON without a condition
    if re.search(r'\bON\s*(WHERE|GROUP|ORDER|LIMIT|;|\s*$)', upper):
        warnings_list.append("Malformed JOIN — ON clause has no condition.")

    # Detect SELECT without FROM (unless it's a function-only query like SELECT NOW())
    if upper.startswith("SELECT") and "FROM" not in upper:
        # Allow simple function calls like SELECT CURRENT_DATE, SELECT 1+1
        if re.search(r'SELECT\s+\w+\s*\(', upper) or re.search(r'SELECT\s+\d', upper):
            pass
        elif re.search(r'SELECT\s+CURRENT_', upper):
            pass
        else:
            warnings_list.append("SELECT without FROM — query may be incomplete.")

    if warnings_list:
        return " ".join(warnings_list)
    return None


# ── Result → DataFrame Helper ─────────────────────────────────────────────────

def _sql_result_to_dataframe(sql: str, db) -> pd.DataFrame | None:
    """
    Re-execute a read-only SQL query via pd.read_sql() against the
    SQLAlchemy engine embedded in the LangChain SQLDatabase object.

    Returns None on any failure (the caller falls back to raw text).
    """
    if not sql or sql.strip().upper() == "NONE":
        return None

    try:
        engine = db._engine
        df = pd.read_sql(sql, engine)
        return df
    except Exception as exc:
        logger.debug("pd.read_sql fallback failed: %s", exc)
        return None


# ── Run Query Helper (for retry) ──────────────────────────────────────────────

def _run_ask(question: str, db, use_few_shot: bool):
    """
    Execute the ask() pipeline and store the result in session state.
    Used by both the main Run button and the Retry button.
    """
    try:
        output = ask(
            question=question,
            db=db,
            use_few_shot=use_few_shot,
        )
        st.session_state.current_result = output
        st.session_state.history.append(output)

        # Log errors internally with full detail
        if output["result"].startswith(("❌", "🚫")):
            logger.warning(
                "SQL error for question='%s' | sql='%s' | error='%s'",
                question[:80], output["sql"][:200], output["result"][:300],
            )

    except Exception as e:
        err_str = str(e)
        logger.error("ask() raised an exception: %s", err_str)

        if any(t in err_str for t in ["Timeout", "timeout", "504", "timed out", "Request timed out"]):
            st.warning(
                "The NVIDIA AI API is taking too long to respond (free tier can be slow). "
                "Please try again in a few moments — or try a simpler question first."
            )
        else:
            st.error(f"Something went wrong: {e}")


# ── Session State ──────────────────────────────────────────────────────────────
for key, default in [
    ("db", None), ("db_connected", False),
    ("history", []), ("current_result", None),
    ("retry_pending", False),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<p class="sidebar-label">Connection</p>', unsafe_allow_html=True)

    if not st.session_state.db_connected:
        if st.button("🔌 Connect to Database"):
            with st.spinner("Connecting..."):
                try:
                    st.session_state.db = get_db()
                    st.session_state.db_connected = True
                    st.rerun()
                except Exception as e:
                    st.error(f"Connection failed: {e}")
    else:
        st.markdown('<span class="badge-success">● Connected</span>', unsafe_allow_html=True)
        st.markdown("")

        try:
            tables = st.session_state.db.get_usable_table_names()
            if tables:
                st.markdown('<p class="sidebar-label" style="margin-top:1rem;">Tables</p>', unsafe_allow_html=True)
                for table in tables:
                    st.markdown(f"`{table}`")
        except Exception:
            pass

        st.markdown("---")
        if st.button("🔌 Disconnect"):
            st.session_state.db = None
            st.session_state.db_connected = False
            st.session_state.history = []
            st.session_state.current_result = None
            st.rerun()

    st.markdown("---")
    st.markdown('<p class="sidebar-label">Settings</p>', unsafe_allow_html=True)
    use_few_shot = st.checkbox("Use few-shot examples", value=False,
                               help="Adds example Q&A pairs to the prompt for better accuracy.")
    show_sql = st.checkbox("Always show SQL", value=True,
                           help="Display the generated SQL query alongside the result.")

    st.markdown("---")
    if st.session_state.history:
        st.markdown('<p class="sidebar-label">History</p>', unsafe_allow_html=True)
        for item in reversed(st.session_state.history[-8:]):
            truncated = item["question"][:45] + "..." if len(item["question"]) > 45 else item["question"]
            safe_q = html.escape(truncated)
            st.markdown(f'<div class="history-item">↗ {safe_q}</div>', unsafe_allow_html=True)

        if st.button("🗑 Clear History"):
            st.session_state.history = []
            st.session_state.current_result = None
            st.rerun()

    st.markdown("---")
    st.markdown(
        '<p style="font-size:.75rem;color:#334155;font-family:JetBrains Mono,monospace;">'
        'Qwen 3 Coder · 480B<br>NVIDIA NIM Free Tier</p>',
        unsafe_allow_html=True,
    )

# ── Main Area ──────────────────────────────────────────────────────────────────
st.markdown("""
<div class="app-header">
    <h1 class="app-title">AI SQL Assistant</h1>
    <p class="app-subtitle">natural language → postgresql · powered by mistral large 3</p>
</div>
""", unsafe_allow_html=True)

if not st.session_state.db_connected:
    st.info("👈 Connect to your database using the sidebar to get started.")
    st.stop()

question = st.text_area(
    "Ask a question about your data",
    placeholder="e.g. Who was the top run scorer for CSK in IPL 2025?",
    height=100,
    label_visibility="collapsed",
)

col1, col2, _ = st.columns([2, 1, 1])
with col1:
    run_btn = st.button("⚡ Generate & Run SQL")
with col2:
    if st.button("✕ Clear"):
        st.session_state.current_result = None
        st.session_state.retry_pending = False
        st.rerun()

# ── Run the chain ──────────────────────────────────────────────────────────────
if run_btn:
    if not question.strip():
        st.warning("Please enter a question first.")
    else:
        with st.spinner("Thinking..."):
            _run_ask(question.strip(), st.session_state.db, use_few_shot)

# ── Handle Retry ───────────────────────────────────────────────────────────────
if st.session_state.retry_pending:
    st.session_state.retry_pending = False
    prev = st.session_state.current_result
    if prev:
        with st.spinner("Regenerating SQL..."):
            _run_ask(prev["question"], st.session_state.db, use_few_shot)

# ── Display Results ────────────────────────────────────────────────────────────
if st.session_state.current_result:
    output = st.session_state.current_result
    raw_result = output["result"]
    sql_text = output["sql"]

    st.markdown("---")

    # Classify the result
    is_error = raw_result.startswith(("❌", "🚫"))
    is_warn  = raw_result.startswith("⚠️")

    # Re-execute via pd.read_sql for proper DataFrame (display only)
    df = None
    if not is_error and not is_warn and st.session_state.db is not None:
        df = _sql_result_to_dataframe(sql_text, st.session_state.db)

    # SQL structural validation warning (shown above the panels)
    if not is_error and not is_warn:
        validation_msg = _validate_sql_structure(sql_text)
        if validation_msg:
            st.warning(f"⚠ SQL structure warning: {validation_msg}")

    # ── Two-column layout ──────────────────────────────────────────────────
    # Always show SQL when there's an error (user needs to see what went wrong)
    show_left = show_sql or sql_text == "None" or is_error
    if show_left:
        left_col, right_col = st.columns(2, gap="medium")
    else:
        left_col = None
        right_col = st.container()

    # ── Left: Generated SQL ────────────────────────────────────────────────
    if left_col is not None:
        with left_col:
            st.markdown(
                '<div class="panel-label"><span class="icon">⚡</span> Generated SQL</div>',
                unsafe_allow_html=True,
            )
            st.code(sql_text, language="sql")

    # ── Right: Result ──────────────────────────────────────────────────────
    with right_col:
        st.markdown(
            '<div class="panel-label"><span class="icon">📊</span> Result</div>',
            unsafe_allow_html=True,
        )

        # ── Error state ────────────────────────────────────────────────
        if is_error:
            category, friendly, suggestion, technical = _classify_error(raw_result)

            # Status badges
            st.markdown(
                f'<div class="status-bar">'
                f'<span class="badge-error">✕ Error</span>'
                f'<span class="badge-category">{html.escape(category)}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

            # Friendly message
            st.error(f"**{friendly}**")
            st.caption(f"💡 {suggestion}")

            # Collapsible technical details
            with st.expander("Show Technical Details"):
                st.markdown("**PostgreSQL / SQLAlchemy Error:**")
                st.code(technical, language="text")
                if sql_text and sql_text != "None":
                    st.markdown("**Generated SQL:**")
                    st.code(sql_text, language="sql")

            # Retry button
            if st.button("🔄 Regenerate SQL", key="retry_btn"):
                st.session_state.retry_pending = True
                st.rerun()

        # ── Warning / out-of-scope ─────────────────────────────────────
        elif is_warn:
            st.markdown(
                '<div class="status-bar">'
                '<span class="badge-empty">⚠ Out of Scope</span>'
                '</div>',
                unsafe_allow_html=True,
            )
            st.warning(raw_result)

            if st.button("🔄 Regenerate SQL", key="retry_warn_btn"):
                st.session_state.retry_pending = True
                st.rerun()

        # ── DataFrame with rows ────────────────────────────────────────
        elif df is not None and not df.empty:
            row_count = len(df)
            col_count = len(df.columns)
            st.markdown(
                f'<div class="status-bar">'
                f'<span class="badge-success">✓ Success</span>'
                f'<span class="badge-rows">{row_count} Row{"s" if row_count != 1 else ""}'
                f' · {col_count} Column{"s" if col_count != 1 else ""}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
            st.dataframe(
                df,
                hide_index=True,
                height=min(38 * (row_count + 1) + 2, 500),
            )

        # ── Empty DataFrame (0 rows) ──────────────────────────────────
        elif df is not None and df.empty:
            st.markdown(
                '<div class="status-bar">'
                '<span class="badge-success">✓ Success</span>'
                '<span class="badge-empty">0 Rows Returned</span>'
                '</div>',
                unsafe_allow_html=True,
            )
            st.info("Query executed successfully. No rows returned.")

        # ── Fallback: raw text (pd.read_sql failed) ───────────────────
        else:
            st.markdown(
                '<div class="status-bar">'
                '<span class="badge-success">✓ Success</span>'
                '</div>',
                unsafe_allow_html=True,
            )
            st.text(raw_result)