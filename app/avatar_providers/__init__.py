"""
Avatar Providers module.
Provides dynamic factory for selecting between:
- Lightweight 2D Neural Canvas ($0 EdgeTTS + WordBoundary visemes)
- D-ID WebRTC Live Stream
- Simli WebRTC Stream (<300ms Low Latency)
- Anam.ai Digital Human WebRTC Stream
- Akool Avatar Stream
- HeyGen Studio & WebRTC Video
"""
from typing import Optional

from app.avatar_providers.base import BaseAvatarProvider
from app.avatar_providers.did_adapter import DIDAvatarProvider
from app.avatar_providers.heygen_adapter import HeyGenAvatarProvider
from app.avatar_providers.simli_adapter import SimliAvatarProvider
from app.avatar_providers.anam_adapter import AnamAvatarProvider
from app.avatar_providers.akool_adapter import AkoolAvatarProvider
from app.config import settings


def get_avatar_provider(provider_name: Optional[str] = None) -> Optional[BaseAvatarProvider]:
    """
    Get configured 3rd-party avatar provider adapter.
    Returns None if using the default 2D Neural Canvas engine.
    """
    name = (provider_name or settings.avatar_provider).lower().strip()

    if name in ("d-id", "did"):
        return DIDAvatarProvider()
    elif name == "simli":
        return SimliAvatarProvider()
    elif name in ("anam", "anam.ai", "anamai"):
        return AnamAvatarProvider()
    elif name == "akool":
        return AkoolAvatarProvider()
    elif name == "heygen":
        return HeyGenAvatarProvider()
    elif name in ("edge-tts", "canvas", "default", "2d"):
        return None
    else:
        return None
