"""
Conversational Chatbot & ASR API routes using Groq LLM and Whisper.
Allows the avatar to respond intelligently to speech and text inputs.
"""
import os
import aiohttp
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, status
from pydantic import BaseModel, Field

from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/chat", tags=["Conversation & ASR"])


class ChatMessage(BaseModel):
    role: str = Field(description="Role: 'user', 'assistant', or 'system'")
    content: str


class ChatRequest(BaseModel):
    message: str = Field(description="The user's query or message")
    history: Optional[List[ChatMessage]] = Field(default=[], description="Previous conversation turns")
    system_prompt: Optional[str] = Field(
        default="You are an intelligent, friendly real-time AI avatar assistant. Keep your responses natural, engaging, and concise (1 to 2 sentences max) so they can be spoken quickly.",
        description="System prompt guiding persona",
    )


class ChatResponse(BaseModel):
    reply: str
    model: str


@router.post(
    "/respond",
    response_model=ChatResponse,
    summary="Generate conversational AI response",
    description="Uses Groq high-speed LLM to produce real-time conversational responses for the avatar.",
)
async def generate_response(body: ChatRequest):
    if not settings.groq_api_key:
        # Fallback if no Groq key configured
        return ChatResponse(
            reply=f"You said: '{body.message}'. To enable full conversational AI, add your GROQ_API_KEY.",
            model="fallback",
        )

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.groq_api_key}",
        "Content-Type": "application/json",
        "User-Agent": "AvatarService/1.0",
    }

    messages = [{"role": "system", "content": body.system_prompt}]
    for msg in body.history[-6:]:  # Keep last 6 turns for context
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": body.message})

    payload = {
        "model": "openai/gpt-oss-20b",
        "messages": messages,
        "max_tokens": 120,
        "temperature": 0.7,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    err_text = await resp.text()
                    logger.error("Groq chat error", extra={"status": resp.status, "error": err_text})
                    # Fallback to compound-mini if gpt-oss is busy
                    payload["model"] = "groq/compound-mini"
                    async with session.post(url, json=payload, headers=headers) as retry_resp:
                        if retry_resp.status != 200:
                            raise HTTPException(
                                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail="Failed to get response from Groq LLM.",
                            )
                        res_json = await retry_resp.json()
                else:
                    res_json = await resp.json()

                reply_text = res_json["choices"][0]["message"]["content"].strip()
                return ChatResponse(reply=reply_text, model=payload["model"])

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error in conversational pipeline", extra={"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Conversational generation error: {str(e)}",
        )


@router.post(
    "/transcribe",
    summary="Transcribe speech audio via Groq Whisper",
    description="Converts recorded microphone audio into text.",
)
async def transcribe_audio(file: UploadFile = File(...)):
    if not settings.groq_api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GROQ_API_KEY is required for server-side Whisper transcription.",
        )

    url = "https://api.groq.com/openai/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {settings.groq_api_key}"}

    audio_bytes = await file.read()
    data = aiohttp.FormData()
    data.add_field("file", audio_bytes, filename=file.filename or "audio.webm", content_type=file.content_type)
    data.add_field("model", "whisper-large-v3-turbo")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data, headers=headers) as resp:
                if resp.status != 200:
                    err_text = await resp.text()
                    logger.error("Groq Whisper error", extra={"status": resp.status, "error": err_text})
                    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Whisper error.")

                result = await resp.json()
                return {"text": result.get("text", "").strip()}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("ASR error", extra={"error": str(e)})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
