"""
Avatar Profile API — manage named expert avatar profiles with RAG document knowledge bases.

Endpoints:
  POST   /api/v1/profiles                       Create new profile
  GET    /api/v1/profiles                       List all profiles
  GET    /api/v1/profiles/{id}                  Get profile details
  DELETE /api/v1/profiles/{id}                  Delete profile
  POST   /api/v1/profiles/{id}/documents        Upload & index a document
"""
import os
import uuid
from pathlib import Path
from typing import Optional, List, Any, Dict

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, status
from pydantic import BaseModel, Field

from app.logging_config import get_logger
from app.services import rag_service
from app.services.document_parser import parse_document

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/profiles", tags=["Avatar Profiles & RAG"])

# Temporary uploads directory
UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "uploads"
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}


# ── Request / Response models ───────────────────────────────────────────────────

class CreateProfileRequest(BaseModel):
    name: str = Field(description="Display name for this avatar expert, e.g. 'AI Expert Adam'")
    persona: str = Field(default="female", description="Avatar visual preset: 'male' or 'female'")
    system_prompt: Optional[str] = Field(
        default=None,
        description="Custom system prompt. Auto-generated from name if omitted."
    )


class ProfileResponse(BaseModel):
    profile_id: str
    name: str
    persona: str
    system_prompt: str
    created_at: str
    documents: List[Dict[str, Any]]


# ── Endpoints ───────────────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=ProfileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new avatar expert profile",
)
async def create_profile(body: CreateProfileRequest):
    """
    Create a named avatar expert profile. Optionally provide a custom system prompt
    or let the system auto-generate one based on the name. Upload documents separately.
    """
    try:
        meta = rag_service.create_profile(
            name=body.name,
            persona=body.persona,
            system_prompt=body.system_prompt,
        )
        return ProfileResponse(**meta)
    except Exception as e:
        logger.error("Failed to create profile", extra={"error": str(e)})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get(
    "",
    summary="List all avatar expert profiles",
)
async def list_profiles():
    """Return all saved profiles sorted newest first."""
    return rag_service.list_profiles()


@router.get(
    "/{profile_id}",
    response_model=ProfileResponse,
    summary="Get profile details",
)
async def get_profile(profile_id: str):
    """Retrieve metadata for a specific profile including its indexed documents."""
    meta = rag_service.get_profile(profile_id)
    if meta is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found.")
    return ProfileResponse(**meta)


@router.delete(
    "/{profile_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a profile and all its documents",
)
async def delete_profile(profile_id: str):
    """Permanently delete a profile and all its indexed documents."""
    deleted = rag_service.delete_profile(profile_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found.")


@router.post(
    "/{profile_id}/documents",
    summary="Upload and index a document for this profile",
    description=(
        "Upload a PDF, DOCX, TXT, or MD document. "
        "The system extracts text, chunks it, and indexes it for retrieval when users ask questions."
    ),
)
async def upload_document(
    profile_id: str,
    file: UploadFile = File(...),
):
    """
    Upload and index a knowledge document for this avatar expert profile.

    Supported: .pdf, .docx, .txt, .md
    """
    # Validate profile exists
    meta = rag_service.get_profile(profile_id)
    if meta is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found.")

    # Validate file extension
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{suffix}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Save upload temporarily
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    tmp_filename = f"{uuid.uuid4()}{suffix}"
    tmp_path = UPLOAD_DIR / tmp_filename

    try:
        content = await file.read()
        if len(content) == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")
        if len(content) > 20 * 1024 * 1024:  # 20 MB limit
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File too large (max 20 MB).")

        tmp_path.write_bytes(content)

        # Parse & chunk
        chunks = parse_document(tmp_path)
        if not chunks:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Could not extract any text from the uploaded document.",
            )

        # Move to profile storage
        profile_docs_dir = rag_service._profile_dir(profile_id) / "docs"
        profile_docs_dir.mkdir(parents=True, exist_ok=True)
        stored_path = profile_docs_dir / (uuid.uuid4().hex + suffix)
        tmp_path.rename(stored_path)

        # Index chunks
        updated_meta = rag_service.index_document(
            profile_id=profile_id,
            filepath=stored_path,
            filename=file.filename or "document",
            chunks=chunks,
        )

        return {
            "status": "indexed",
            "filename": file.filename,
            "chunks_indexed": len(chunks),
            "total_documents": len(updated_meta["documents"]),
            "profile": updated_meta,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Document indexing failed", extra={"error": str(e), "profile_id": profile_id})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Indexing error: {str(e)}")
    finally:
        # Cleanup temp file if still there
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


@router.post(
    "/{profile_id}/query",
    summary="Test document context retrieval",
    description="For debugging — retrieve document chunks relevant to a query.",
)
async def query_profile(profile_id: str, query: str):
    """Test the RAG retrieval for a profile with a specific query."""
    meta = rag_service.get_profile(profile_id)
    if meta is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found.")

    context = rag_service.retrieve_context(profile_id, query)
    return {"query": query, "context": context, "has_context": bool(context)}
