"""
rag/indexing.py
---------------
Indexes knowledge/ directory files into ChromaDB.

Reads markdown/text files from:
    knowledge/schema_docs/      ← table & column descriptions
    knowledge/business_rules/   ← business logic
    knowledge/glossary/         ← term definitions
    knowledge/kpi_definitions/  ← KPI docs

Chunks each file, embeds via NVIDIA NIM, and upserts into ChromaDB.
Safe to re-run — upsert prevents duplicates.

Usage:
    # Index everything
    python -m rag.indexing

    # Index a specific source type only
    python -m rag.indexing --source schema
    python -m rag.indexing --source glossary
    python -m rag.indexing --source business_rules
    python -m rag.indexing --source kpi

    # Wipe and re-index from scratch
    python -m rag.indexing --reset
"""

import os
import re
import logging
import argparse
import hashlib
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from rag.embeddings import get_embedder
from rag.vector_store import get_chroma_client, get_vector_store, add_documents, reset_collection

load_dotenv()

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

CHUNK_SIZE    = int(os.getenv("CHUNK_SIZE",   "400"))   # target tokens per chunk
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "50"))   # overlap between chunks

# Map source_type → knowledge/ subdirectory
SOURCE_PATHS: dict[str, str] = {
    "schema":         os.getenv("SCHEMA_DOCS_PATH",     "./knowledge/schema_docs"),
    "business_rules": os.getenv("BUSINESS_RULES_PATH",  "./knowledge/business_rules"),
    "glossary":       os.getenv("GLOSSARY_PATH",        "./knowledge/glossary"),
    "kpi":            os.getenv("KPI_DEFINITIONS_PATH", "./knowledge/kpi_definitions"),
}

# File extensions to index
SUPPORTED_EXTENSIONS = {".md", ".txt"}


# ── Text chunking ──────────────────────────────────────────────────────────────

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """
    Split text into overlapping chunks by word count.

    Tries to split on paragraph boundaries first (double newline),
    then falls back to word-level sliding window.

    Args:
        text:       Input text to split.
        chunk_size: Target words per chunk.
        overlap:    Words to repeat at the start of each new chunk.

    Returns:
        List of text chunks.
    """
    # Normalize whitespace
    text = re.sub(r"\n{3,}", "\n\n", text.strip())

    # Try paragraph-based splitting first
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks: list[str] = []
    current_words: list[str] = []

    for para in paragraphs:
        para_words = para.split()

        # If a single paragraph exceeds chunk_size, split it further
        if len(para_words) > chunk_size:
            # Flush current buffer first
            if current_words:
                chunks.append(" ".join(current_words))
                current_words = current_words[-overlap:] if overlap else []

            # Sliding window over long paragraph
            for i in range(0, len(para_words), chunk_size - overlap):
                window = para_words[i : i + chunk_size]
                if window:
                    chunks.append(" ".join(window))
            current_words = para_words[-(overlap):] if overlap else []
            continue

        # Would adding this paragraph exceed chunk_size?
        if len(current_words) + len(para_words) > chunk_size:
            if current_words:
                chunks.append(" ".join(current_words))
                current_words = current_words[-overlap:] if overlap else []

        current_words.extend(para_words)

    # Flush remaining words
    if current_words:
        chunks.append(" ".join(current_words))

    return [c for c in chunks if c.strip()]


# ── ID generation ──────────────────────────────────────────────────────────────

def make_chunk_id(source_type: str, filename: str, chunk_index: int) -> str:
    """
    Generate a stable, unique ID for a document chunk.

    Uses source_type + filename + chunk index so re-indexing the same
    file always produces the same IDs → upsert deduplicates cleanly.

    Returns:
        String ID like "schema__customers__0"
    """
    stem = Path(filename).stem
    # Sanitize for ChromaDB (alphanumeric + underscores only)
    stem = re.sub(r"[^a-zA-Z0-9_-]", "_", stem)
    return f"{source_type}__{stem}__{chunk_index}"


# ── Single file indexer ────────────────────────────────────────────────────────

def index_file(
    filepath: Path,
    source_type: str,
    collection,
    embedder,
) -> int:
    """
    Read, chunk, and index a single file into ChromaDB.

    Args:
        filepath:    Path to the file.
        source_type: Category label (schema, glossary, kpi, business_rules).
        collection:  ChromaDB collection.
        embedder:    NVIDIAEmbeddings instance.

    Returns:
        Number of chunks indexed from this file.
    """
    try:
        text = filepath.read_text(encoding="utf-8").strip()
    except Exception as exc:
        logger.error("❌ Could not read %s: %s", filepath, exc)
        return 0

    if not text:
        logger.warning("⚠️  Skipping empty file: %s", filepath.name)
        return 0

    chunks = chunk_text(text)
    if not chunks:
        logger.warning("⚠️  No chunks produced from: %s", filepath.name)
        return 0

    # Build metadata for each chunk
    file_hash = hashlib.md5(text.encode()).hexdigest()[:8]

    metadatas = [
        {
            "source_type": source_type,
            "filename":    filepath.name,
            "file_hash":   file_hash,
            "chunk_index": i,
            "total_chunks": len(chunks),
        }
        for i in range(len(chunks))
    ]

    ids = [make_chunk_id(source_type, filepath.name, i) for i in range(len(chunks))]

    add_documents(collection, texts=chunks, metadatas=metadatas, ids=ids, embedder=embedder)

    logger.info(
        "  ✅ %s → %d chunk(s) indexed. [%s]",
        filepath.name, len(chunks), source_type,
    )
    return len(chunks)


# ── Directory indexer ──────────────────────────────────────────────────────────

def index_directory(
    source_type: str,
    collection,
    embedder,
) -> dict:
    """
    Index all supported files from a knowledge/ subdirectory.

    Args:
        source_type: One of: schema, business_rules, glossary, kpi.
        collection:  ChromaDB collection.
        embedder:    NVIDIAEmbeddings instance.

    Returns:
        Dict with files_found, files_indexed, total_chunks.
    """
    directory = Path(SOURCE_PATHS[source_type])

    if not directory.exists():
        logger.warning("⚠️  Directory not found, skipping: %s", directory)
        return {"files_found": 0, "files_indexed": 0, "total_chunks": 0}

    files = [
        f for f in sorted(directory.iterdir())
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
    ]

    if not files:
        logger.warning("⚠️  No .md or .txt files found in: %s", directory)
        return {"files_found": 0, "files_indexed": 0, "total_chunks": 0}

    logger.info("📂 Indexing [%s] from %s (%d file(s))", source_type, directory, len(files))

    total_chunks   = 0
    files_indexed  = 0

    for filepath in files:
        chunks = index_file(filepath, source_type, collection, embedder)
        if chunks > 0:
            total_chunks  += chunks
            files_indexed += 1

    return {
        "files_found":   len(files),
        "files_indexed": files_indexed,
        "total_chunks":  total_chunks,
    }


# ── Main indexing entry point ──────────────────────────────────────────────────

def run_indexing(
    source_filter: Optional[str] = None,
    reset: bool = False,
) -> dict:
    """
    Index all (or one) knowledge source(s) into ChromaDB.

    Args:
        source_filter: Index only this source type (None = index all).
        reset:         If True, wipe the collection before indexing.

    Returns:
        Summary dict with per-source and total stats.
    """
    client     = get_chroma_client()
    embedder   = get_embedder()

    if reset:
        logger.warning("🗑️  --reset flag set. Wiping collection before indexing.")
        reset_collection(client=client)

    collection = get_vector_store(client=client)

    sources = (
        {source_filter: SOURCE_PATHS[source_filter]}
        if source_filter
        else SOURCE_PATHS
    )

    summary = {}
    grand_total_chunks = 0

    for source_type in sources:
        result = index_directory(source_type, collection, embedder)
        summary[source_type] = result
        grand_total_chunks  += result["total_chunks"]

    summary["__total_chunks__"] = grand_total_chunks
    summary["__collection_count__"] = collection.count()

    return summary


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s:%(name)s:%(message)s",
    )

    parser = argparse.ArgumentParser(description="Index knowledge/ docs into ChromaDB.")
    parser.add_argument(
        "--source",
        choices=list(SOURCE_PATHS.keys()),
        default=None,
        help="Index only this source type (default: index all).",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Wipe the collection before indexing.",
    )
    args = parser.parse_args()

    print("\n🔍 AI SQL Assistant — RAG Indexing")
    print("=" * 45)

    if args.reset:
        print("⚠️  Reset flag set — collection will be wiped.\n")

    summary = run_indexing(source_filter=args.source, reset=args.reset)

    print("\n── Indexing Summary ──────────────────────────")
    for source, stats in summary.items():
        if source.startswith("__"):
            continue
        print(
            f"  {source:<18} "
            f"files: {stats['files_indexed']}/{stats['files_found']}  "
            f"chunks: {stats['total_chunks']}"
        )

    print(f"\n  Total chunks indexed : {summary['__total_chunks__']}")
    print(f"  Collection count     : {summary['__collection_count__']}")
    print("\n✅ Indexing complete.\n")