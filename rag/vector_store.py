"""
rag/vector_store.py
───────────────────
ChromaDB client and collection management.

We never pass embedding_function to get_or_create_collection — we always
supply pre-computed embedding vectors directly when upserting and querying.
This avoids all chromadb embedding-function conflict/version issues.

Public API:
    get_client()      → chromadb.PersistentClient (cached)
    get_collection()  → chromadb.Collection | None
    add_chunks(chunks, ids, metadatas, embeddings)
    reset_collection()
"""

import os
import logging
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

COLLECTION_NAME = "sql_assistant_rag"
DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "vector_db")

_client     = None
_collection = None


def get_client():
    """Return (and cache) a ChromaDB PersistentClient."""
    global _client
    if _client is not None:
        return _client

    try:
        import chromadb  # noqa: PLC0415

        db_path = os.getenv("CHROMA_DB_PATH", DEFAULT_DB_PATH)
        Path(db_path).mkdir(parents=True, exist_ok=True)

        _client = chromadb.PersistentClient(path=db_path)
        logger.info("[INFO] ChromaDB PersistentClient at %s", db_path)
        return _client

    except ImportError:
        logger.warning("chromadb not installed — RAG disabled.")
        return None
    except Exception as exc:
        logger.warning("ChromaDB init failed: %s", exc)
        return None


def get_collection():
    """
    Return (and cache) the RAG collection.
    NO embedding_function is passed — we always provide vectors ourselves.
    Returns None if ChromaDB is unavailable.
    """
    global _collection
    if _collection is not None:
        return _collection

    client = get_client()
    if client is None:
        return None

    try:
        # embedding_function=None tells chromadb we will supply vectors manually
        _collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=None,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            "✅ Collection '%s' ready (%d docs).",
            COLLECTION_NAME,
            _collection.count(),
        )
        return _collection

    except Exception as exc:
        logger.warning("Could not get/create collection: %s", exc)
        return None


def add_chunks(
    chunks:     List[str],
    ids:        List[str],
    metadatas:  List[dict],
    embeddings: List[List[float]],
) -> bool:
    """Upsert chunks with their pre-computed embeddings. Returns True on success."""
    if not chunks:
        logger.warning("add_chunks: empty list.")
        return False
    if not embeddings or len(embeddings) != len(chunks):
        logger.error("add_chunks: embeddings length mismatch.")
        return False

    collection = get_collection()
    if collection is None:
        return False

    try:
        collection.upsert(
            documents=chunks,
            ids=ids,
            metadatas=metadatas,
            embeddings=embeddings,
        )
        logger.info("[INFO] Upserted %d chunks into '%s'.", len(chunks), COLLECTION_NAME)
        return True

    except Exception as exc:
        logger.error("add_chunks failed: %s", exc)
        return False


def reset_collection() -> bool:
    """Wipe and recreate the collection. Also deletes the stale vector_db folder."""
    global _client, _collection

    # First try graceful chromadb delete
    client = get_client()
    if client:
        try:
            client.delete_collection(COLLECTION_NAME)
            logger.info("[INFO] Collection '%s' deleted.", COLLECTION_NAME)
        except Exception:
            pass

    # Also nuke the on-disk folder so stale embedding-function config is gone
    db_path = os.getenv("CHROMA_DB_PATH", DEFAULT_DB_PATH)
    try:
        import shutil
        if Path(db_path).exists():
            shutil.rmtree(db_path)
            logger.info("[INFO] Deleted vector_db folder at %s", db_path)
    except Exception as exc:
        logger.warning("Could not delete vector_db folder: %s", exc)

    # Reset caches so next call rebuilds from scratch
    _client     = None
    _collection = None

    return get_collection() is not None