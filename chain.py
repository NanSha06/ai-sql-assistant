import os
import warnings
import re

warnings.filterwarnings("ignore", category=DeprecationWarning, module="langchain_community")

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from db import get_db, get_schema
from prompts import build_prompt, SYSTEM_PROMPT

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
        model="mistralai/mistral-large-3-675b-instruct-2512",
        api_key=api_key,
        base_url="https://integrate.api.nvidia.com/v1",
        temperature=0,       # deterministic SQL output
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
    # Remove ```sql ... ``` or ``` ... ``` fences
    cleaned = re.sub(r"```(?:sql)?", "", raw, flags=re.IGNORECASE).replace("```", "")

    # Strip leading/trailing whitespace
    cleaned = cleaned.strip()

    # Normalize "none" responses
    if cleaned.lower() in ("none", "none;", "none."):
        return "None"

    return cleaned


# ── Core Query Function ────────────────────────────────────────────────────────

def generate_sql(question: str, schema: str, use_few_shot: bool = False) -> str:
    """
    Send a natural language question + schema to Mistral and get back SQL.

    Args:
        question:     User's plain English question
        schema:       DDL schema string from get_schema()
        use_few_shot: Whether to include few-shot examples in the prompt

    Returns:
        Clean SQL query string, or 'None' if out of scope
    """
    llm = get_llm()

    user_prompt = build_prompt(schema, question, use_few_shot=use_few_shot)

    messages = [
        SystemMessage(content=SYSTEM_PROMPT.format(schema=schema)),
        HumanMessage(content=user_prompt)
    ]

    response = llm.invoke(messages)
    raw_sql = response.content

    return clean_sql(raw_sql)


def run_query(sql: str, db) -> str:
    """
    Execute a SQL query against the PostgreSQL database.

    Args:
        sql: Clean SQL query string
        db:  SQLDatabase instance from db.py

    Returns:
        Query result as a string, or an error message
    """
    if sql == "None":
        return "⚠️ This question could not be answered from the available schema."

    try:
        result = db.run(sql)
        if not result or result.strip() == "":
            return "✅ Query ran successfully but returned no results."
        return result
    except Exception as e:
        return f"❌ Query execution failed: {e}"


def ask(question: str, db=None, use_few_shot: bool = False) -> dict:
    """
    Full pipeline: question → SQL → execute → result.

    Args:
        question:     User's plain English question
        db:           SQLDatabase instance (created if not provided)
        use_few_shot: Whether to include few-shot examples

    Returns:
        dict with keys: question, sql, result
    """
    if db is None:
        db = get_db()

    schema = get_schema(db)
    sql = generate_sql(question, schema, use_few_shot=use_few_shot)
    result = run_query(sql, db)

    return {
        "question": question,
        "sql": sql,
        "result": result
    }


# ── Quick test ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🔗 Testing full chain...\n")

    test_questions = [
        "How many tables are in the database?",
        "What is the current date?",
    ]

    try:
        db = get_db()

        for question in test_questions:
            print(f"❓ Question: {question}")
            output = ask(question, db=db)
            print(f"🧠 SQL     : {output['sql']}")
            print(f"📊 Result  : {output['result']}")
            print("-" * 50)

    except Exception as e:
        print(f"❌ Error: {e}")