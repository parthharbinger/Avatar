"""
HeyGen Standard Studio Video Generation Service.
Allows generating downloadable, studio-quality MP4 avatar videos using HeyGen API.
"""
import aiohttp
from typing import Dict, Any, Optional, List
from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)


class HeyGenVideoService:
    BASE_URL = "https://api.heygen.com"

    def __init__(self) -> None:
        self.api_key = settings.heygen_api_key

    def _get_headers(self) -> Dict[str, str]:
        return {
            "X-Api-Key": self.api_key,
            "Content-Type": "application/json",
            "accept": "application/json",
            "User-Agent": "AvatarService/1.0",
        }

    async def list_avatars(self) -> List[Dict[str, Any]]:
        """Fetch list of available HeyGen avatars."""
        if not self.api_key:
            return []

        url = f"{self.BASE_URL}/v2/avatars"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self._get_headers()) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("data", {}).get("avatars", [])
                    return []
        except Exception as e:
            logger.error("Failed to fetch HeyGen avatars", extra={"error": str(e)})
            return []

    async def generate_video(
        self,
        text: str,
        avatar_id: str = "Abigail_expressive_2024112501",
        voice_id: str = "1bd001e7e50f421d891986aad5158bc8",
        title: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Submit a video generation task to HeyGen."""
        if not self.api_key:
            raise ValueError("HEYGEN_API_KEY is not configured in .env")

        url = f"{self.BASE_URL}/v2/video/generate"
        payload = {
            "title": title or f"Avatar Video - {text[:30]}",
            "video_inputs": [
                {
                    "character": {
                        "type": "avatar",
                        "avatar_id": avatar_id,
                        "avatar_style": "normal",
                    },
                    "voice": {
                        "type": "text",
                        "input_text": text,
                        "voice_id": voice_id,
                    },
                }
            ],
            "dimension": {"width": 1280, "height": 720},
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=self._get_headers()) as resp:
                data = await resp.json()
                if resp.status not in (200, 201):
                    err_msg = data.get("error", {}).get("message") or str(data)
                    logger.error("HeyGen video generation failed", extra={"status": resp.status, "error": err_msg})
                    raise RuntimeError(f"HeyGen error: {err_msg}")

                video_id = data.get("data", {}).get("video_id")
                return {
                    "video_id": video_id,
                    "status": "processing",
                    "message": "Video generation task queued successfully",
                }

    async def get_video_status(self, video_id: str) -> Dict[str, Any]:
        """Check rendering status of a generated HeyGen video."""
        if not self.api_key:
            raise ValueError("HEYGEN_API_KEY is not configured in .env")

        url = f"{self.BASE_URL}/v1/video_status.get?video_id={video_id}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self._get_headers()) as resp:
                if resp.status != 200:
                    err_text = await resp.text()
                    raise RuntimeError(f"Failed to fetch video status: {err_text}")

                data = await resp.json()
                video_data = data.get("data", {})
                return {
                    "video_id": video_id,
                    "status": video_data.get("status"),  # 'pending', 'processing', 'completed', 'failed'
                    "video_url": video_data.get("video_url"),
                    "thumbnail_url": video_data.get("thumbnail_url"),
                    "duration": video_data.get("duration"),
                    "error": video_data.get("error"),
                }


heygen_video_service = HeyGenVideoService()
