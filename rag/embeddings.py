"""
rag/embeddings.py
-----------------
Multilingual embedding wrapper using NVIDIA NIM's NVIDIAEmbeddings
via langchain_nvidia_ai_endpoints.

Model: nvidia/llama-nemotron-embed-1b-v2
- Multilingual & cross-lingual retrieval
- Long context support
- Free tier on NVIDIA NIM

Usage:
    from rag.embeddings import get_embedder, embed_text, embed_batch

    embedder = get_embedder()
    vector   = embed_text("show top customers by revenue")
    vectors  = embed_batch(["question one", "question two"])
"""

import os
import time
import logging
from typing import Optional

from dotenv import load_dotenv
from langchain_nvidia_ai_endpoints import NVIDIAEmbeddings

load_dotenv()

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nvidia/llama-nemotron-embed-1b-v2")
EMBED_API_KEY   = os.getenv("NVIDIA_EMBED_API_KEY") or os.getenv("NVIDIA_API_KEY")

# Retry settings for transient API errors
MAX_RETRIES     = 3
RETRY_DELAY_SEC = 2


# ── Client factory ─────────────────────────────────────────────────────────────

def get_embedder(model: Optional[str] = None) -> NVIDIAEmbeddings:
    """
    Create and return an NVIDIAEmbeddings client.

    Returns:
        NVIDIAEmbeddings instance ready for query/passage embedding.

    Raises:
        ValueError: If NVIDIA_API_KEY / NVIDIA_EMBED_API_KEY is missing.
    """
    if not EMBED_API_KEY:
        raise ValueError(
            "❌ No embedding API key found. "
            "Set NVIDIA_EMBED_API_KEY or NVIDIA_API_KEY in your .env file."
        )

    return NVIDIAEmbeddings(
        model=model or EMBEDDING_MODEL,
        api_key=EMBED_API_KEY,
        truncate="END",   # silently truncate inputs that exceed model max
    )


# ── Single text embedding (query) ─────────────────────────────────────────────

def embed_text(
    text: str,
    embedder: Optional[NVIDIAEmbeddings] = None,
) -> list[float]:
    """
    Embed a single query string.

    Uses embed_query() — the correct method for user questions at
    retrieval time (as opposed to documents at indexing time).

    Args:
        text:     Input query string (any supported language).
        embedder: Optional pre-built NVIDIAEmbeddings instance.

    Returns:
        List of floats representing the embedding vector.

    Raises:
        ValueError:   On empty input.
        RuntimeError: If all retries are exhausted.
    """
    if not text or not text.strip():
        raise ValueError("❌ embed_text received an empty string.")

    embedder   = embedder or get_embedder()
    last_error: Exception = RuntimeError("Unknown error")

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return embedder.embed_query(text)
        except Exception as exc:
            last_error = exc
            logger.warning(
                "embed_text attempt %d/%d failed: %s", attempt, MAX_RETRIES, exc
            )
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY_SEC * attempt)

    raise RuntimeError(
        f"❌ embed_text failed after {MAX_RETRIES} attempts. "
        f"Last error: {last_error}"
    )


# ── Batch embedding (documents / passages) ────────────────────────────────────

def embed_batch(
    texts: list[str],
    embedder: Optional[NVIDIAEmbeddings] = None,
) -> list[list[float]]:
    """
    Embed a list of document/passage strings for indexing into ChromaDB.

    Uses embed_documents() — the correct method for schema chunks,
    business rules, and glossary entries at indexing time.

    Args:
        texts:    List of document strings to embed.
        embedder: Optional pre-built NVIDIAEmbeddings instance.

    Returns:
        List of embedding vectors in the same order as input texts.

    Raises:
        ValueError:   If texts list is empty.
        RuntimeError: If all retries are exhausted.
    """
    if not texts:
        raise ValueError("❌ embed_batch received an empty list.")

    embedder   = embedder or get_embedder()
    clean      = [t for t in texts if t and t.strip()]
    last_error: Exception = RuntimeError("Unknown error")

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            vectors = embedder.embed_documents(clean)
            logger.debug("Embedded %d documents.", len(vectors))
            return vectors
        except Exception as exc:
            last_error = exc
            logger.warning(
                "embed_batch attempt %d/%d failed: %s", attempt, MAX_RETRIES, exc
            )
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY_SEC * attempt)

    raise RuntimeError(
        f"❌ embed_batch failed after {MAX_RETRIES} attempts. "
        f"Last error: {last_error}"
    )


# ── Health check ───────────────────────────────────────────────────────────────

def check_embedding_health() -> bool:
    """
    Send a minimal test embedding to verify the NIM endpoint is
    reachable and the API key is valid.

    Returns:
        True if the endpoint responds correctly, False otherwise.
    """
    try:
        vector = embed_text("health check")
        ok = isinstance(vector, list) and len(vector) > 0
        if ok:
            logger.info(
                "✅ Embedding health check passed. Model: %s | Vector dim: %d",
                EMBEDDING_MODEL, len(vector),
            )
        return ok
    except Exception as exc:
        logger.error("❌ Embedding health check failed: %s", exc)
        return False


# ── Quick test ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print(f"Model   : {EMBEDDING_MODEL}\n")

    # Test 1 — health check
    print("── Health check ──────────────────────────────")
    healthy = check_embedding_health()
    print(f"Healthy : {healthy}\n")

    if healthy:
        # Test 2 — multilingual single embeddings
        print("── Multilingual embed_query ──────────────────")
        test_queries = [
            ("English", "Show top 10 customers by revenue"),
            ("Hindi",   "राजस्व के अनुसार शीर्ष 10 ग्राहक दिखाओ"),
            ("French",  "Montrez les 10 meilleurs clients par revenus"),
            ("Spanish", "Mostrar los 10 principales clientes por ingresos"),
        ]

        vectors = []
        for lang, query in test_queries:
            vec = embed_text(query)
            vectors.append(vec)
            print(f"  [{lang:8s}] dim={len(vec)} | first3={[round(v,4) for v in vec[:3]]}")

        # Test 3 — batch embed_documents
        print("\n── Batch embed_documents ─────────────────────")
        docs = [
            "Table: customers — stores customer name, email, created_at",
            "Table: orders — stores order_id, customer_id, amount, status",
            "Revenue: total value of completed orders",
        ]
        batch_vecs = embed_batch(docs)
        print(f"  Docs     : {len(docs)}")
        print(f"  Returned : {len(batch_vecs)} vectors")
        print(f"  Dim match: {all(len(v) == len(vectors[0]) for v in batch_vecs)}")