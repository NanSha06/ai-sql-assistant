"""
rag/embeddings.py
─────────────────
Embedding provider for the RAG layer.

Calls NVIDIA NIM embeddings directly via the OpenAI-compatible REST API
using the `openai` package — zero PyTorch, zero DLL dependencies.

The `openai` package is already in requirements.txt (used by langchain-openai).

Public API:
    get_embedder()          -> Embeddings instance (cached)
    embed_text(text)        -> List[float]
    embed_batch(texts)      -> List[List[float]]

Environment variables:
    NVIDIA_API_KEY  — same key used for the LLM
"""

import os
import time
import logging
from typing import List

from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)

NVIDIA_EMBED_MODEL  = "nvidia/nv-embedqa-e5-v5"
NVIDIA_BASE_URL     = "https://integrate.api.nvidia.com/v1"
EMBED_DIM           = 1024
EMBED_TIMEOUT_SEC   = 15   # hard cap — fail fast if NIM is slow

_embedder = None


def get_embedder():
    """Return a cached embedder instance. No PyTorch required."""
    global _embedder
    if _embedder is not None:
        return _embedder

    api_key = os.getenv("NVIDIA_API_KEY")

    if api_key:
        _embedder = _NIMEmbedder(api_key)
        logger.info("[embeddings] NVIDIA NIM embeddings ready (%s, %d-dim, timeout=%ds).",
                    NVIDIA_EMBED_MODEL, EMBED_DIM, EMBED_TIMEOUT_SEC)
    else:
        logger.warning(
            "[embeddings] NVIDIA_API_KEY not set. "
            "RAG will use fallback embedder — set the key for real semantic search."
        )
        _embedder = _FallbackEmbedder()

    return _embedder


def embed_text(text: str) -> List[float]:
    """Embed a single string and return its vector."""
    return get_embedder().embed_query(text)


def embed_batch(texts: List[str]) -> List[List[float]]:
    """Embed a list of strings and return their vectors."""
    if not texts:
        return []
    return get_embedder().embed_documents(texts)


# ── Provider: NVIDIA NIM via openai REST client (no PyTorch) ─────────────────

class _NIMEmbedder:
    """
    Calls NVIDIA NIM /v1/embeddings directly with the `openai` package.
    No langchain-nvidia-ai-endpoints, no torch, no DLLs.

    timeout is set at the httpx transport level so the request is
    hard-killed after EMBED_TIMEOUT_SEC seconds — no more hangs.
    """

    def __init__(self, api_key: str):
        from openai import OpenAI          # already in requirements.txt
        self._client = OpenAI(
            api_key=api_key,
            base_url=NVIDIA_BASE_URL,
            timeout=EMBED_TIMEOUT_SEC,     # ← hard timeout (connect + read)
        )

    def embed_query(self, text: str) -> List[float]:
        return self._call([text])[0]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        # NIM accepts up to 96 inputs per call — batch safely
        results = []
        batch_size = 32
        for i in range(0, len(texts), batch_size):
            results.extend(self._call(texts[i : i + batch_size]))
        return results

    def _call(self, texts: List[str]) -> List[List[float]]:
        # Replace empty strings — NIM rejects them
        texts = [t if t and t.strip() else "." for t in texts]

        t0 = time.perf_counter()
        logger.debug("[embeddings] NIM request start (%d texts, model=%s)",
                     len(texts), NVIDIA_EMBED_MODEL)

        response = self._client.embeddings.create(
            model=NVIDIA_EMBED_MODEL,
            input=texts,
            encoding_format="float",
            extra_body={"input_type": "query", "truncate": "END"},
        )

        elapsed = time.perf_counter() - t0
        logger.debug("[embeddings] NIM request end (%.2fs)", elapsed)

        # Sort by index to preserve order
        items = sorted(response.data, key=lambda x: x.index)
        return [item.embedding for item in items]


# ── Fallback: deterministic hash embedder (stdlib only) ──────────────────────

class _FallbackEmbedder:
    """
    Zero-dependency fallback when no API key is set.
    Keeps ChromaDB happy so the app starts — retrieval quality is meaningless.
    """
    DIM = EMBED_DIM

    def embed_query(self, text: str) -> List[float]:
        return self._hash_embed(text)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self._hash_embed(t) for t in texts]

    def _hash_embed(self, text: str) -> List[float]:
        import hashlib
        seed = int(hashlib.md5(text.encode("utf-8", errors="replace")).hexdigest(), 16)
        vec = []
        for _ in range(self.DIM):
            seed = (seed * 1664525 + 1013904223) & 0xFFFFFFFF
            vec.append((seed / 0xFFFFFFFF) * 2 - 1)
        norm = sum(x * x for x in vec) ** 0.5 or 1.0
        return [x / norm for x in vec]