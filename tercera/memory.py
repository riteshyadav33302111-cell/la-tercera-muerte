"""
Memory: chunks and embeds the codebase into a local vector store (LanceDB).
This gives the ghost RAG-powered recall of its own code.
"""

from __future__ import annotations

import pathlib
from typing import Optional

SOURCE_EXTENSIONS = {
    ".py", ".js", ".ts", ".rb", ".go", ".java", ".rs",
    ".c", ".cpp", ".cs", ".php", ".swift", ".kt", ".ex",
    ".clj", ".hs", ".ml", ".lua", ".sh", ".bash",
}

CHUNK_LINES = 40
CHUNK_OVERLAP = 8


def _chunk_file(path: pathlib.Path, repo_root: pathlib.Path) -> list[dict]:
    """Split a source file into overlapping chunks."""
    try:
        lines = path.read_text(errors="ignore").splitlines()
    except Exception:
        return []

    chunks = []
    i = 0
    while i < len(lines):
        chunk_lines = lines[i: i + CHUNK_LINES]
        text = "\n".join(chunk_lines)
        if text.strip():
            chunks.append({
                "text": text,
                "file": str(path.relative_to(repo_root)),
                "start_line": i + 1,
                "end_line": i + len(chunk_lines),
            })
        i += CHUNK_LINES - CHUNK_OVERLAP

    return chunks


def build_memory(grave: dict, progress_cb=None) -> int:
    """
    Embed the repository's source files into LanceDB.
    Returns the number of chunks stored.
    """
    try:
        import lancedb
        import pyarrow as pa
    except ImportError:
        raise ImportError(
            "Install lancedb and pyarrow: pip install lancedb pyarrow"
        )

    from .llm import embed

    repo_path = pathlib.Path(grave["path"])
    db_path = repo_path / ".tercera" / "memory.lance"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    db = lancedb.connect(str(db_path))

    # Drop old table if it exists
    try:
        db.drop_table("memories")
    except Exception:
        pass

    # Collect all chunks
    all_chunks = []
    for f in repo_path.rglob("*"):
        if (
            f.is_file()
            and f.suffix.lower() in SOURCE_EXTENSIONS
            and ".tercera" not in str(f)
            and f.stat().st_size < 500_000
        ):
            all_chunks.extend(_chunk_file(f, repo_path))

    if not all_chunks:
        return 0

    # Embed chunks
    records = []
    for i, chunk in enumerate(all_chunks):
        if progress_cb:
            progress_cb(i, len(all_chunks), chunk["file"])
        try:
            vector = embed(chunk["text"])
            records.append({
                "vector": vector,
                "text": chunk["text"],
                "file": chunk["file"],
                "start_line": chunk["start_line"],
                "end_line": chunk["end_line"],
            })
        except Exception:
            continue

    if records:
        tbl = db.create_table("memories", data=records)

    return len(records)


def retrieve(query: str, grave: dict, top_k: int = 5) -> list[dict]:
    """
    Retrieve the most relevant code chunks for a query.
    Returns list of {text, file, start_line} dicts.
    """
    try:
        import lancedb
    except ImportError:
        return []

    from .llm import embed

    repo_path = pathlib.Path(grave["path"])
    db_path = repo_path / ".tercera" / "memory.lance"

    if not db_path.exists():
        return []

    try:
        db = lancedb.connect(str(db_path))
        tbl = db.open_table("memories")
        query_vec = embed(query)
        results = tbl.search(query_vec).limit(top_k).to_list()
        return results
    except Exception:
        return []


def memory_exists(grave: dict) -> bool:
    """Check if memory has been built for this grave."""
    db_path = pathlib.Path(grave["path"]) / ".tercera" / "memory.lance"
    return db_path.exists()
