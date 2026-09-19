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


def _bm25_score(query_tokens: List[str], chunk: str, doc_freq: Dict[str, int], total_chunks: int) -> float:
    """
    Lightweight, robust BM25 passage scoring.
    k1=1.5, b=0.75 standard parameters with non-negative smoothed IDF.
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

    N = max(total_chunks, 1)
    for qt in query_tokens:
        if qt not in tf_map:
            continue
        tf = tf_map[qt]
        n_q = doc_freq.get(qt, 1)
        # Smoothed positive Lucene/BM25 IDF
        idf = math.log(1.0 + (N - n_q + 0.5) / (n_q + 0.5))
        if idf <= 0:
            idf = math.log(1.0 + (N + 1.0) / (n_q + 1.0))
        tf_norm = (tf * (k1 + 1.0)) / (tf + k1 * (1.0 - b + b * dl / avg_len))
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
        "Keep answers natural, conversational, and under 3 sentences. "
        "Always respond in pure plain text without emojis, emoticons, logos, bullet points, or markdown formatting."
    )

    metadata: Dict[str, Any] = {
        "profile_id": profile_id,
        "name": name,
        "persona": persona.lower().strip() if persona else "female",
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


def delete_document(profile_id: str, doc_id: str) -> Optional[Dict[str, Any]]:
    """
    Remove an indexed document and all its chunks from a profile's index.

    Args:
        profile_id: Target profile.
        doc_id: Unique document ID to remove.

    Returns:
        Updated profile metadata dict, or None if profile not found.
    """
    meta = get_profile(profile_id)
    if meta is None:
        return None

    # Filter out document from metadata
    orig_docs = meta.get("documents", [])
    meta["documents"] = [d for d in orig_docs if d.get("doc_id") != doc_id]

    # Rebuild index without this document's chunks
    idx_path = _index_path(profile_id)
    if idx_path.exists():
        idx_data: Dict[str, Any] = json.loads(idx_path.read_text("utf-8"))
        remaining_chunks = [c for c in idx_data.get("chunks", []) if c.get("doc_id") != doc_id]

        new_doc_freq: Dict[str, int] = {}
        for chunk_item in remaining_chunks:
            tokens = set(_tokenize(chunk_item["text"]))
            for t in tokens:
                new_doc_freq[t] = new_doc_freq.get(t, 0) + 1

        _index_path(profile_id).write_text(
            json.dumps(
                {
                    "chunks": remaining_chunks,
                    "doc_freq": new_doc_freq,
                    "num_docs": len(meta["documents"]),
                },
                ensure_ascii=False,
            ),
            "utf-8",
        )

    _metadata_path(profile_id).write_text(json.dumps(meta, indent=2), "utf-8")
    logger.info(
        "Document deleted",
        extra={"profile_id": profile_id, "doc_id": doc_id},
    )
    return meta


STOP_WORDS = {
    "what", "is", "are", "the", "a", "an", "and", "or", "to", "of", "in", "for", "on",
    "with", "at", "by", "from", "about", "tell", "me", "can", "you", "do", "how", "much",
    "many", "i", "my", "your", "we", "our", "it", "its", "please", "does", "did", "have",
    "has", "had", "will", "would", "could", "should", "any", "some", "that", "this"
}


def extract_grounded_answer(chunks: List[str], query: str, max_sentences: int = 2) -> str:
    """
    Directly extracts the most relevant, grounded answer sentences from top chunks
    matching the query keywords when LLM is unavailable or for instant local responses.
    """
    if not chunks:
        return "No relevant information found in the document knowledge base."

    query_tokens = set(_tokenize(query))
    meaningful_tokens = {t for t in query_tokens if t not in STOP_WORDS and len(t) > 1}
    if not meaningful_tokens:
        meaningful_tokens = query_tokens

    candidates = []
    for chunk in chunks:
        lines = [line.strip() for line in chunk.split("\n") if line.strip()]
        for line in lines:
            # Skip divider lines and uppercase numbered section headers
            if line.startswith("=") or re.match(r"^\d+\.\s+[A-Z\s&/]+$", line):
                continue
            if len(line) < 35 and line.isupper():
                continue

            sub_sentences = re.split(r"(?<=[.!?])\s+", line)
            for s in sub_sentences:
                s_clean = s.strip().lstrip("-•* ").strip()
                if len(s_clean) >= 15:
                    s_tokens = set(_tokenize(s_clean))
                    matched_tokens = s_tokens & meaningful_tokens
                    overlap = len(matched_tokens)
                    if overlap > 0:
                        score = float(overlap)
                        if any(char.isdigit() for char in s_clean):
                            score += 0.5
                        if ":" in s_clean:
                            score += 0.5
                        candidates.append((score, len(s_clean), s_clean))

    if not candidates:
        for chunk in chunks:
            for line in chunk.split("\n"):
                clean = line.strip().lstrip("-•* ").strip()
                if len(clean) > 20 and not clean.startswith("=") and not re.match(r"^\d+\.\s+[A-Z\s&/]+$", clean):
                    return clean
        return chunks[0][:200].strip()

    # Sort candidates by score descending, then length
    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)

    selected = []
    seen = set()
    for _, _, sentence in candidates:
        norm = sentence.lower()[:40]
        if norm not in seen:
            seen.add(norm)
            selected.append(sentence)
            if len(selected) >= max_sentences:
                break

    answer = " ".join(selected)
    if answer and answer[-1] not in ".!?":
        answer += "."
    return answer


def retrieve_context_with_sources(profile_id: str, query: str, top_k: int = 4, min_score: float = 0.25) -> Dict[str, Any]:
    """
    Retrieve relevant text chunks with source metadata, formatted context string,
    and relevance flag.

    Returns:
        Dict with "context" (str), "sources" (List[Dict[str, Any]]),
        "has_context" (bool), "max_score" (float), and "top_chunks" (List[str]).
    """
    empty_result = {
        "context": "",
        "sources": [],
        "has_context": False,
        "max_score": 0.0,
        "top_chunks": [],
    }

    idx_path = _index_path(profile_id)
    if not idx_path.exists():
        return empty_result

    meta = get_profile(profile_id)
    doc_map = {d["doc_id"]: d.get("filename", "document") for d in (meta.get("documents", []) if meta else [])}

    idx_data: Dict[str, Any] = json.loads(idx_path.read_text("utf-8"))
    chunks: List[Dict] = idx_data.get("chunks", [])
    doc_freq: Dict[str, int] = idx_data.get("doc_freq", {})
    num_docs: int = idx_data.get("num_docs", 1)

    if not chunks:
        return empty_result

    query_tokens = _tokenize(query)
    if not query_tokens:
        return empty_result

    meaningful_tokens = [t for t in query_tokens if t not in STOP_WORDS and len(t) > 1]
    tokens_to_score = meaningful_tokens if meaningful_tokens else query_tokens

    total_chunks = len(chunks)
    scored = []
    for c in chunks:
        score = _bm25_score(tokens_to_score, c["text"], doc_freq, total_chunks)
        if score >= min_score:
            scored.append((score, c))

    scored.sort(key=lambda x: x[0], reverse=True)
    top_scored = scored[:top_k]

    if not top_scored:
        return empty_result

    max_score = top_scored[0][0]
    top_chunks = [c["text"] for _, c in top_scored]
    sources = [
        {
            "doc_id": c.get("doc_id"),
            "filename": doc_map.get(c.get("doc_id"), "document"),
            "score": round(score, 3),
            "snippet": c["text"][:160] + "..." if len(c["text"]) > 160 else c["text"],
        }
        for score, c in top_scored
    ]

    context = "\n---\n".join(top_chunks)
    formatted = f"[Relevant document context]\n{context}\n[End of context]"
    return {
        "context": formatted,
        "sources": sources,
        "has_context": True,
        "max_score": round(max_score, 3),
        "top_chunks": top_chunks,
    }


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
    result = retrieve_context_with_sources(profile_id, query, top_k)
    return result["context"]


