"""
rag/retriever.py
────────────────
Retrieves relevant schema / glossary / KPI chunks from ChromaDB
and returns a RetrievalResult object consumed by context_builder.py.

Public API:
    retrieve_context(query, collection=None, embedder=None) -> RetrievalResult
    RetrievalResult  — rich result object with .chunks, .total, .language,
                       .by_source_type()
"""

import time
import logging
from typing import List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

TOP_K    = 5
MIN_SCORE = 0.25   # minimum cosine similarity (0-1)


# ── Language result ───────────────────────────────────────────────────────────

@dataclass
class LanguageResult:
    language: str       = "en"
    language_name: str  = "English"
    confidence: float   = 1.0


def _detect_language(text: str) -> LanguageResult:
    """Detect language of text. Falls back to English on any error."""
    try:
        from langdetect import detect, detect_langs   # noqa: PLC0415
        lang = detect(text)
        langs = detect_langs(text)
        confidence = langs[0].prob if langs else 1.0
        name = _LANG_NAMES.get(lang, lang.upper())
        return LanguageResult(language=lang, language_name=name, confidence=confidence)
    except Exception:
        return LanguageResult()


_LANG_NAMES = {
    "en": "English", "hi": "Hindi",   "fr": "French",  "es": "Spanish",
    "de": "German",  "zh": "Chinese", "ja": "Japanese","pt": "Portuguese",
    "ar": "Arabic",  "ru": "Russian", "it": "Italian", "ko": "Korean",
}


# ── RetrievalResult ───────────────────────────────────────────────────────────

@dataclass
class RetrievalResult:
    """
    Returned by retrieve_context().
    Consumed by context_builder.build_context().
    """
    query:    str
    chunks:   List[dict]          = field(default_factory=list)
    language: LanguageResult      = field(default_factory=LanguageResult)

    @property
    def total(self) -> int:
        return len(self.chunks)

    def by_source_type(self, source_type: str) -> List[dict]:
        """Return chunks filtered by source_type metadata."""
        return [c for c in self.chunks if c.get("source_type") == source_type]


# ── Main retrieval function ───────────────────────────────────────────────────

def retrieve_context(
    query: str,
    collection=None,
    embedder=None,
) -> RetrievalResult:
    """
    Embed the query and retrieve TOP_K most relevant chunks from ChromaDB.

    FAIL-FAST CONTRACT:
    - Embedding requests are hard-capped at 15s (set in embeddings.py).
    - Any exception (timeout, network, ChromaDB) is caught and logged.
    - On ANY failure, returns an empty RetrievalResult so SQL generation
      proceeds without RAG context. Never raises, never blocks.

    Args:
        query:      User question (any language).
        collection: Optional pre-built ChromaDB collection.
        embedder:   Optional pre-built embedder instance.

    Returns:
        RetrievalResult with chunks and language detection.
    """
    t_start = time.perf_counter()
    logger.info("[retriever] Entering RAG retrieval for: %.60s", query)

    lang = _detect_language(query)
    result = RetrievalResult(query=query, language=lang)

    if not query or not query.strip():
        logger.debug("[retriever] Empty query — skipping RAG.")
        return result

    try:
        # ── Collection lookup ─────────────────────────────────────────────
        if collection is None:
            from rag.vector_store import get_collection   # noqa: PLC0415
            collection = get_collection()

        if collection is None:
            logger.debug("[retriever] ChromaDB collection unavailable — RAG skipped.")
            return result

        count = collection.count()
        if count == 0:
            logger.debug("[retriever] ChromaDB collection is empty — run rag.indexing first.")
            return result

        # ── Embedding ─────────────────────────────────────────────────────
        t_embed_start = time.perf_counter()
        logger.info("[retriever] Embedding request start")

        if embedder is None:
            from rag.embeddings import embed_text         # noqa: PLC0415
            query_vector = embed_text(query)
        else:
            query_vector = embedder.embed_query(query)

        t_embed_end = time.perf_counter()
        logger.info("[retriever] Embedding request end (%.2fs)",
                    t_embed_end - t_embed_start)

        # ── ChromaDB query ────────────────────────────────────────────────
        t_chroma_start = time.perf_counter()
        logger.info("[retriever] Chroma query start (top_k=%d, collection_size=%d)",
                    TOP_K, count)

        results = collection.query(
            query_embeddings=[query_vector],
            n_results=min(TOP_K, count),
            include=["documents", "metadatas", "distances"],
        )

        t_chroma_end = time.perf_counter()
        logger.info("[retriever] Chroma query end (%.2fs)",
                    t_chroma_end - t_chroma_start)

        # ── Parse results ─────────────────────────────────────────────────
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for doc, meta, dist in zip(documents, metadatas, distances):
            if not doc or not doc.strip():
                continue

            # Convert L2 distance → cosine similarity approximation
            similarity = 1.0 / (1.0 + dist)
            if similarity < MIN_SCORE:
                continue

            result.chunks.append({
                "text":        doc.strip(),
                "source_type": (meta or {}).get("source_type", "schema"),
                "filename":    (meta or {}).get("filename", ""),
                "table_name":  (meta or {}).get("table_name", ""),
                "distance":    round(dist, 4),
                "similarity":  round(similarity, 4),
            })

        logger.info("[retriever] Retrieved %d chunks for query.", result.total)

    except Exception as exc:
        # ── FAIL-FAST: catch everything, log, return empty result ──────
        logger.warning("[retriever] RAG retrieval failed (%.2fs): %s",
                       time.perf_counter() - t_start, exc)

    t_total = time.perf_counter() - t_start
    logger.info("[retriever] Total retrieval time: %.2fs", t_total)

    return result