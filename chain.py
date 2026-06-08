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

# ── LLM Setup (cached — one instance for the lifetime of the process) ─────────

_llm_instance = None

def get_llm() -> ChatOpenAI:
    """
    Return a cached ChatOpenAI instance via NVIDIA NIM.
    Never re-initialised per request — avoids repeated handshake overhead.
    timeout=30 ensures a hung NIM call fails fast instead of spinning forever.
    """
    global _llm_instance
    if _llm_instance is not None:
        return _llm_instance

    api_key = os.getenv("NVIDIA_API_KEY")
    if not api_key:
        raise ValueError("❌ NVIDIA_API_KEY is missing from your .env file.")

    _llm_instance = ChatOpenAI(
        model=os.getenv("LLM_MODEL", "qwen/qwen3-coder-480b-a35b-instruct"),
        api_key=api_key,
        base_url=os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1"),
        temperature=0,
        timeout=120,   # 675B model on free tier can be slow — 60s before giving up
    )
    return _llm_instance


# ── SQL Cleaner ────────────────────────────────────────────────────────────────

def clean_sql(raw: str) -> str:
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
    llm = get_llm()
    user_prompt = build_prompt(schema, question, use_few_shot=use_few_shot, rag_context=rag_context)
    messages = [
        SystemMessage(content=SYSTEM_PROMPT.format(schema=schema)),
        HumanMessage(content=user_prompt),
    ]
    response = llm.invoke(messages)
    return clean_sql(response.content)


def run_query(sql: str, db) -> str:
    if sql == "None":
        return "⚠️ This question could not be answered from the available schema."

    try:
        assert_safe(sql)
    except ValueError as e:
        return f"🚫 {e}"

    try:
        result = db.run(sql)
        if not result or result.strip() == "":
            return "✅ Query ran successfully but returned no results."
        return result
    except Exception as e:
        return f"❌ Query execution failed: {e}"


def ask(question: str, db=None, use_few_shot: bool = False) -> dict:
    if db is None:
        db = get_db()

    schema = get_schema(db)
    rag_context_str, retrieval = get_rag_context(question)
    sql = generate_sql(question, schema, use_few_shot=use_few_shot, rag_context=rag_context_str)
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
    try:
        db = get_db()
        for question in ["How many tables are in the database?", "What is the current date?"]:
            print(f"❓ Question : {question}")
            output = ask(question, db=db)
            print(f"🌐 Language : {output['language']}")
            print(f"📚 RAG chunks: {output['rag_chunks']}")
            print(f"🧠 SQL      : {output['sql']}")
            print(f"📊 Result   : {output['result']}")
            print("-" * 50)
    except Exception as e:
        print(f"❌ Error: {e}")