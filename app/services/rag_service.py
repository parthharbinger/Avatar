"""
RAG Service — manages avatar knowledge profiles.

Each profile stores:
  - metadata (name, persona, created_at, document list)
  - chunked text index for fast keyword retrieval (no external vector DB needed)

Retrieval uses a simple TF-IDF + keyword overlap hybrid sufficient for 
document-expert use cases within Groq's context window.
"""
import json
import math
import re
import uuid
import shutil
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any

from app.logging_config import get_logger

logger = get_logger(__name__)

# ── Paths ───────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent.parent  # Avatar/
DATA_DIR = BASE_DIR / "data" / "profiles"


# ── Internal helpers ────────────────────────────────────────────────────────────

def _profile_dir(profile_id: str) -> Path:
    return DATA_DIR / profile_id


def _metadata_path(profile_id: str) -> Path:
    return _profile_dir(profile_id) / "metadata.json"


def _index_path(profile_id: str) -> Path:
    return _profile_dir(profile_id) / "index.json"


def _tokenize(text: str) -> List[str]:
    """Simple lowercase word tokenizer, strips punctuation."""
    return re.findall(r"[a-z0-9]+", text.lower())


def _bm25_score(query_tokens: List[str], chunk: str, doc_freq: Dict[str, int], num_docs: int) -> float:
    """
    Lightweight BM25 scoring.
    k1=1.5, b=0.75 standard parameters.
    """
    k1, b = 1.5, 0.75
    chunk_tokens = _tokenize(chunk)
    if not chunk_tokens:
        return 0.0
    avg_len = 120  # estimated average chunk token length
    dl = len(chunk_tokens)
    score = 0.0
    tf_map: Dict[str, int] = {}
    for t in chunk_tokens:
        tf_map[t] = tf_map.get(t, 0) + 1

    for qt in query_tokens:
        if qt not in tf_map:
            continue
        tf = tf_map[qt]
        idf_num = num_docs - doc_freq.get(qt, 0) + 0.5
        idf_den = doc_freq.get(qt, 0) + 0.5
        idf = math.log((idf_num / idf_den) + 1)
        tf_norm = (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * dl / avg_len))
        score += idf * tf_norm

    return score


# ── Public API ──────────────────────────────────────────────────────────────────

def list_profiles() -> List[Dict[str, Any]]:
    """Return metadata for all saved profiles, sorted newest first."""
    if not DATA_DIR.exists():
        return []
    results = []
    for d in DATA_DIR.iterdir():
        meta_path = d / "metadata.json"
        if meta_path.exists():
            try:
                results.append(json.loads(meta_path.read_text("utf-8")))
            except Exception:
                pass
    results.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return results


def get_profile(profile_id: str) -> Optional[Dict[str, Any]]:
    """Return profile metadata dict, or None if not found."""
    mp = _metadata_path(profile_id)
    if not mp.exists():
        return None
    return json.loads(mp.read_text("utf-8"))


def create_profile(name: str, persona: str = "female", system_prompt: Optional[str] = None) -> Dict[str, Any]:
    """
    Create a new avatar expert profile.

    Args:
        name: Human-readable profile name (e.g. "AI Expert Adam").
        persona: Avatar visual preset — 'male' | 'female'.
        system_prompt: Override system prompt. Auto-generated if omitted.

    Returns:
        Profile metadata dict with new `profile_id`.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    profile_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    auto_prompt = (
        f"You are {name}, an intelligent AI expert. "
        "Answer questions accurately and concisely based on the provided document knowledge. "
        "If the question relates to the documents you have been given, use that knowledge. "
        "Keep answers natural and under 3 sentences."
    )

    metadata: Dict[str, Any] = {
        "profile_id": profile_id,
        "name": name,
        "persona": "male" if persona.lower() in ("male", "david", "adam") else "female",
        "system_prompt": system_prompt or auto_prompt,
        "created_at": created_at,
        "documents": [],      # list of {doc_id, filename, chunk_count, uploaded_at}
    }

    pd = _profile_dir(profile_id)
    pd.mkdir(parents=True, exist_ok=True)
    _metadata_path(profile_id).write_text(json.dumps(metadata, indent=2), "utf-8")
    # Empty index
    _index_path(profile_id).write_text(json.dumps({"chunks": [], "doc_freq": {}, "num_docs": 0}), "utf-8")

    logger.info("Profile created", extra={"profile_id": profile_id, "profile_name": name})
    return metadata


def delete_profile(profile_id: str) -> bool:
    """Delete a profile and all its documents. Returns True if deleted, False if not found."""
    pd = _profile_dir(profile_id)
    if not pd.exists():
        return False
    shutil.rmtree(pd)
    logger.info("Profile deleted", extra={"profile_id": profile_id})
    return True


def index_document(profile_id: str, filepath: str | Path, filename: str, chunks: List[str]) -> Dict[str, Any]:
    """
    Add a document's chunks to the profile's retrieval index.

    Args:
        profile_id: Target profile.
        filepath: Path to the stored document file.
        filename: Original file name (for display).
        chunks: List of text chunks from document_parser.

    Returns:
        Updated profile metadata.
    """
    meta = get_profile(profile_id)
    if meta is None:
        raise ValueError(f"Profile {profile_id} not found")

    # Load existing index
    idx_data: Dict[str, Any] = json.loads(_index_path(profile_id).read_text("utf-8"))
    existing_chunks: List[Dict] = idx_data.get("chunks", [])
    doc_freq: Dict[str, int] = idx_data.get("doc_freq", {})
    num_docs: int = idx_data.get("num_docs", 0)

    doc_id = str(uuid.uuid4())

    # Add chunks with doc_id label
    for i, chunk in enumerate(chunks):
        tokens = set(_tokenize(chunk))
        for t in tokens:
            doc_freq[t] = doc_freq.get(t, 0) + 1
        existing_chunks.append({"doc_id": doc_id, "chunk_idx": i, "text": chunk})

    num_docs += 1

    # Save updated index
    _index_path(profile_id).write_text(
        json.dumps({"chunks": existing_chunks, "doc_freq": doc_freq, "num_docs": num_docs}, ensure_ascii=False),
        "utf-8",
    )

    # Update metadata
    meta["documents"].append({
        "doc_id": doc_id,
        "filename": filename,
        "chunk_count": len(chunks),
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    })
    _metadata_path(profile_id).write_text(json.dumps(meta, indent=2), "utf-8")

    logger.info(
        "Document indexed",
        extra={"profile_id": profile_id, "doc_id": doc_id, "doc_filename": filename, "chunks": len(chunks)},
    )
    return meta


def retrieve_context(profile_id: str, query: str, top_k: int = 4) -> str:
    """
    Retrieve the most relevant text chunks for a query using BM25 scoring.

    Args:
        profile_id: Profile to query.
        query: User's natural-language question.
        top_k: Number of top chunks to return.

    Returns:
        Formatted context string ready for LLM injection, or empty string if no docs.
    """
    idx_path = _index_path(profile_id)
    if not idx_path.exists():
        return ""

    idx_data: Dict[str, Any] = json.loads(idx_path.read_text("utf-8"))
    chunks: List[Dict] = idx_data.get("chunks", [])
    doc_freq: Dict[str, int] = idx_data.get("doc_freq", {})
    num_docs: int = idx_data.get("num_docs", 1)

    if not chunks:
        return ""

    query_tokens = _tokenize(query)
    if not query_tokens:
        return ""

    # Score all chunks
    scored = [
        (_bm25_score(query_tokens, c["text"], doc_freq, max(num_docs, 1)), c["text"])
        for c in chunks
    ]
    scored.sort(key=lambda x: x[0], reverse=True)

    top_chunks = [text for score, text in scored[:top_k] if score > 0]

    if not top_chunks:
        return ""

    context = "\n---\n".join(top_chunks)
    return f"[Relevant document context]\n{context}\n[End of context]"
