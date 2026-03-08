"""
rag.py
Document ingestion and RAG query pipeline for the MVP dashboard.

Storage: SQLite at data/embeddings.db (local, gitignored).
Embeddings: via LLM gateway /v1/embeddings (openai/text-embedding-3-small, 1536 dims).
Similarity: cosine via numpy (no pgvector needed on laptop).
"""

import io
import json
import os
import sqlite3
import struct
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from services import llm_chat, llm_embed

DB_PATH      = Path(__file__).parent / "data" / "embeddings.db"
CHUNK_CHARS  = 2000   # ~500 tokens
OVERLAP_CHARS = 200   # ~50 tokens
TOP_K        = 5


# ── Database ──────────────────────────────────────────────────────────────────

def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS documents (
                doc_id       TEXT PRIMARY KEY,
                filename     TEXT NOT NULL,
                uploaded_at  TEXT NOT NULL,
                chunk_count  INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS chunks (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_id      TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                chunk_text  TEXT NOT NULL,
                embedding   BLOB NOT NULL,
                FOREIGN KEY (doc_id) REFERENCES documents(doc_id)
            );
        """)


# ── Text extraction ───────────────────────────────────────────────────────────

def extract_text(filename: str, content: bytes) -> str:
    """Extract plain text from PDF, DOCX, TXT, or MD file bytes."""
    ext = Path(filename).suffix.lower()

    if ext == ".pdf":
        import pdfplumber
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            pages = [p.extract_text() or "" for p in pdf.pages]
        return "\n\n".join(p for p in pages if p.strip())

    if ext in (".docx",):
        import docx
        doc = docx.Document(io.BytesIO(content))
        return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())

    # TXT, MD, and anything else -- treat as UTF-8 text
    return content.decode("utf-8", errors="replace")


# ── Chunking ──────────────────────────────────────────────────────────────────

def chunk_text(text: str) -> list[str]:
    """Split text into overlapping character chunks."""
    text = text.strip()
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = start + CHUNK_CHARS
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start += CHUNK_CHARS - OVERLAP_CHARS
    return chunks


# ── Embedding helpers ─────────────────────────────────────────────────────────

def _vec_to_blob(vec: list[float]) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)


def _blob_to_vec(blob: bytes) -> np.ndarray:
    n = len(blob) // 4
    return np.array(struct.unpack(f"{n}f", blob), dtype=np.float32)


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


# ── Ingest ────────────────────────────────────────────────────────────────────

def ingest_document(filename: str, content: bytes) -> dict:
    """
    Extract, chunk, embed, and store a document.
    Returns {doc_id, filename, chunk_count}.
    Raises on extraction or embedding failure.
    """
    text = extract_text(filename, content)
    if not text.strip():
        raise ValueError(f"No text could be extracted from {filename!r}")

    chunks = chunk_text(text)
    if not chunks:
        raise ValueError(f"Document produced no chunks after extraction")

    # Embed all chunks in one gateway call (batched)
    vectors = llm_embed(chunks)
    if len(vectors) != len(chunks):
        raise RuntimeError(f"Embedding count mismatch: {len(vectors)} vectors for {len(chunks)} chunks")

    doc_id = str(uuid.uuid4())
    now    = datetime.now(timezone.utc).isoformat()

    with _conn() as conn:
        conn.execute(
            "INSERT INTO documents (doc_id, filename, uploaded_at, chunk_count) VALUES (?, ?, ?, ?)",
            (doc_id, filename, now, len(chunks))
        )
        conn.executemany(
            "INSERT INTO chunks (doc_id, chunk_index, chunk_text, embedding) VALUES (?, ?, ?, ?)",
            [
                (doc_id, i, chunk, _vec_to_blob(vec))
                for i, (chunk, vec) in enumerate(zip(chunks, vectors))
            ]
        )

    return {"doc_id": doc_id, "filename": filename, "chunk_count": len(chunks)}


# ── Query ─────────────────────────────────────────────────────────────────────

def query_rag(question: str) -> dict:
    """
    Embed the question, find top-K similar chunks, call LLM with context.
    Returns {answer, sources: [{doc_id, filename, chunk_index, chunk_text, score}]}.
    """
    with _conn() as conn:
        rows = conn.execute(
            "SELECT c.doc_id, c.chunk_index, c.chunk_text, c.embedding, d.filename "
            "FROM chunks c JOIN documents d ON c.doc_id = d.doc_id"
        ).fetchall()

    if not rows:
        return {
            "answer": "No documents are indexed yet. Upload a document on the Documents tab first.",
            "sources": [],
        }

    # Embed question
    q_vec = np.array(llm_embed([question])[0], dtype=np.float32)

    # Score all chunks
    scored = []
    for row in rows:
        chunk_vec = _blob_to_vec(row["embedding"])
        score = _cosine(q_vec, chunk_vec)
        scored.append({
            "doc_id":      row["doc_id"],
            "filename":    row["filename"],
            "chunk_index": row["chunk_index"],
            "chunk_text":  row["chunk_text"],
            "score":       score,
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    top = scored[:TOP_K]

    # Build prompt
    context_parts = [
        f"[Source {i+1}: {c['filename']}, chunk {c['chunk_index']+1}]\n{c['chunk_text']}"
        for i, c in enumerate(top)
    ]
    context = "\n\n---\n\n".join(context_parts)

    messages = [
        {
            "role": "system",
            "content": (
                "You are a helpful assistant. Answer the user's question using only the "
                "provided document excerpts. If the answer is not clearly supported by the "
                "excerpts, say so explicitly rather than guessing."
            ),
        },
        {
            "role": "user",
            "content": f"Document excerpts:\n\n{context}\n\nQuestion: {question}",
        },
    ]

    answer = llm_chat(messages, max_output_tokens=1024)

    # Return sources with score rounded for display
    sources = [
        {**c, "score": round(c["score"], 4)}
        for c in top
        if c["score"] > 0.3  # suppress near-zero matches
    ]

    return {"answer": answer, "sources": sources}


# ── Document management ───────────────────────────────────────────────────────

def list_documents() -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT doc_id, filename, uploaded_at, chunk_count FROM documents ORDER BY uploaded_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def delete_document(doc_id: str) -> bool:
    with _conn() as conn:
        conn.execute("DELETE FROM chunks WHERE doc_id = ?", (doc_id,))
        result = conn.execute("DELETE FROM documents WHERE doc_id = ?", (doc_id,))
    return result.rowcount > 0
