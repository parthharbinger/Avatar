"""
Application configuration loaded from environment variables via pydantic-settings.
"""
import json
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    environment: str = "development"
    log_level: str = "INFO"

    # Session Management
    session_timeout_seconds: int = 300
    max_concurrent_sessions: int = 20

    # CORS
    cors_origins: List[str] = ["*"]

    # TTS
    tts_provider: str = "edge-tts"
    edge_tts_voice: str = "en-US-AriaNeural"
    edge_tts_verify_ssl: bool = False
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "21m00Tcm4TlvDq8ikWAM"
    openai_api_key: str = ""
    openai_tts_voice: str = "alloy"

    # Avatar Video Providers (Optional 3rd-party photorealistic WebRTC streaming)
    avatar_provider: str = "edge-tts"  # 'edge-tts' (2D Canvas $0) | 'd-id' (WebRTC) | 'heygen' (WebRTC)
    did_api_key: str = ""
    did_source_url: str = "https://raw.githubusercontent.com/d-id/create-stream-webrtc/main/emma.png"
    heygen_api_key: str = ""
    heygen_avatar_id: str = "default"

    # ASR (optional)
    groq_api_key: str = ""


# Global singleton
settings = Settings()
