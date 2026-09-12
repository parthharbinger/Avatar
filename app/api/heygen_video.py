"""
HeyGen Standard Studio Video Generation API Routes.
"""
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.services.heygen_video import heygen_video_service
from app.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/video/heygen", tags=["HeyGen Studio Video"])


class GenerateVideoRequest(BaseModel):
    text: str = Field(description="The script for the avatar to speak")
    avatar_id: Optional[str] = Field(default="Abigail_expressive_2024112501", description="HeyGen avatar ID")
    voice_id: Optional[str] = Field(default="1bd001e7e50f421d891986aad5158bc8", description="HeyGen voice ID")
    title: Optional[str] = Field(default=None, description="Optional title")


class GenerateVideoResponse(BaseModel):
    video_id: str
    status: str
    message: str


class VideoStatusResponse(BaseModel):
    video_id: str
    status: Optional[str] = None
    video_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    duration: Optional[float] = None
    error: Optional[Any] = None


@router.post(
    "/generate",
    response_model=GenerateVideoResponse,
    summary="Generate HeyGen Studio Video (MP4)",
    description="Submits a standard studio video generation task to HeyGen.",
)
async def generate_heygen_video(body: GenerateVideoRequest):
    try:
        result = await heygen_video_service.generate_video(
            text=body.text,
            avatar_id=body.avatar_id or "Abigail_expressive_2024112501",
            voice_id=body.voice_id or "1bd001e7e50f421d891986aad5158bc8",
            title=body.title,
        )
        return GenerateVideoResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED if "credit" in str(e).lower() else status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except Exception as e:
        logger.error("Error generating HeyGen video", extra={"error": str(e)})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get(
    "/{video_id}/status",
    response_model=VideoStatusResponse,
    summary="Get HeyGen Video Status & Download Link",
    description="Polls rendering status and returns the completed MP4 video URL.",
)
async def get_heygen_video_status(video_id: str):
    try:
        result = await heygen_video_service.get_video_status(video_id)
        return VideoStatusResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get(
    "/avatars",
    summary="List HeyGen Avatars",
    description="Returns available studio avatars from HeyGen.",
)
async def list_heygen_avatars():
    avatars = await heygen_video_service.list_avatars()
    return {"avatars": avatars[:30]}
