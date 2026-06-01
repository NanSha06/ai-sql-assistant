"""
rag/vector_store.py
-------------------
ChromaDB vector store setup and management.

Responsibilities:
- Initialize and persist ChromaDB collection
- Add document chunks with metadata
- Query by similarity (used by retriever.py)
- Reset / inspect the collection

Usage:
    from rag.vector_store import get_vector_store, add_documents, query_store

    store = get_vector_store()
    add_documents(store, texts=["..."], metadatas=[{...}])
    results = query_store(store, query_text="top customers by revenue", k=5)
"""

import os
import logging
from typing import Optional

import chromadb
from chromadb.config import Settings
from dotenv import load_dotenv
from langchain_nvidia_ai_endpoints import NVIDIAEmbeddings

from rag.embeddings import get_embedder, embed_text, embed_batch

load_dotenv()

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

CHROMA_PERSIST_PATH     = os.getenv("CHROMA_PERSIST_PATH",     "./vector_db")
CHROMA_COLLECTION_NAME  = os.getenv("CHROMA_COLLECTION_NAME",  "sql_assistant_rag")
RAG_TOP_K               = int(os.getenv("RAG_TOP_K", "5"))


# ── ChromaDB client factory ────────────────────────────────────────────────────

def get_chroma_client() -> chromadb.PersistentClient:
    """
    Create a persistent ChromaDB client that saves data to disk.

    Data is stored at CHROMA_PERSIST_PATH so it survives restarts.
    The vector_db/ directory is created automatically if it doesn't exist.

    Returns:
        chromadb.PersistentClient instance.
    """
    os.makedirs(CHROMA_PERSIST_PATH, exist_ok=True)

    client = chromadb.PersistentClient(
        path=CHROMA_PERSIST_PATH,
        settings=Settings(anonymized_telemetry=False),
    )

    logger.debug("ChromaDB client ready. Path: %s", CHROMA_PERSIST_PATH)
    return client


# ── Collection factory ─────────────────────────────────────────────────────────

def get_vector_store(
    client: Optional[chromadb.PersistentClient] = None,
    collection_name: Optional[str] = None,
) -> chromadb.Collection:
    """
    Get or create the ChromaDB collection.

    Uses cosine similarity — correct for normalized embedding vectors
    produced by nvidia/llama-nemotron-embed-1b-v2.

    Args:
        client:          Optional pre-built ChromaDB client.
        collection_name: Override collection name (defaults to env var).

    Returns:
        ChromaDB Collection ready for add/query operations.
    """
    client          = client or get_chroma_client()
    collection_name = collection_name or CHROMA_COLLECTION_NAME

    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},   # cosine similarity for embeddings
    )

    logger.info(
        "✅ Vector store ready. Collection: '%s' | Documents: %d",
        collection_name,
        collection.count(),
    )
    return collection


# ── Add documents ──────────────────────────────────────────────────────────────

def add_documents(
    collection: chromadb.Collection,
    texts: list[str],
    metadatas: Optional[list[dict]] = None,
    ids: Optional[list[str]] = None,
    embedder: Optional[NVIDIAEmbeddings] = None,
    batch_size: int = 32,
) -> int:
    """
    Embed and insert document chunks into the ChromaDB collection.

    Called by indexing.py when loading schema docs, business rules,
    glossary entries, and KPI definitions.

    Args:
        collection: Target ChromaDB collection.
        texts:      List of text chunks to store.
        metadatas:  Optional list of metadata dicts (one per chunk).
                    Useful for filtering by source_type, table_name, etc.
        ids:        Optional list of unique string IDs.
                    Auto-generated as "doc_0", "doc_1"... if not provided.
        embedder:   Optional pre-built NVIDIAEmbeddings instance.
        batch_size: Number of chunks to embed and insert per batch.

    Returns:
        Total number of documents successfully added.

    Raises:
        ValueError: If texts list is empty.
    """
    if not texts:
        raise ValueError("❌ add_documents received an empty texts list.")

    embedder  = embedder  or get_embedder()
    metadatas = metadatas or [{} for _ in texts]
    ids       = ids       or [f"doc_{i}" for i in range(len(texts))]

    total_added = 0

    for i in range(0, len(texts), batch_size):
        batch_texts     = texts[i : i + batch_size]
        batch_metadatas = metadatas[i : i + batch_size]
        batch_ids       = ids[i : i + batch_size]

        try:
            vectors = embed_batch(batch_texts, embedder=embedder)

            collection.upsert(           # upsert = insert or update if ID exists
                documents=batch_texts,
                embeddings=vectors,
                metadatas=batch_metadatas,
                ids=batch_ids,
            )

            total_added += len(batch_texts)
            logger.debug(
                "Upserted batch %d-%d (%d docs). Total: %d",
                i, i + len(batch_texts), len(batch_texts), total_added,
            )

        except Exception as exc:
            logger.error("❌ Failed to add batch starting at index %d: %s", i, exc)
            raise

    logger.info("✅ Added %d documents to collection '%s'.", total_added, collection.name)
    return total_added


# ── Query store ────────────────────────────────────────────────────────────────

def query_store(
    collection: chromadb.Collection,
    query_text: str,
    k: Optional[int] = None,
    where: Optional[dict] = None,
    embedder: Optional[NVIDIAEmbeddings] = None,
) -> list[dict]:
    """
    Retrieve the top-k most similar documents for a query string.

    Called by retriever.py at query time to fetch relevant schema
    context, business rules, and glossary entries.

    Args:
        collection: ChromaDB collection to search.
        query_text: User question (any supported language).
        k:          Number of results to return (defaults to RAG_TOP_K).
        where:      Optional ChromaDB metadata filter dict.
                    Example: {"source_type": "schema"}
        embedder:   Optional pre-built NVIDIAEmbeddings instance.

    Returns:
        List of result dicts, each containing:
            - text:      The document chunk text
            - metadata:  Associated metadata dict
            - distance:  Cosine distance (lower = more similar)
            - id:        Document ID

    Raises:
        ValueError: If query_text is empty.
        RuntimeError: If collection is empty.
    """
    if not query_text or not query_text.strip():
        raise ValueError("❌ query_store received an empty query string.")

    if collection.count() == 0:
        raise RuntimeError(
            "❌ Vector store is empty. Run indexing.py first to populate it."
        )

    k        = k or RAG_TOP_K
    embedder = embedder or get_embedder()

    query_vector = embed_text(query_text, embedder=embedder)

    query_kwargs = dict(
        query_embeddings=[query_vector],
        n_results=min(k, collection.count()),   # can't request more than total docs
        include=["documents", "metadatas", "distances"],
    )
    if where:
        query_kwargs["where"] = where

    raw = collection.query(**query_kwargs)

    # Flatten ChromaDB's nested list response into a clean list of dicts
    results = []
    for doc, meta, dist, doc_id in zip(
        raw["documents"][0],
        raw["metadatas"][0],
        raw["distances"][0],
        raw["ids"][0],
    ):
        results.append({
            "text":     doc,
            "metadata": meta,
            "distance": round(dist, 4),
            "id":       doc_id,
        })

    logger.debug(
        "Query returned %d results for: '%s'", len(results), query_text[:60]
    )
    return results


# ── Utility helpers ────────────────────────────────────────────────────────────

def get_collection_stats(collection: chromadb.Collection) -> dict:
    """
    Return a summary of what's currently stored in the collection.

    Returns:
        Dict with total doc count and breakdown by source_type.
    """
    total = collection.count()

    if total == 0:
        return {"total": 0, "by_source_type": {}}

    all_docs = collection.get(include=["metadatas"])
    source_counts: dict[str, int] = {}

    for meta in all_docs["metadatas"]:
        source_type = meta.get("source_type", "unknown")
        source_counts[source_type] = source_counts.get(source_type, 0) + 1

    return {"total": total, "by_source_type": source_counts}


def reset_collection(
    client: Optional[chromadb.PersistentClient] = None,
    collection_name: Optional[str] = None,
) -> None:
    """
    Delete and recreate the collection — wipes all indexed documents.

    Use when you want to re-index from scratch after schema changes.

    Args:
        client:          Optional pre-built ChromaDB client.
        collection_name: Override collection name.
    """
    client          = client or get_chroma_client()
    collection_name = collection_name or CHROMA_COLLECTION_NAME

    try:
        client.delete_collection(collection_name)
        logger.warning("🗑️  Collection '%s' deleted.", collection_name)
    except Exception:
        pass  # collection didn't exist — that's fine

    client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )
    logger.info("✅ Collection '%s' recreated (empty).", collection_name)


# ── Quick test ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("── Initializing vector store ─────────────────")
    collection = get_vector_store()
    print(f"Collection : {collection.name}")
    print(f"Documents  : {collection.count()}\n")

    # Test data — simulated schema + glossary chunks
    sample_texts = [
        "Table: customers — columns: customer_id, name, email, created_at. Stores all registered customers.",
        "Table: orders — columns: order_id, customer_id, amount, status, created_at. Stores purchase orders.",
        "Table: products — columns: product_id, name, category, price. Stores product catalog.",
        "Foreign key: orders.customer_id → customers.customer_id",
        "Business term: Revenue — total value of all completed (status='completed') orders.",
        "KPI: Monthly Active Users — count of distinct customer_ids with an order in a calendar month.",
    ]
    sample_metadatas = [
        {"source_type": "schema",   "table_name": "customers"},
        {"source_type": "schema",   "table_name": "orders"},
        {"source_type": "schema",   "table_name": "products"},
        {"source_type": "schema",   "table_name": "orders"},
        {"source_type": "glossary", "term": "revenue"},
        {"source_type": "kpi",      "term": "monthly_active_users"},
    ]
    sample_ids = [f"test_{i}" for i in range(len(sample_texts))]

    print("── Adding test documents ──────────────────────")
    added = add_documents(
        collection,
        texts=sample_texts,
        metadatas=sample_metadatas,
        ids=sample_ids,
    )
    print(f"Added : {added} documents\n")

    print("── Collection stats ───────────────────────────")
    stats = get_collection_stats(collection)
    print(f"Total          : {stats['total']}")
    print(f"By source_type : {stats['by_source_type']}\n")

    print("── Query test (English) ───────────────────────")
    results = query_store(collection, "show top customers by revenue", k=3)
    for r in results:
        print(f"  [{r['distance']:.4f}] ({r['metadata'].get('source_type')}) {r['text'][:70]}")

    print("\n── Query test (Hindi) ─────────────────────────")
    results_hi = query_store(collection, "राजस्व के अनुसार शीर्ष ग्राहक", k=3)
    for r in results_hi:
        print(f"  [{r['distance']:.4f}] ({r['metadata'].get('source_type')}) {r['text'][:70]}")

    print("\n── Metadata filter test ───────────────────────")
    schema_only = query_store(
        collection,
        "customer orders",
        k=3,
        where={"source_type": "schema"},
    )
    print(f"Schema-only results: {len(schema_only)}")
    for r in schema_only:
        print(f"  [{r['distance']:.4f}] {r['text'][:70]}")

    print("\n── Reset test ─────────────────────────────────")
    reset_collection()
    empty = get_vector_store()
    print(f"After reset, count: {empty.count()}")