"""
rag/retriever.py
----------------
Query-time retrieval layer.

Combines language detection + vector search to fetch the most
relevant schema, glossary, business rules, and KPI chunks
for a given user question (any language).

This is the single entry point that chain.py will call:

    from rag.retriever import retrieve_context
    context = retrieve_context("show top customers by revenue")

Usage:
    python -m rag.retriever
"""

import logging
import os
from typing import Optional

from dotenv import load_dotenv

from rag.embeddings import get_embedder
from rag.vector_store import get_chroma_client, get_vector_store, query_store
from rag.language_detector import detect_language, DetectionResult

load_dotenv()

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

RAG_TOP_K = int(os.getenv("RAG_TOP_K", "5"))

# How many results to fetch per source_type when doing split retrieval.
# Total results = SCHEMA_K + GLOSSARY_K + KPI_K + RULES_K
SCHEMA_K  = int(os.getenv("SCHEMA_K",  "3"))
GLOSSARY_K = int(os.getenv("GLOSSARY_K", "1"))
KPI_K     = int(os.getenv("KPI_K",     "1"))
RULES_K   = int(os.getenv("RULES_K",   "1"))


# ── Result dataclass ───────────────────────────────────────────────────────────

class RetrievalResult:
    """
    Structured output from a retrieval call.

    Attributes:
        chunks:    List of retrieved document dicts (text, metadata, distance).
        language:  DetectionResult from language_detector.
        query:     Original user query.
        total:     Total number of chunks retrieved.
    """
    def __init__(
        self,
        chunks: list[dict],
        language: DetectionResult,
        query: str,
    ):
        self.chunks   = chunks
        self.language = language
        self.query    = query
        self.total    = len(chunks)

    def by_source_type(self, source_type: str) -> list[dict]:
        """Filter chunks by source_type metadata."""
        return [c for c in self.chunks if c["metadata"].get("source_type") == source_type]

    def __repr__(self) -> str:
        return (
            f"RetrievalResult("
            f"total={self.total}, "
            f"language={self.language.language_name}, "
            f"query='{self.query[:40]}...')"
        )


# ── Core retrieval ─────────────────────────────────────────────────────────────

def retrieve_context(
    query: str,
    k: Optional[int] = None,
    collection=None,
    embedder=None,
    split_by_source: bool = True,
) -> RetrievalResult:
    """
    Main retrieval function — called by chain.py at query time.

    Detects query language, embeds it, and retrieves the most
    relevant chunks from ChromaDB.

    Two retrieval modes:

    split_by_source=True (default):
        Fetches SCHEMA_K schema chunks + GLOSSARY_K glossary chunks
        + KPI_K kpi chunks + RULES_K business_rules chunks separately.
        Guarantees representation from each source type.

    split_by_source=False:
        Single query across all source types, returns top-k overall.
        Faster but may return all results from one source type.

    Args:
        query:            User question (any language).
        k:                Total results to return (overrides env RAG_TOP_K).
        collection:       Optional pre-built ChromaDB collection.
        embedder:         Optional pre-built NVIDIAEmbeddings instance.
        split_by_source:  Whether to retrieve per source type.

    Returns:
        RetrievalResult with chunks, language info, and query.

    Raises:
        RuntimeError: If vector store is empty (indexing hasn't been run).
    """
    if not query or not query.strip():
        raise ValueError("❌ retrieve_context received an empty query.")

    # Lazy-init shared resources
    embedder   = embedder   or get_embedder()
    collection = collection or get_vector_store(client=get_chroma_client())

    if collection.count() == 0:
        raise RuntimeError(
            "❌ Vector store is empty. "
            "Run `python -m rag.indexing` first to populate it."
        )

    # Detect language (for logging + UI display — doesn't change retrieval)
    lang_result = detect_language(query)
    logger.info("🌐 %s", lang_result)

    chunks: list[dict] = []

    if split_by_source:
        # ── Per-source retrieval ───────────────────────────────────────────────
        # Fetch from each source type separately so every category is represented
        source_ks = {
            "schema":         SCHEMA_K,
            "glossary":       GLOSSARY_K,
            "kpi":            KPI_K,
            "business_rules": RULES_K,
        }

        seen_ids: set[str] = set()

        for source_type, source_k in source_ks.items():
            try:
                results = query_store(
                    collection,
                    query_text=query,
                    k=source_k,
                    where={"source_type": source_type},
                    embedder=embedder,
                )
                for r in results:
                    if r["id"] not in seen_ids:
                        chunks.append(r)
                        seen_ids.add(r["id"])

                logger.debug(
                    "  [%s] retrieved %d chunk(s)", source_type, len(results)
                )

            except Exception as exc:
                # A source type with no docs raises an error from query_store —
                # log and continue rather than failing the whole retrieval
                logger.debug("  [%s] skipped: %s", source_type, exc)

    else:
        # ── Single-query retrieval ─────────────────────────────────────────────
        k      = k or RAG_TOP_K
        chunks = query_store(
            collection,
            query_text=query,
            k=k,
            embedder=embedder,
        )

    # Sort final results by distance (most similar first)
    chunks.sort(key=lambda x: x["distance"])

    logger.info(
        "✅ Retrieved %d chunk(s) for query: '%s'",
        len(chunks), query[:60],
    )

    return RetrievalResult(chunks=chunks, language=lang_result, query=query)


# ── Convenience wrapper ────────────────────────────────────────────────────────

def retrieve_as_text(
    query: str,
    separator: str = "\n\n---\n\n",
    **kwargs,
) -> str:
    """
    Retrieve context and return it as a single joined string.

    Used by context_builder.py to assemble the final prompt context block.

    Args:
        query:     User question.
        separator: String to join chunks with.
        **kwargs:  Passed through to retrieve_context().

    Returns:
        Single string of all retrieved chunks joined by separator.
    """
    result = retrieve_context(query, **kwargs)
    return separator.join(c["text"] for c in result.chunks)


# ── Quick test ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    test_queries = [
        ("English", "Show top 10 customers by revenue"),
        ("Hindi",   "राजस्व के अनुसार शीर्ष 10 ग्राहक दिखाओ"),
        ("French",  "Montrez les 10 meilleurs clients par revenus"),
        ("Spanish", "Mostrar los 10 principales clientes por ingresos"),
    ]

    print("\n🔍 Retriever Test")
    print("=" * 60)

    for label, query in test_queries:
        print(f"\n── [{label}] ──────────────────────────────────────")
        print(f"Query: {query}")

        try:
            result = retrieve_context(query)
            print(f"Language : {result.language}")
            print(f"Chunks   : {result.total}")

            for i, chunk in enumerate(result.chunks, 1):
                src  = chunk["metadata"].get("source_type", "?")
                dist = chunk["distance"]
                text = chunk["text"][:80].replace("\n", " ")
                print(f"  {i}. [{src:<15}] dist={dist:.4f} | {text}")

        except RuntimeError as e:
            print(f"  ⚠️  {e}")

    # Test retrieve_as_text
    print("\n── retrieve_as_text ───────────────────────────────────")
    try:
        text_context = retrieve_as_text("top customers by revenue")
        print(text_context[:300] + "..." if len(text_context) > 300 else text_context)
    except RuntimeError as e:
        print(f"  ⚠️  {e}")