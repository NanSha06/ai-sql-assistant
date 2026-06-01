import os
import warnings
import re

warnings.filterwarnings("ignore", category=DeprecationWarning, module="langchain_community")

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from db import get_db, get_schema
from prompts import build_prompt, SYSTEM_PROMPT
from rag.context_builder import get_rag_context
from rag.sql_guardrails import assert_safe

load_dotenv()


# ── LLM Setup ─────────────────────────────────────────────────────────────────

def get_llm() -> ChatOpenAI:
    """
    Initialize Mistral Large 3 via NVIDIA NIM's OpenAI-compatible API.

    Returns:
        ChatOpenAI instance pointed at NVIDIA NIM endpoint.
    """
    api_key = os.getenv("NVIDIA_API_KEY")
    if not api_key:
        raise ValueError("❌ NVIDIA_API_KEY is missing from your .env file.")

    return ChatOpenAI(
        model=os.getenv("LLM_MODEL", "mistralai/mistral-large-3-675b-instruct-2512"),
        api_key=api_key,
        base_url=os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1"),
        temperature=0,
        top_p=1,
        max_tokens=1000
    )


# ── SQL Cleaner ────────────────────────────────────────────────────────────────

def clean_sql(raw: str) -> str:
    """
    Strip markdown fences, extra whitespace, and noise from LLM output.

    Args:
        raw: Raw string returned by the LLM

    Returns:
        Clean SQL string or 'None' if out of scope
    """
    cleaned = re.sub(r"```(?:sql)?", "", raw, flags=re.IGNORECASE).replace("```", "")
    cleaned = cleaned.strip()

    if cleaned.lower() in ("none", "none;", "none."):
        return "None"

    return cleaned


# ── Core Query Function ────────────────────────────────────────────────────────

def generate_sql(
    question: str,
    schema: str,
    use_few_shot: bool = False,
    rag_context: str = "",
) -> str:
    """
    Send a natural language question + schema + RAG context to Mistral
    and get back a clean SQL query.

    Args:
        question:     User's plain English question (any language)
        schema:       DDL schema string from get_schema()
        use_few_shot: Whether to include few-shot examples in the prompt
        rag_context:  Retrieved business context from context_builder.py

    Returns:
        Clean SQL query string, or 'None' if out of scope
    """
    llm = get_llm()

    user_prompt = build_prompt(
        schema,
        question,
        use_few_shot=use_few_shot,
        rag_context=rag_context,
    )

    messages = [
        SystemMessage(content=SYSTEM_PROMPT.format(schema=schema)),
        HumanMessage(content=user_prompt),
    ]

    response = llm.invoke(messages)
    return clean_sql(response.content)


def run_query(sql: str, db) -> str:
    """
    Validate and execute a SQL query against the PostgreSQL database.

    Runs sql_guardrails check before execution — blocks any destructive
    statements that somehow bypassed the LLM prompt rules.

    Args:
        sql: Clean SQL query string
        db:  SQLDatabase instance from db.py

    Returns:
        Query result as a string, or an error message
    """
    if sql == "None":
        return "⚠️ This question could not be answered from the available schema."

    # ── Safety guard ───────────────────────────────────────────────────────────
    try:
        assert_safe(sql)
    except ValueError as e:
        return f"🚫 {e}"

    # ── Execute ────────────────────────────────────────────────────────────────
    try:
        result = db.run(sql)
        if not result or result.strip() == "":
            return "✅ Query ran successfully but returned no results."
        return result
    except Exception as e:
        return f"❌ Query execution failed: {e}"


def ask(
    question: str,
    db=None,
    use_few_shot: bool = False,
) -> dict:
    """
    Full RAG-enhanced pipeline:
    question → RAG retrieval → SQL generation → safety check → execute → result.

    Args:
        question:     User's plain English question (any language)
        db:           SQLDatabase instance (created if not provided)
        use_few_shot: Whether to include few-shot examples

    Returns:
        dict with keys: question, sql, result, language, rag_chunks
    """
    if db is None:
        db = get_db()

    schema = get_schema(db)

    # ── RAG context retrieval ──────────────────────────────────────────────────
    # Degrades gracefully to "" if vector store is empty or unavailable
    rag_context_str, retrieval = get_rag_context(question)

    # ── SQL generation ─────────────────────────────────────────────────────────
    sql = generate_sql(
        question,
        schema,
        use_few_shot=use_few_shot,
        rag_context=rag_context_str,
    )

    # ── Execution ──────────────────────────────────────────────────────────────
    result = run_query(sql, db)

    return {
        "question":   question,
        "sql":        sql,
        "result":     result,
        "language":   retrieval.language.language_name if retrieval else "English",
        "rag_chunks": retrieval.total if retrieval else 0,
    }


# ── Quick test ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🔗 Testing full RAG-enhanced chain...\n")

    test_questions = [
        "How many tables are in the database?",
        "What is the current date?",
    ]

    try:
        db = get_db()

        for question in test_questions:
            print(f"❓ Question : {question}")
            output = ask(question, db=db)
            print(f"🌐 Language : {output['language']}")
            print(f"📚 RAG chunks: {output['rag_chunks']}")
            print(f"🧠 SQL      : {output['sql']}")
            print(f"📊 Result   : {output['result']}")
            print("-" * 50)

    except Exception as e:
        print(f"❌ Error: {e}")