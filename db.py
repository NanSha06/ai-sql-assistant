import os
import warnings
from dotenv import load_dotenv

# Suppress langchain-community deprecation warning (no standalone replacement yet for SQLDatabase)
warnings.filterwarnings("ignore", category=DeprecationWarning, module="langchain_community")

from langchain_community.utilities import SQLDatabase

# Load environment variables from .env file
load_dotenv()


def get_db_url() -> str:
    """Build PostgreSQL connection URL from environment variables."""
    host = os.getenv("DB_HOST")
    port = os.getenv("DB_PORT")
    name = os.getenv("DB_NAME")
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASS")

    # Check all required env variables are present
    missing = [
        var for var, val in {
            "DB_HOST": host,
            "DB_PORT": port,
            "DB_NAME": name,
            "DB_USER": user,
            "DB_PASS": password
        }.items() if not val
    ]

    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"


def get_db(include_tables: list = None) -> SQLDatabase:
    """
    Connect to PostgreSQL and return a LangChain SQLDatabase instance.

    Args:
        include_tables: Optional list of table names to expose to the agent.
                        If None, all tables are included.
                        Example: ["users", "orders", "products"]

    Returns:
        SQLDatabase instance ready for use with LangChain SQL Agent.
    """
    db_url = get_db_url()

    try:
        if include_tables:
            db = SQLDatabase.from_uri(
                db_url,
                include_tables=include_tables
            )
        else:
            db = SQLDatabase.from_uri(db_url)

        print(f"✅ Connected to database successfully.")
        print(f"📋 Available tables: {db.get_usable_table_names()}")
        return db

    except Exception as e:
        raise ConnectionError(f"❌ Failed to connect to the database: {e}")


def get_schema(db: SQLDatabase) -> str:
    """
    Extract and return the DDL schema from the database.
    Used to inject table definitions into the prompt.

    Args:
        db: SQLDatabase instance

    Returns:
        Schema string with table definitions
    """
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