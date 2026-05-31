from langchain_core.prompts import PromptTemplate


# ── System Prompt ──────────────────────────────────────────────────────────────
# Instructs Mistral Large 3 to act as a SQL expert.
# Injected once when the agent is initialized.

SYSTEM_PROMPT = """You are an expert SQL assistant. Your job is to help users query a PostgreSQL database by converting their plain English questions into accurate SQL queries.

You will be given:
- The database schema (table names, column names, data types, and relationships)
- A question in plain English

Your rules:
1. Return ONLY the SQL query — no explanations, no markdown, no code fences, no preamble.
2. Always use correct PostgreSQL syntax.
3. Never use DROP, DELETE, INSERT, UPDATE, ALTER, TRUNCATE or any other destructive or data-modifying statements. SELECT queries only.
4. If the question cannot be answered from the given schema, respond with exactly: None
5. Use table aliases for readability in complex queries.
6. Always qualify column names with table aliases when joining multiple tables.
7. Use LIMIT 100 by default unless the user specifies a different number.
8. Use ILIKE instead of LIKE for case-insensitive string matching in PostgreSQL.

Schema:
{schema}
"""


# ── User Prompt Template ───────────────────────────────────────────────────────
# This is the per-question prompt sent for each user query.

SQL_PROMPT_TEMPLATE = PromptTemplate(
    input_variables=["schema", "question"],
    template="""Based on the PostgreSQL database schema below, write a SQL query to answer the user's question.

Schema:
{schema}

Rules:
- Return ONLY the raw SQL query.
- No explanations, no markdown, no code fences.
- SELECT queries only — never modify the database.
- If the question is out of scope or cannot be answered from the schema, return exactly: None

Question: {question}

SQL Query:"""
)


# ── Few-Shot Examples (optional context booster) ───────────────────────────────
# These examples help Mistral understand the expected input/output format.

FEW_SHOT_EXAMPLES = [
    {
        "question": "How many users are in the database?",
        "sql": "SELECT COUNT(*) AS total_users FROM users;"
    },
    {
        "question": "Show me the top 5 most expensive products.",
        "sql": "SELECT product_name, price FROM products ORDER BY price DESC LIMIT 5;"
    },
    {
        "question": "List all orders placed in the last 30 days.",
        "sql": "SELECT * FROM orders WHERE created_at >= NOW() - INTERVAL '30 days' LIMIT 100;"
    },
    {
        "question": "What is the total revenue from completed orders?",
        "sql": "SELECT SUM(total_amount) AS total_revenue FROM orders WHERE status = 'completed';"
    },
    {
        "question": "Show all users who have never placed an order.",
        "sql": """SELECT u.id, u.name, u.email
FROM users u
LEFT JOIN orders o ON u.id = o.user_id
WHERE o.id IS NULL
LIMIT 100;"""
    }
]


def build_few_shot_context() -> str:
    """
    Formats few-shot examples into a readable string
    to optionally append to the prompt for better model guidance.
    """
    context = "Here are some example questions and their correct SQL queries:\n\n"
    for i, example in enumerate(FEW_SHOT_EXAMPLES, 1):
        context += f"Example {i}:\n"
        context += f"Question: {example['question']}\n"
        context += f"SQL: {example['sql']}\n\n"
    return context.strip()


def build_prompt(schema: str, question: str, use_few_shot: bool = False) -> str:
    """
    Build the final prompt string to send to the LLM.

    Args:
        schema:       DDL schema string from get_schema() in db.py
        question:     User's plain English question
        use_few_shot: Whether to include few-shot examples in the prompt

    Returns:
        Fully formatted prompt string
    """
    few_shot_context = f"\n\n{build_few_shot_context()}\n\n" if use_few_shot else ""

    return SQL_PROMPT_TEMPLATE.format(
        schema=schema + few_shot_context,
        question=question
    )


# ── Quick test ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    sample_schema = """
    CREATE TABLE users (
        id SERIAL PRIMARY KEY,
        name VARCHAR(100),
        email VARCHAR(100),
        created_at TIMESTAMP
    );

    CREATE TABLE orders (
        id SERIAL PRIMARY KEY,
        user_id INT REFERENCES users(id),
        total_amount DECIMAL(10, 2),
        status VARCHAR(50),
        created_at TIMESTAMP
    );
    """

    sample_question = "How many users signed up last month?"

    print("=== Prompt WITHOUT few-shot examples ===\n")
    print(build_prompt(sample_schema, sample_question, use_few_shot=False))

    print("\n=== Prompt WITH few-shot examples ===\n")
    print(build_prompt(sample_schema, sample_question, use_few_shot=True))