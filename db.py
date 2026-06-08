import os
import warnings
from urllib.parse import quote_plus
from dotenv import load_dotenv

warnings.filterwarnings("ignore", category=DeprecationWarning, module="langchain_community")

from langchain_community.utilities import SQLDatabase
from sqlalchemy.engine import URL

load_dotenv()


def get_db_url() -> str:
    """
    Build a PostgreSQL connection URL from environment variables.
    Uses SQLAlchemy URL.create() so special characters in passwords
    (e.g. @, :, /, #, spaces) are safely percent-encoded and never
    break URL parsing.
    """
    host     = os.getenv("DB_HOST")
    port     = os.getenv("DB_PORT", "5432")
    name     = os.getenv("DB_NAME")
    user     = os.getenv("DB_USER")
    password = os.getenv("DB_PASS", "")

    missing = [k for k, v in {"DB_HOST": host, "DB_NAME": name, "DB_USER": user}.items() if not v]
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

    url = URL.create(
        drivername="postgresql+psycopg2",
        username=user,
        password=password,   # SQLAlchemy handles encoding internally
        host=host,
        port=int(port),
        database=name,
    )
    return url.render_as_string(hide_password=False)


def get_db(include_tables: list = None) -> SQLDatabase:
    """
    Connect to PostgreSQL and return a LangChain SQLDatabase instance.

    Args:
        include_tables: Optional list of table names to expose to the agent.

    Returns:
        SQLDatabase instance.
    """
    db_url = get_db_url()

    try:
        db = SQLDatabase.from_uri(
            db_url,
            include_tables=include_tables if include_tables else None,
        )
        print("[SUCCESS] Connected to database successfully.")
        print(f"[INFO] Available tables: {db.get_usable_table_names()}")
        return db
    except Exception as e:
        raise ConnectionError(f"❌ Failed to connect to the database: {e}")


def get_schema(db: SQLDatabase) -> str:
    """Extract and return the DDL schema from the database."""
    return db.get_table_info()


# ── Quick connection test ──────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Testing database connection...\n")
    try:
        db = get_db()
        schema = get_schema(db)
        print("\n📄 Schema Preview:\n")
        print(schema[:1000], "..." if len(schema) > 1000 else "")
    except Exception as e:
        print(e)