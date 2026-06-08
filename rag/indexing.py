"""
rag/indexing.py
───────────────
Builds (or refreshes) the ChromaDB vector index from two sources:

  1. Live PostgreSQL schema  — extracted via db.get_schema() and split
     per-table so each table is a focused, independently-retrievable chunk.

  2. knowledge/ directory   — Markdown files under schema_docs/, glossary/,
     kpi_definitions/, and business_rules/ are read and indexed with their
     source type recorded in metadata.

Run once after setup, then re-run whenever the schema or knowledge files change:

    python -m rag.indexing           # indexes everything
    python -m rag.indexing --schema  # schema only
    python -m rag.indexing --docs    # knowledge/ docs only
    python -m rag.indexing --reset   # wipe and re-index everything

Public API used by app.py (index-on-connect feature):
    index_schema(db)
    index_knowledge_docs()
    is_index_empty() -> bool
"""

import os
import re
import hashlib
import logging
import argparse
from pathlib import Path
from typing import List, Tuple

logger = logging.getLogger(__name__)

KNOWLEDGE_DIR = Path(__file__).parent.parent / "knowledge"

SOURCE_TYPE_MAP = {
    "schema_docs":      "schema",
    "glossary":         "glossary",
    "kpi_definitions":  "kpi",
    "business_rules":   "business_rule",
}


# ── Public API ────────────────────────────────────────────────────────────────

def is_index_empty() -> bool:
    """Return True if the ChromaDB collection has no documents."""
    try:
        from rag.vector_store import get_collection   # noqa: PLC0415
        col = get_collection()
        return col is None or col.count() == 0
    except Exception:
        return True


def index_schema(db) -> int:
    """
    Extract per-table DDL from a connected SQLDatabase and upsert into ChromaDB.
    Returns the number of chunks indexed (0 on failure).
    """
    try:
        from db import get_schema                     # noqa: PLC0415
        from rag.embeddings import embed_batch        # noqa: PLC0415
        from rag.vector_store import add_chunks       # noqa: PLC0415
    except ImportError as exc:
        logger.error("Missing dependency for index_schema: %s", exc)
        return 0

    try:
        full_schema = get_schema(db)
        table_chunks = _split_schema_by_table(full_schema)

        if not table_chunks:
            logger.warning("No table chunks extracted from schema.")
            return 0

        chunks, ids, metas = [], [], []
        for table_name, ddl in table_chunks:
            doc = _format_schema_chunk(table_name, ddl)
            chunk_id = f"schema__{table_name}__0"
            fhash = hashlib.md5(doc.encode()).hexdigest()[:8]
            chunks.append(doc)
            ids.append(chunk_id)
            metas.append({
                "source_type": "schema",
                "filename": f"{table_name}.md",
                "table_name": table_name,
                "file_hash": fhash,
                "chunk_index": 0,
                "total_chunks": 1,
            })

        embeddings = embed_batch(chunks)
        ok = add_chunks(chunks, ids, metas, embeddings)
        count = len(chunks) if ok else 0
        logger.info("Schema indexing: %d table chunks upserted.", count)
        return count

    except Exception as exc:
        logger.error("index_schema failed: %s", exc)
        return 0


def index_knowledge_docs() -> int:
    """
    Walk knowledge/ subdirectories and index all .md files.
    Returns total chunks indexed.
    """
    try:
        from rag.embeddings import embed_batch   # noqa: PLC0415
        from rag.vector_store import add_chunks  # noqa: PLC0415
    except ImportError as exc:
        logger.error("Missing dependency for index_knowledge_docs: %s", exc)
        return 0

    total = 0
    for subdir, source_type in SOURCE_TYPE_MAP.items():
        folder = KNOWLEDGE_DIR / subdir
        if not folder.exists():
            continue

        md_files = list(folder.glob("*.md"))
        if not md_files:
            continue

        chunks, ids, metas = [], [], []
        for md_path in md_files:
            text = md_path.read_text(encoding="utf-8").strip()
            if not text:
                continue

            fhash = hashlib.md5(text.encode()).hexdigest()[:8]
            chunk_id = f"{source_type}__{md_path.stem}__0"
            chunks.append(text)
            ids.append(chunk_id)
            metas.append({
                "source_type": source_type,
                "filename": md_path.name,
                "file_hash": fhash,
                "chunk_index": 0,
                "total_chunks": 1,
            })

        if chunks:
            embeddings = embed_batch(chunks)
            ok = add_chunks(chunks, ids, metas, embeddings)
            n = len(chunks) if ok else 0
            logger.info("Indexed %d docs from knowledge/%s.", n, subdir)
            total += n

    return total


# ── Schema splitting helpers ──────────────────────────────────────────────────

def _split_schema_by_table(schema: str) -> List[Tuple[str, str]]:
    """
    Split a full DDL schema string into (table_name, ddl_block) pairs.
    Handles both CREATE TABLE and plain column-list formats.
    """
    # Match CREATE TABLE blocks
    pattern = re.compile(
        r"(CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`\"]?(\w+)[`\"]?\s*\(.*?\);)",
        re.IGNORECASE | re.DOTALL,
    )
    matches = pattern.findall(schema)
    if matches:
        return [(name, ddl) for ddl, name in matches]

    # Fallback: split on blank lines and try to extract table names
    blocks = [b.strip() for b in schema.split("\n\n") if b.strip()]
    results = []
    for block in blocks:
        m = re.search(r"(?:TABLE|table)\s+[`\"]?(\w+)[`\"]?", block)
        name = m.group(1) if m else f"block_{len(results)}"
        results.append((name, block))
    return results


def _format_schema_chunk(table_name: str, ddl: str) -> str:
    """Format a schema chunk for embedding — clean and readable."""
    # Extract column names from DDL for the summary line
    col_matches = re.findall(r"^\s+[`\"]?(\w+)[`\"]?\s+\w+", ddl, re.MULTILINE)
    cols = ", ".join(col_matches[:10])
    suffix = ", …" if len(col_matches) > 10 else ""

    return (
        f"# Table: {table_name}\n"
        f"Columns: {cols}{suffix}\n\n"
        f"{ddl.strip()}"
    )


# ── CLI entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Index schema and/or knowledge docs into ChromaDB.")
    parser.add_argument("--schema",  action="store_true", help="Index DB schema only")
    parser.add_argument("--docs",    action="store_true", help="Index knowledge/ docs only")
    parser.add_argument("--reset",   action="store_true", help="Wipe collection before indexing")
    args = parser.parse_args()

    do_all = not (args.schema or args.docs)

    if args.reset:
        from rag.vector_store import reset_collection
        reset_collection()

    if do_all or args.schema:
        try:
            from db import get_db
            db = get_db()
            n = index_schema(db)
            print(f"✅ Schema: {n} chunks indexed.")
        except Exception as e:
            print(f"❌ Schema indexing failed: {e}")
            sys.exit(1)

    if do_all or args.docs:
        n = index_knowledge_docs()
        print(f"✅ Knowledge docs: {n} chunks indexed.")

    # Summary
    from rag.vector_store import get_collection
    col = get_collection()
    print(f"\n📦 Total documents in ChromaDB: {col.count() if col else 0}")