"""
TTS adapter factory — returns the correct provider based on config.
"""
from app.tts.base import BaseTTSAdapter
from app.config import settings


def get_tts_adapter() -> BaseTTSAdapter:
    """
    Returns the configured TTS adapter.
    Add new providers here as elif branches.
    """
    provider = settings.tts_provider.lower()

    if provider == "edge-tts":
        from app.tts.edge_tts_adapter import EdgeTTSAdapter
        return EdgeTTSAdapter()
    else:
        raise ValueError(
            f"Unknown TTS provider: '{provider}'. "
            "Supported: 'edge-tts'. Set TTS_PROVIDER in .env"
        )


from app.tts.base import BaseTTSAdapter, AudioChunk
from app.tts.edge_tts_adapter import EdgeTTSAdapter

__all__ = ["BaseTTSAdapter", "AudioChunk", "EdgeTTSAdapter", "get_tts_adapter"]
