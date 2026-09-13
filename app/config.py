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

    # TTS Providers
    tts_provider: str = "edge-tts"
    edge_tts_voice: str = "en-US-AriaNeural"
    edge_tts_verify_ssl: bool = False
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "21m00Tcm4TlvDq8ikWAM"
    openai_api_key: str = ""
    openai_tts_voice: str = "alloy"

    # Avatar Video Providers (D-ID, Simli, Anam.ai, Akool, HeyGen, Canvas)
    avatar_provider: str = "d-id"  # 'd-id' | 'simli' | 'anam' | 'akool' | 'heygen' | 'canvas'
    did_api_key: str = ""
    did_source_url: str = "https://raw.githubusercontent.com/d-id/create-stream-webrtc/main/emma.png"
    
    # HeyGen
    heygen_api_key: str = ""
    heygen_avatar_id: str = "default"

    # Simli (Low-latency WebRTC Audio-to-Video)
    simli_api_key: str = ""
    simli_face_id: str = "tmp9i8bbq7v"

    # Anam.ai (Conversational Digital Human API)
    anam_api_key: str = ""
    anam_persona_id: str = "default"

    # Akool (Streaming Avatar & Talking Photo API)
    akool_api_key: str = ""
    akool_client_id: str = ""

    # LLM & ASR
    groq_api_key: str = ""


# Global singleton
settings = Settings()
