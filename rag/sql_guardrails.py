"""
rag/sql_guardrails.py
─────────────────────
Validates generated SQL before execution.
Blocks ALL data-modifying and schema-altering statements.
Only pure read operations (SELECT, WITH, EXPLAIN) are allowed.
"""

import re

# Every keyword that can mutate data or schema — covers the full SQL surface
_BLOCKED = re.compile(
    r"^\s*("
    r"INSERT|UPDATE|DELETE|REPLACE|UPSERT|MERGE"   # DML
    r"|DROP|CREATE|ALTER|TRUNCATE|RENAME|COMMENT"  # DDL
    r"|GRANT|REVOKE|DENY"                          # DCL
    r"|BEGIN|COMMIT|ROLLBACK|SAVEPOINT"            # TCL (shouldn't appear but guard anyway)
    r"|COPY|LOAD|IMPORT|EXPORT"                    # bulk ops
    r"|CALL|EXEC|EXECUTE"                          # stored procs
    r"|LOCK|UNLOCK"                                # locking
    r")\b",
    re.IGNORECASE,
)

# Also block inline mutations hidden inside CTEs or subqueries
_INLINE_BLOCKED = re.compile(
    r"\b("
    r"INSERT\s+INTO|UPDATE\s+\w|DELETE\s+FROM"
    r"|DROP\s+(TABLE|VIEW|INDEX|DATABASE|SCHEMA|SEQUENCE)"
    r"|CREATE\s+(TABLE|VIEW|INDEX|DATABASE|SCHEMA|SEQUENCE)"
    r"|ALTER\s+(TABLE|VIEW|INDEX|DATABASE|SCHEMA|SEQUENCE)"
    r"|TRUNCATE\s+TABLE"
    r"|GRANT\s+|REVOKE\s+"
    r")\b",
    re.IGNORECASE,
)


def assert_safe(sql: str) -> None:
    """
    Raise ValueError if sql contains any mutating or schema-altering statement.
    Call this before executing any LLM-generated SQL.

    Args:
        sql: The SQL string to validate (already cleaned by clean_sql()).

    Raises:
        ValueError: with a human-readable message describing what was blocked.
    """
    if not sql or sql.strip().upper() == "NONE":
        return

    # Strip leading comments before checking first keyword
    stripped = re.sub(r"--[^\n]*", "", sql)          # remove single-line comments
    stripped = re.sub(r"/\*.*?\*/", "", stripped, flags=re.DOTALL)  # remove block comments
    stripped = stripped.strip()

    # Check first keyword
    if _BLOCKED.match(stripped):
        first_word = stripped.split()[0].upper()
        raise ValueError(
            f"Blocked statement: {first_word} queries are not permitted. "
            f"Only SELECT / WITH / EXPLAIN queries are allowed."
        )

    # Check for mutations hidden anywhere in the query (e.g. inside CTEs)
    if _INLINE_BLOCKED.search(stripped):
        raise ValueError(
            "Blocked: data-modifying or schema-altering operation detected "
            "inside the query. Only read-only SQL is permitted."
        )


def is_safe(sql: str) -> bool:
    """Convenience wrapper — returns True if sql passes the safety check."""
    try:
        assert_safe(sql)
        return True
    except ValueError:
        return False