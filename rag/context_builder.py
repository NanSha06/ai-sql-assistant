"""
rag/context_builder.py
----------------------
Assembles retrieved RAG chunks into a structured context block
that gets injected into the LangChain SQL agent prompt.

Responsibilities:
- Format chunks by source type (schema, glossary, kpi, business_rules)
- Build a clean, LLM-readable context string
- Add language hint when query is non-English
- Keep context within token budget

Usage:
    from rag.context_builder import build_context
    from rag.retriever import retrieve_context

    result  = retrieve_context("show top customers by revenue")
    context = build_context(result)
    # → inject context into prompts.py
"""

import logging
import os
from typing import Optional

from dotenv import load_dotenv

from rag.retriever import retrieve_context, RetrievalResult

load_dotenv()

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

# Rough character limit for context block to avoid oversized prompts.
# ~4 chars per token → 2000 tokens ≈ 8000 chars
MAX_CONTEXT_CHARS = int(os.getenv("MAX_CONTEXT_CHARS", "8000"))

# Section headers shown to the LLM
SECTION_HEADERS = {
    "schema":         "### Relevant Tables & Columns",
    "glossary":       "### Business Definitions",
    "kpi":            "### KPI Definitions",
    "business_rules": "### Business Rules",
}


# ── Context builder ────────────────────────────────────────────────────────────

def build_context(
    retrieval: RetrievalResult,
    max_chars: Optional[int] = None,
    include_language_hint: bool = True,
    include_distances: bool = False,
) -> str:
    """
    Format a RetrievalResult into a structured context string
    ready for injection into the SQL agent prompt.

    Groups chunks by source_type under labelled sections:

        ### Relevant Tables & Columns
        <schema chunks>

        ### Business Definitions
        <glossary chunks>

        ### KPI Definitions
        <kpi chunks>

        ### Business Rules
        <business_rules chunks>

    Args:
        retrieval:             Output of retrieve_context().
        max_chars:             Max character length of output (default 8000).
        include_language_hint: Prepend a note when query is non-English.
        include_distances:     Append similarity distance to each chunk
                               (useful for debugging, off by default).

    Returns:
        Formatted context string, or empty string if no chunks retrieved.
    """
    if not retrieval.chunks:
        logger.warning("build_context received empty chunks — returning empty string.")
        return ""

    max_chars = max_chars or MAX_CONTEXT_CHARS
    sections: list[str] = []

    # ── Language hint ──────────────────────────────────────────────────────────
    if include_language_hint and retrieval.language.language != "en":
        sections.append(
            f"<!-- Query language: {retrieval.language.language_name} "
            f"({retrieval.language.language}) — "
            f"Generate SQL in standard PostgreSQL regardless of query language. -->"
        )

    # ── Group chunks by source_type ────────────────────────────────────────────
    source_order = ["schema", "glossary", "kpi", "business_rules"]

    for source_type in source_order:
        chunks = retrieval.by_source_type(source_type)
        if not chunks:
            continue

        header = SECTION_HEADERS.get(source_type, f"### {source_type.title()}")
        section_lines = [header]

        for chunk in chunks:
            text = chunk["text"].strip()
            if include_distances:
                text = f"{text}\n<!-- similarity distance: {chunk['distance']} -->"
            section_lines.append(text)

        sections.append("\n\n".join(section_lines))

    if not sections:
        return ""

    context = "\n\n---\n\n".join(sections)

    # ── Token budget guard ─────────────────────────────────────────────────────
    if len(context) > max_chars:
        logger.warning(
            "Context exceeds %d chars (%d). Truncating.",
            max_chars, len(context),
        )
        context = context[:max_chars] + "\n\n[... context truncated ...]"

    logger.debug("Built context: %d chars, %d chunks.", len(context), len(retrieval.chunks))
    return context


# ── Full pipeline convenience function ────────────────────────────────────────

def get_rag_context(
    query: str,
    collection=None,
    embedder=None,
    **build_kwargs,
) -> tuple[str, RetrievalResult]:
    """
    One-call convenience: retrieve + build context.

    This is what chain.py will call — single import, single call.

        from rag.context_builder import get_rag_context
        context, retrieval = get_rag_context(question)

    Args:
        query:        User question (any language).
        collection:   Optional pre-built ChromaDB collection.
        embedder:     Optional pre-built NVIDIAEmbeddings instance.
        **build_kwargs: Passed to build_context().

    Returns:
        Tuple of (context_string, RetrievalResult).
        context_string is empty if vector store is empty.
    """
    try:
        retrieval = retrieve_context(
            query,
            collection=collection,
            embedder=embedder,
        )
        context = build_context(retrieval, **build_kwargs)
        return context, retrieval

    except RuntimeError as exc:
        # Vector store empty — degrade gracefully, don't crash chain.py
        logger.warning("RAG unavailable: %s. Proceeding without context.", exc)
        return "", None


# ── Quick test ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    test_queries = [
        ("English", "Show top 10 customers by revenue"),
        ("Hindi",   "राजस्व के अनुसार शीर्ष 10 ग्राहक दिखाओ"),
        ("French",  "Montrez les 10 meilleurs clients par revenus"),
    ]

    for label, query in test_queries:
        print(f"\n{'='*60}")
        print(f"[{label}] {query}")
        print("=" * 60)

        context, retrieval = get_rag_context(query)

        if context:
            print(context)
            print(f"\n── Stats ──")
            print(f"  Chars    : {len(context)}")
            print(f"  Chunks   : {retrieval.total}")
            print(f"  Language : {retrieval.language.language_name}")
        else:
            print("⚠️  No context retrieved (vector store may be empty).")