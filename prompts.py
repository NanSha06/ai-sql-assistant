from langchain_core.prompts import PromptTemplate


# ── System Prompt ──────────────────────────────────────────────────────────────
# Instructs Mistral Large 3 to act as a SQL expert.
# Now accepts optional RAG context block injected between schema and rules.

SYSTEM_PROMPT = """You are an expert SQL assistant. Your job is to help users query a PostgreSQL database by converting their plain English questions into accurate SQL queries.

You will be given:
- The database schema (table names, column names, data types, and relationships)
- Optional business context: relevant table descriptions, business definitions, and KPI definitions retrieved from a knowledge base
- A question (may be in any language — always generate SQL in standard PostgreSQL)

Your rules:
1. Return ONLY the SQL query — no explanations, no markdown, no code fences, no preamble.
2. Always use correct PostgreSQL syntax.
3. Never use DROP, DELETE, INSERT, UPDATE, ALTER, TRUNCATE or any other destructive or data-modifying statements. SELECT queries only.
4. If the question cannot be answered from the given schema, respond with exactly: None
5. Use table aliases for readability in complex queries.
6. Always qualify column names with table aliases when joining multiple tables.
7. Use LIMIT 100 by default unless the user specifies a different number.
8. Use ILIKE instead of LIKE for case-insensitive string matching in PostgreSQL.
9. Use the business context section to resolve business terms (e.g. "revenue", "MAU") into correct SQL expressions.

Schema:
{schema}
"""


# ── User Prompt Template (with RAG context slot) ───────────────────────────────
# rag_context is optional — empty string if RAG is unavailable or not yet indexed.

SQL_PROMPT_TEMPLATE = PromptTemplate(
    input_variables=["schema", "question", "rag_context"],
    template="""Based on the PostgreSQL database schema below, write a SQL query to answer the user's question.

Schema:
{schema}

{rag_context}

Rules:
- Return ONLY the raw SQL query.
- No explanations, no markdown, no code fences.
- SELECT queries only — never modify the database.
- If the question is out of scope or cannot be answered from the schema, return exactly: None
- The question may be in any language — always generate SQL in standard PostgreSQL.

Question: {question}

SQL Query:"""
)


# ── Few-Shot Examples (optional context booster) ───────────────────────────────

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


def build_prompt(
    schema: str,
    question: str,
    use_few_shot: bool = False,
    rag_context: str = "",
) -> str:
    """
    Build the final prompt string to send to the LLM.

    Args:
        schema:       DDL schema string from get_schema() in db.py
        question:     User's plain English question (any language)
        use_few_shot: Whether to include few-shot examples in the prompt
        rag_context:  Retrieved RAG context block from context_builder.py
                      (empty string if RAG unavailable — graceful degradation)

    Returns:
        Fully formatted prompt string
    """
    few_shot_context = f"\n\n{build_few_shot_context()}\n\n" if use_few_shot else ""

    # Format RAG context block — only shown to LLM if content exists
    rag_block = ""
    if rag_context and rag_context.strip():
        rag_block = f"Business Context (use this to resolve business terms):\n{rag_context}"

    return SQL_PROMPT_TEMPLATE.format(
        schema=schema + few_shot_context,
        question=question,
        rag_context=rag_block,
    )


# ── Quick test ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    sample_schema = """
    CREATE TABLE customers (
        id SERIAL PRIMARY KEY,
        name VARCHAR(100),
        email VARCHAR(100),
        created_at TIMESTAMP
    );

    CREATE TABLE orders (
        id SERIAL PRIMARY KEY,
        customer_id INT REFERENCES customers(id),
        amount DECIMAL(10, 2),
        status VARCHAR(50),
        created_at TIMESTAMP
    );
    """

    sample_rag_context = """### Relevant Tables & Columns
Table: customers — stores customer name, email, created_at

### Business Definitions
Revenue — total value of all completed orders (status='completed')"""

    sample_question = "Show top 10 customers by revenue"

    print("=== Prompt WITHOUT RAG context ===\n")
    print(build_prompt(sample_schema, sample_question))

    print("\n=== Prompt WITH RAG context ===\n")
    print(build_prompt(sample_schema, sample_question, rag_context=sample_rag_context))

    print("\n=== Prompt WITH RAG + few-shot ===\n")
    print(build_prompt(sample_schema, sample_question, use_few_shot=True, rag_context=sample_rag_context))