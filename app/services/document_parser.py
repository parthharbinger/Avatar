"""
Document Parser — extracts and chunks text from PDF, DOCX, TXT, and MD files.
Chunks are sentence-boundary-aware with configurable overlap for better retrieval.
"""
import re
import math
from pathlib import Path
from typing import List

from app.logging_config import get_logger

logger = get_logger(__name__)

# ── Chunk settings ─────────────────────────────────────────────────────────────
CHUNK_SIZE = 400        # target characters per chunk
CHUNK_OVERLAP = 80      # overlap between consecutive chunks
MIN_CHUNK = 60          # discard chunks shorter than this


def extract_text(filepath: str | Path) -> str:
    """
    Extract raw text from a supported document file.

    Supported formats: .pdf, .docx, .txt, .md
    Returns the extracted plain text as a single string.
    """
    path = Path(filepath)
    suffix = path.suffix.lower()

    if not path.exists():
        raise FileNotFoundError(f"Document not found: {filepath}")

    logger.info("Extracting text from document", extra={"file": str(path), "type": suffix})

    if suffix == ".pdf":
        return _extract_pdf(path)
    elif suffix == ".docx":
        return _extract_docx(path)
    elif suffix in (".txt", ".md"):
        return path.read_text(encoding="utf-8", errors="replace")
    else:
        raise ValueError(f"Unsupported file type: {suffix}. Supported: pdf, docx, txt, md")


def _extract_pdf(path: Path) -> str:
    """Extract text from PDF using pypdf."""
    try:
        from pypdf import PdfReader
    except ImportError:
        raise RuntimeError("pypdf is required for PDF parsing. Run: uv add pypdf")

    reader = PdfReader(str(path))
    pages = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            pages.append(text)
    return "\n\n".join(pages)


def _extract_docx(path: Path) -> str:
    """Extract text from DOCX using python-docx."""
    try:
        from docx import Document
    except ImportError:
        raise RuntimeError("python-docx is required for DOCX parsing. Run: uv add python-docx")

    doc = Document(str(path))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    # Also extract table cell text
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                if cell.text.strip():
                    paragraphs.append(cell.text.strip())
    return "\n\n".join(paragraphs)


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """
    Split text into overlapping chunks bounded by sentence boundaries.

    Strategy:
    1. Normalize whitespace and collapse excessive blank lines.
    2. Split into sentences using a simple regex boundary detector.
    3. Accumulate sentences into chunks up to `chunk_size` characters.
    4. Overlap the last `overlap` characters between consecutive chunks.
    5. Discard any chunk shorter than MIN_CHUNK.
    """
    if not text or not text.strip():
        return []

    # Normalize whitespace
    text = re.sub(r"\r\n|\r", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = text.strip()

    # Sentence splitting — splits on ". ", "! ", "? ", newlines
    sentence_endings = re.compile(r'(?<=[.!?])\s+|(?<=\n)\n')
    sentences = [s.strip() for s in sentence_endings.split(text) if s.strip()]

    if not sentences:
        return []

    chunks: List[str] = []
    current = ""

    for sentence in sentences:
        # If adding this sentence keeps us under limit, append
        if len(current) + len(sentence) + 1 <= chunk_size:
            current = (current + " " + sentence).strip()
        else:
            # Emit the current chunk
            if len(current) >= MIN_CHUNK:
                chunks.append(current)

            # Start next chunk with overlap from tail of previous
            if overlap > 0 and len(current) > overlap:
                # Carry over the last `overlap` chars; find a word boundary
                tail = current[-overlap:]
                word_break = tail.find(" ")
                overlap_text = tail[word_break + 1:] if word_break != -1 else tail
                current = (overlap_text + " " + sentence).strip()
            else:
                current = sentence

    # Don't forget the last chunk
    if len(current) >= MIN_CHUNK:
        chunks.append(current)

    logger.info(
        "Document chunked",
        extra={"total_chars": len(text), "chunks": len(chunks), "chunk_size": chunk_size},
    )
    return chunks


def parse_document(filepath: str | Path) -> List[str]:
    """
    Full pipeline: extract text from a document and return text chunks for RAG indexing.
    """
    text = extract_text(filepath)
    return chunk_text(text)
