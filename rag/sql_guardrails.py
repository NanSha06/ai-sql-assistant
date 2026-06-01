"""
rag/sql_guardrails.py
---------------------
SQL safety validation layer.

Blocks dangerous write/destructive SQL statements before execution.
Allows all read-only analytical queries through untouched.

Per instructions.md:
- Block: DROP, DELETE, TRUNCATE, ALTER, UPDATE (unless explicitly enabled)
- Allow: SELECT, WITH, aggregations, analytical queries
- Must NOT modify valid SELECT queries
- Must NOT interfere with normal SQL execution flow

Usage:
    from rag.sql_guardrails import validate_sql, SQLValidationResult

    result = validate_sql("SELECT * FROM orders")
    if result.is_safe:
        run_query(result.sql)
    else:
        print(result.reason)
"""

import logging
import os
import re
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

# Load blocked keywords from .env, fallback to safe defaults
_raw_blocked = os.getenv("SQL_BLOCKED_KEYWORDS", "DROP,DELETE,TRUNCATE,ALTER,UPDATE")
BLOCKED_KEYWORDS: list[str] = [k.strip().upper() for k in _raw_blocked.split(",") if k.strip()]

# Master kill switch — set SQL_ALLOW_WRITES=true ONLY in controlled environments
SQL_ALLOW_WRITES: bool = os.getenv("SQL_ALLOW_WRITES", "false").lower() == "true"


# ── Result dataclass ───────────────────────────────────────────────────────────

@dataclass
class SQLValidationResult:
    """
    Result of a SQL safety validation check.

    Attributes:
        is_safe:  True if SQL is safe to execute.
        sql:      The original SQL string (never modified).
        blocked_keyword: The keyword that triggered the block (None if safe).
        reason:   Human-readable explanation.
    """
    is_safe:         bool
    sql:             str
    blocked_keyword: str | None
    reason:          str

    def __str__(self) -> str:
        status = "✅ SAFE" if self.is_safe else "🚫 BLOCKED"
        return f"{status} | {self.reason}"


# ── Core validation ────────────────────────────────────────────────────────────

def validate_sql(sql: str) -> SQLValidationResult:
    """
    Validate a SQL string against the safety ruleset.

    Rules (in order):
    1. Empty input → blocked
    2. SQL_ALLOW_WRITES=true → everything passes (bypass mode)
    3. Tokenize SQL and check each token against BLOCKED_KEYWORDS
       Uses word-boundary matching to avoid false positives
       (e.g. "updated_at" column should not trigger UPDATE block)
    4. All SELECT / WITH / analytical queries → safe

    IMPORTANT: This function NEVER modifies the SQL string.
    It only decides whether to allow or block execution.

    Args:
        sql: SQL string to validate.

    Returns:
        SQLValidationResult with is_safe flag and reason.
    """
    if not sql or not sql.strip():
        return SQLValidationResult(
            is_safe=False,
            sql=sql,
            blocked_keyword=None,
            reason="Empty SQL string.",
        )

    # ── Bypass mode ───────────────────────────────────────────────────────────
    if SQL_ALLOW_WRITES:
        logger.warning(
            "⚠️  SQL_ALLOW_WRITES=true — safety checks bypassed. "
            "Do NOT use in production."
        )
        return SQLValidationResult(
            is_safe=True,
            sql=sql,
            blocked_keyword=None,
            reason="Write operations enabled via SQL_ALLOW_WRITES=true.",
        )

    # ── Keyword detection ─────────────────────────────────────────────────────
    # Strip comments before checking — prevents hiding DROP inside a comment
    clean_sql = _strip_comments(sql)

    for keyword in BLOCKED_KEYWORDS:
        # Word-boundary regex: matches "DROP" but not "DROPDOWN" or "updated_at"
        pattern = rf"\b{re.escape(keyword)}\b"
        if re.search(pattern, clean_sql, re.IGNORECASE):
            reason = (
                f"Blocked keyword detected: '{keyword}'. "
                f"Only read-only SELECT queries are permitted. "
                f"Set SQL_ALLOW_WRITES=true to enable write operations."
            )
            logger.warning("🚫 SQL blocked — keyword: '%s' | SQL: %s", keyword, sql[:120])
            return SQLValidationResult(
                is_safe=False,
                sql=sql,
                blocked_keyword=keyword,
                reason=reason,
            )

    # ── Passed all checks ─────────────────────────────────────────────────────
    logger.debug("✅ SQL passed validation: %s", sql[:120])
    return SQLValidationResult(
        is_safe=True,
        sql=sql,
        blocked_keyword=None,
        reason="Query is read-only and safe to execute.",
    )


# ── Comment stripping ──────────────────────────────────────────────────────────

def _strip_comments(sql: str) -> str:
    """
    Remove SQL comments before keyword scanning.

    Handles:
    - Single-line comments: -- comment
    - Multi-line comments:  /* comment */

    This prevents hiding dangerous keywords inside comments like:
        SELECT 1 -- DROP TABLE users

    Args:
        sql: Raw SQL string.

    Returns:
        SQL with comments removed.
    """
    # Remove multi-line comments /* ... */
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    # Remove single-line comments -- ...
    sql = re.sub(r"--[^\n]*", " ", sql)
    return sql.strip()


# ── Convenience helpers ────────────────────────────────────────────────────────

def is_safe(sql: str) -> bool:
    """Quick boolean check — returns True if SQL is safe to execute."""
    return validate_sql(sql).is_safe


def assert_safe(sql: str) -> str:
    """
    Validate SQL and return it if safe, raise ValueError if blocked.

    Use in chain.py as a guard before run_query():

        sql = assert_safe(generated_sql)
        result = run_query(sql, db)

    Args:
        sql: SQL string to validate.

    Returns:
        The original SQL string if safe.

    Raises:
        ValueError: With a user-friendly message if SQL is blocked.
    """
    result = validate_sql(sql)
    if not result.is_safe:
        raise ValueError(f"🚫 SQL execution blocked: {result.reason}")
    return sql


# ── Quick test ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print(f"Blocked keywords : {BLOCKED_KEYWORDS}")
    print(f"Allow writes     : {SQL_ALLOW_WRITES}")
    print()

    test_cases = [
        # (description, sql, expected_safe)
        ("Simple SELECT",
         "SELECT * FROM orders",
         True),

        ("SELECT with WHERE",
         "SELECT customer_id, SUM(amount) FROM orders WHERE status = 'completed' GROUP BY customer_id",
         True),

        ("CTE / WITH",
         "WITH ranked AS (SELECT *, ROW_NUMBER() OVER (ORDER BY amount DESC) AS rn FROM orders) SELECT * FROM ranked WHERE rn <= 10",
         True),

        ("Subquery",
         "SELECT name FROM customers WHERE customer_id IN (SELECT customer_id FROM orders GROUP BY customer_id HAVING SUM(amount) > 1000)",
         True),

        ("Column named updated_at (false positive guard)",
         "SELECT customer_id, updated_at FROM customers ORDER BY updated_at DESC",
         True),

        ("Column named drop_reason (false positive guard)",
         "SELECT id, drop_reason FROM events WHERE drop_reason IS NOT NULL",
         True),

        ("DROP TABLE",
         "DROP TABLE users",
         False),

        ("DELETE",
         "DELETE FROM orders WHERE status = 'pending'",
         False),

        ("TRUNCATE",
         "TRUNCATE TABLE logs",
         False),

        ("ALTER TABLE",
         "ALTER TABLE customers ADD COLUMN phone VARCHAR(20)",
         False),

        ("UPDATE",
         "UPDATE orders SET status = 'cancelled' WHERE order_id = 1",
         False),

        ("DROP hidden in comment — executes as SELECT 1, so SAFE",
         "SELECT 1 -- DROP TABLE users",
         True),

        ("DROP in multiline comment — executes as SELECT 1 FROM orders, so SAFE",
         "SELECT 1 /* DROP TABLE users */ FROM orders",
         True),

        ("Empty SQL",
         "",
         False),
    ]

    passed = 0
    failed = 0

    print(f"{'#':<3} {'Description':<42} {'Expected':<10} {'Got':<10} {'Status'}")
    print("-" * 85)

    for i, (desc, sql, expected) in enumerate(test_cases, 1):
        result  = validate_sql(sql)
        got     = result.is_safe
        status  = "✅ PASS" if got == expected else "❌ FAIL"

        if got == expected:
            passed += 1
        else:
            failed += 1

        print(
            f"{i:<3} {desc:<42} "
            f"{'SAFE' if expected else 'BLOCK':<10} "
            f"{'SAFE' if got else 'BLOCK':<10} "
            f"{status}"
        )
        if got != expected:
            print(f"     Reason: {result.reason}")

    print(f"\nResults: {passed}/{len(test_cases)} passed", end="")
    print(" ✅" if failed == 0 else f"  ❌ {failed} failed")