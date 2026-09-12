"""
Avatar Providers module.
Provides factory for selecting between $0 EdgeTTS/Canvas mode, D-ID WebRTC, and HeyGen WebRTC.
"""
from typing import Optional

from app.avatar_providers.base import BaseAvatarProvider
from app.avatar_providers.did_adapter import DIDAvatarProvider
from app.avatar_providers.heygen_adapter import HeyGenAvatarProvider
from app.config import settings


def get_avatar_provider(provider_name: Optional[str] = None) -> Optional[BaseAvatarProvider]:
    """
    Get configured 3rd-party avatar provider (if any).
    Returns None if using the default $0 Canvas 2D engine.
    """
    name = (provider_name or settings.avatar_provider).lower()

    if name in ("d-id", "did"):
        return DIDAvatarProvider()
    elif name == "heygen":
        return HeyGenAvatarProvider()
    elif name in ("edge-tts", "canvas", "default"):
        return None
    else:
        return None
