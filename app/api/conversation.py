"""
Conversational Chatbot & ASR API routes using Groq LLM and Whisper.
Allows the avatar to respond intelligently to speech and text inputs.
Supports RAG document context injection when a profile_id is supplied.
"""
import re
import aiohttp
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, status
from pydantic import BaseModel, Field

from app.config import settings
from app.logging_config import get_logger
from app.services import rag_service
from app.services.text_sanitizer import clean_text_for_speech, PLAIN_TEXT_SPEECH_DIRECTIVE

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/chat", tags=["Conversation & ASR"])

HTTP_TIMEOUT = aiohttp.ClientTimeout(total=6.0)


def is_greeting_or_intro(query: str) -> bool:
    """Detect if query is a conversational greeting, identity inquiry, or capability check."""
    q = query.strip().lower()
    q_clean = re.sub(r"[^\w\s]", " ", q)
    words = q_clean.split()
    if not words:
        return True

    # 1. Pure greeting check (e.g. "hello", "hi there", "good morning")
    greeting_words = {
        "hi", "hello", "hey", "howdy", "greetings", "good", "morning", "afternoon",
        "evening", "day", "there", "yo", "hola", "namaste", "friend", "avatar",
        "assistant", "bot", "start", "help"
    }
    if all(w in greeting_words for w in words):
        return True

    # 2. Identity or capability query check
    intro_phrases = [
        "who are you", "who r u", "what is your name", "whats your name", "what are you",
        "what do you do", "what can you do", "what can you help", "how can you help",
        "tell me about yourself", "introduce yourself", "what are your capabilities",
        "what is your role", "what are you capable of", "how do you work"
    ]
    if any(phrase in q_clean for phrase in intro_phrases):
        domain_specific_tokens = {
            "paracetamol", "dosage", "mortgage", "interest", "apy", "shipping",
            "telehealth", "prescription", "fever", "refund", "insurance", "cd",
            "loan", "wire", "fraud", "clinic", "symptom", "order", "return"
        }
        if not any(token in words for token in domain_specific_tokens):
            return True

    return False



def get_persona_intro(profile_meta: Dict[str, Any]) -> str:
    """Generate an instant, natural persona greeting based on avatar domain."""
    name = profile_meta.get("name", "AI Assistant")
    persona = profile_meta.get("persona", "").lower()

    if persona == "banking" or "alexander" in name.lower():
        return (
            "Hello! I am Alexander, Senior Wealth Advisor at Crestview Private Bank. "
            "I can assist you with private checking, high-yield savings (4.85% APY), certificates of deposit, "
            "mortgages, rewards cards, and wealth management. How can I help you today?"
        )
    elif persona == "healthcare" or "maya" in name.lower():
        return (
            "Hello! I am Dr. Maya, Clinical Health Advisor at Apex Healthcare Partners. "
            "I can assist you with clinic hours, telehealth appointments, insurance coverage, "
            "prescription refills, and clinical care. How can I help you today?"
        )
    elif persona == "ecommerce" or "elena" in name.lower():
        return (
            "Hello! I am Elena, your E-Commerce Concierge at Global Luxe. "
            "I can assist you with order tracking, shipping timelines, 30-day return policy, "
            "price matching, and VIP rewards. How can I help you today?"
        )
    else:
        return f"Hello! I am {name}. I am ready to answer your questions based on my verified knowledge base. How can I assist you today?"


def detect_domain_mismatch(query: str, persona: str, profile_name: str) -> Optional[str]:
    """
    Returns an out-of-domain refusal/redirection message if the query explicitly
    belongs to a different specialist domain, or None if the query is in-domain or general.
    """
    q_lower = query.lower()

    medical_keywords = [
        "health", "doctor", "clinic", "hospital", "telehealth", "medicine", "medication",
        "prescription", "dosage", "pill", "symptom", "pain", "fever", "cough", "infection",
        "diagnos", "patient", "triage", "urgent care", "therapy", "disease", "illness",
        "paracetamol", "ibuprofen", "aspirin", "antibiotic", "headache", "chest", "burn"
    ]
    is_medical = any(k in q_lower for k in medical_keywords)

    banking_keywords = [
        "bank", "banking", "account", "savings", "checking", "interest", "apy", "cd",
        "deposit", "mortgage", "loan", "credit card", "wire", "swift", "fraud", "wealth",
        "investment", "portfolio", "crestview", "routing", "balance", "fund", "heloc"
    ]
    is_banking = any(k in q_lower for k in banking_keywords)

    ecommerce_keywords = [
        "return policy", "shipping", "delivery", "track", "package", "refund", "exchange",
        "price match", "cart", "product", "warranty", "loyalty", "promo", "discount", "coupon",
        "luxe", "store", "purchase", "item", "order"
    ]
    is_ecommerce = any(k in q_lower for k in ecommerce_keywords)

    persona_norm = persona.lower()
    name_norm = profile_name.lower()

    # 1. Banking Avatar
    if persona_norm == "banking" or "alexander" in name_norm:
        if is_medical:
            return (
                "I specialize in Private Banking and Wealth Management at Crestview Private Bank. "
                "That medical topic is outside of my financial document knowledge base. "
                "Please consult our Healthcare advisor, Dr. Maya, for clinical guidance."
            )
        elif is_ecommerce:
            return (
                "I specialize in Private Banking and Wealth Management at Crestview Private Bank. "
                "For questions regarding store orders, shipping, and returns, please speak with our E-Commerce Concierge, Elena."
            )

    # 2. Healthcare Avatar
    elif persona_norm == "healthcare" or "maya" in name_norm:
        if is_banking:
            return (
                "I am a Clinical Health Advisor at Apex Healthcare Partners. "
                "I do not have access to financial or banking records in my clinical documents. "
                "Please consult our Banking advisor, Alexander, for financial services."
            )
        elif is_ecommerce:
            return (
                "I am a Clinical Health Advisor at Apex Healthcare Partners. "
                "For questions regarding store orders, shipping, and returns, please speak with our E-Commerce Concierge, Elena."
            )

    # 3. E-Commerce Avatar
    elif persona_norm == "ecommerce" or "elena" in name_norm:
        if is_medical:
            return (
                "I am an E-Commerce Concierge for Global Luxe and do not have clinical medical information in my store documents. "
                "Please consult our Healthcare advisor, Dr. Maya, for medical inquiries."
            )
        elif is_banking:
            return (
                "I am an E-Commerce Concierge for Global Luxe. "
                "For banking, investments, mortgages, and wealth management, please consult our Banking advisor, Alexander."
            )

    return None


def get_out_of_domain_response(query: str, profile_name: str, persona: str) -> str:
    """
    Sub-millisecond out-of-domain rejection with cross-avatar specialist redirection.
    """
    mismatch = detect_domain_mismatch(query, persona, profile_name)
    if mismatch:
        return mismatch

    persona_norm = persona.lower()
    name_norm = profile_name.lower()

    if persona_norm == "banking" or "alexander" in name_norm:
        return (
            f"I am {profile_name}. That query does not match any information in my banking documents. "
            "I can only assist with private banking, high-yield savings, mortgages, credit cards, and wealth advisory."
        )
    elif persona_norm == "healthcare" or "maya" in name_norm:
        return (
            f"I am {profile_name}. That information is not found in my clinical healthcare documents. "
            "Please ask a question related to clinic services, telehealth, insurance, or medical triage."
        )
    elif persona_norm == "ecommerce" or "elena" in name_norm:
        return (
            f"I am {profile_name}. That topic is not covered in my store policy documents. "
            "I can assist with product orders, shipping timelines, 30-day returns, price matching, and rewards."
        )
    else:
        return (
            f"I am {profile_name}. That query does not match any information in my uploaded document knowledge base. "
            "Please ask a question related to my specialized documents."
        )


class ChatMessage(BaseModel):
    role: str = Field(description="Role: 'user', 'assistant', or 'system'")
    content: str


class ChatRequest(BaseModel):
    message: str = Field(description="The user's query or message")
    history: Optional[List[ChatMessage]] = Field(default=[], description="Previous conversation turns")
    system_prompt: Optional[str] = Field(
        default="You are an intelligent, friendly real-time AI avatar assistant. Keep your responses natural, engaging, concise (1 to 2 sentences max), and in plain text without emojis, logos, or formatting so they can be spoken smoothly.",
        description="System prompt guiding persona",
    )
    profile_id: Optional[str] = Field(
        default=None,
        description="Avatar expert profile ID. When set, relevant document context is injected from the RAG knowledge base.",
    )
    llm_provider: Optional[str] = Field(
        default=None,
        description="LLM provider: 'groq' | 'nvidia-nim'. Defaults to configured provider.",
    )


class ChatResponse(BaseModel):
    reply: str
    model: str
    sources: Optional[List[Dict[str, Any]]] = None


@router.post(
    "/respond",
    response_model=ChatResponse,
    summary="Generate conversational AI response",
    description="Uses Groq or NVIDIA NIM high-speed LLM to produce real-time conversational responses for the avatar.",
)
async def generate_response(body: ChatRequest):
    provider = (body.llm_provider or settings.llm_provider).lower()

    # ── RAG: Evaluate context & domain boundaries when profile_id is present ──
    active_system_prompt = body.system_prompt
    retrieved_sources = []
    rag_top_chunks = []
    has_rag_context = False

    if body.profile_id:
        try:
            profile_meta = rag_service.get_profile(body.profile_id)
            if profile_meta:
                # Use profile's custom system prompt if default was sent
                if not body.system_prompt or body.system_prompt == ChatRequest.model_fields["system_prompt"].default:
                    active_system_prompt = profile_meta.get("system_prompt", body.system_prompt)

                profile_docs = profile_meta.get("documents", [])
                profile_name = profile_meta.get("name", "Avatar")
                persona = profile_meta.get("persona", "general")

                # 1. Greeting / Persona Intro check (< 1ms)
                if is_greeting_or_intro(body.message):
                    intro_reply = get_persona_intro(profile_meta)
                    return ChatResponse(
                        reply=intro_reply,
                        model="persona-greeting",
                        sources=None,
                    )

                # 2. Domain Mismatch check (< 1ms)
                domain_mismatch_msg = detect_domain_mismatch(body.message, persona, profile_name)
                if domain_mismatch_msg:
                    return ChatResponse(
                        reply=domain_mismatch_msg,
                        model="rag-boundary-guard",
                        sources=None,
                    )

                # 3. RAG Retrieval & Context Matching
                rag_res = rag_service.retrieve_context_with_sources(body.profile_id, body.message)
                has_rag_context = rag_res.get("has_context", False)
                rag_top_chunks = rag_res.get("top_chunks", [])
                retrieved_sources = rag_res.get("sources", [])

                # 4. Out-of-Document check
                if profile_docs and not has_rag_context:
                    out_of_domain_reply = get_out_of_domain_response(
                        query=body.message,
                        profile_name=profile_name,
                        persona=persona,
                    )
                    return ChatResponse(
                        reply=out_of_domain_reply,
                        model="rag-boundary-guard",
                        sources=None,
                    )

                if has_rag_context and rag_res.get("context"):
                    active_system_prompt = f"{active_system_prompt}\n\n{rag_res['context']}"

        except Exception as rag_err:
            logger.warning("RAG context evaluation failed", extra={"error": str(rag_err)})
    else:
        # ── Open-Ended Non-Document Mode (No Profile / General Avatar) ────────
        if is_greeting_or_intro(body.message):
            return ChatResponse(
                reply=(
                    "Hello! I am Nova, your open-ended conversational AI avatar. "
                    "I am not connected to any specific document knowledge base, "
                    "so we can converse freely on any topic, creative brainstorming, science, tech, or general knowledge. "
                    "How can I help you today?"
                ),
                model="persona-greeting",
                sources=None,
            )

        if not body.system_prompt or body.system_prompt == ChatRequest.model_fields["system_prompt"].default:
            active_system_prompt = (
                "You are Nova, an intelligent, friendly open-ended AI avatar assistant. "
                "You are operating in open-ended conversation mode without any uploaded document constraints, "
                "so you can discuss any topic freely. If asked about your documents or knowledge base, "
                "clearly note that you are in open-ended mode without specific uploaded documents attached. "
                "Keep your responses natural, engaging, concise (1 to 2 sentences max), and in plain text "
                "without emojis, logos, or formatting so they can be spoken smoothly."
            )

    # Enforce pure plain-text directive to avoid emojis, logos, or markdown in speech
    system_instruction = f"{active_system_prompt}\n\n{PLAIN_TEXT_SPEECH_DIRECTIVE}"

    messages = [{"role": "system", "content": system_instruction}]
    for msg in body.history[-6:]:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": body.message})

    # ── 1. NVIDIA NIM LLM Execution ──────────────────────────────────────────
    if provider == "nvidia-nim" or (not settings.groq_api_key and settings.nvidia_nim_api_key):
        if not settings.nvidia_nim_api_key:
            if has_rag_context and rag_top_chunks:
                grounded = rag_service.extract_grounded_answer(rag_top_chunks, body.message)
                return ChatResponse(
                    reply=clean_text_for_speech(grounded),
                    model="rag-local-extractor",
                    sources=retrieved_sources if retrieved_sources else None,
                )
            return ChatResponse(
                reply=clean_text_for_speech(f"You said: '{body.message}'. To enable NVIDIA NIM conversational AI, add your NVIDIA_NIM_API_KEY."),
                model="fallback",
                sources=None,
            )

        nim_url = "https://integrate.api.nvidia.com/v1/chat/completions"
        nim_headers = {
            "Authorization": f"Bearer {settings.nvidia_nim_api_key}",
            "Content-Type": "application/json",
            "User-Agent": "AvatarService/1.0",
        }
        nim_model = settings.nvidia_nim_model or "meta/llama-3.2-11b-vision-instruct"
        nim_payload = {
            "model": nim_model,
            "messages": messages,
            "max_tokens": 120,
            "temperature": 0.7,
        }

        try:
            async with aiohttp.ClientSession(timeout=HTTP_TIMEOUT) as session:
                async with session.post(nim_url, json=nim_payload, headers=nim_headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        raw_reply = data["choices"][0]["message"]["content"].strip()
                        reply = clean_text_for_speech(raw_reply)
                        return ChatResponse(
                            reply=reply,
                            model=f"nvidia-nim/{nim_model}",
                            sources=retrieved_sources if retrieved_sources else None,
                        )
                    else:
                        err_text = await resp.text()
                        logger.error("NVIDIA NIM error", extra={"status": resp.status, "error": err_text})
        except Exception as nim_err:
            logger.error("NVIDIA NIM invocation failed", extra={"error": str(nim_err)})

        if has_rag_context and rag_top_chunks:
            grounded = rag_service.extract_grounded_answer(rag_top_chunks, body.message)
            return ChatResponse(
                reply=clean_text_for_speech(grounded),
                model="rag-local-extractor",
                sources=retrieved_sources if retrieved_sources else None,
            )

    # ── 2. Groq LLM Execution (Default / Primary) ───────────────────────────
    if not settings.groq_api_key:
        if has_rag_context and rag_top_chunks:
            grounded = rag_service.extract_grounded_answer(rag_top_chunks, body.message)
            return ChatResponse(
                reply=clean_text_for_speech(grounded),
                model="rag-local-extractor",
                sources=retrieved_sources if retrieved_sources else None,
            )
        return ChatResponse(
            reply=clean_text_for_speech(f"You said: '{body.message}'. To enable full conversational AI, configure GROQ_API_KEY or NVIDIA_NIM_API_KEY."),
            model="fallback",
            sources=None,
        )

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.groq_api_key}",
        "Content-Type": "application/json",
        "User-Agent": "AvatarService/1.0",
    }

    primary_model = settings.groq_model if settings.groq_model and not settings.groq_model.startswith("llama-3.3") else "qwen/qwen3.8-27b"
    payload = {
        "model": primary_model,
        "messages": messages,
        "max_tokens": 120,
        "temperature": 0.7,
    }

    try:
        async with aiohttp.ClientSession(timeout=HTTP_TIMEOUT) as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    err_text = await resp.text()
                    logger.error("Groq chat primary error", extra={"status": resp.status, "error": err_text})
                    # Fallback to compound-mini model
                    payload["model"] = "groq/compound-mini"
                    async with session.post(url, json=payload, headers=headers) as retry_resp:
                        if retry_resp.status == 200:
                            data = await retry_resp.json()
                            raw_reply = data["choices"][0]["message"]["content"].strip()
                            return ChatResponse(
                                reply=clean_text_for_speech(raw_reply),
                                model="groq/compound-mini",
                                sources=retrieved_sources if retrieved_sources else None,
                            )
                        else:
                            # 2nd fallback to gpt-oss-120b
                            payload["model"] = "openai/gpt-oss-120b"
                            async with session.post(url, json=payload, headers=headers) as retry_resp2:
                                if retry_resp2.status == 200:
                                    data2 = await retry_resp2.json()
                                    raw_reply2 = data2["choices"][0]["message"]["content"].strip()
                                    return ChatResponse(
                                        reply=clean_text_for_speech(raw_reply2),
                                        model="groq/openai-gpt-oss-120b",
                                        sources=retrieved_sources if retrieved_sources else None,
                                    )
                                logger.error("Groq chat fallback error", extra={"status": retry_resp2.status})
                else:
                    data = await resp.json()
                    raw_reply = data["choices"][0]["message"]["content"].strip()
                    return ChatResponse(
                        reply=clean_text_for_speech(raw_reply),
                        model=f"groq/{primary_model}",
                        sources=retrieved_sources if retrieved_sources else None,
                    )

    except Exception as e:
        logger.warning("External LLM query timed out or failed; engaging local grounded extractor", extra={"error": str(e)})

    # Local Grounded Fallback if LLM times out or fails
    if has_rag_context and rag_top_chunks:
        grounded = rag_service.extract_grounded_answer(rag_top_chunks, body.message)
        return ChatResponse(
            reply=clean_text_for_speech(grounded),
            model="rag-local-extractor",
            sources=retrieved_sources if retrieved_sources else None,
        )

    if body.profile_id:
        return ChatResponse(
            reply="I am processing your query based on my verified documents. Please ask a question related to my specialized knowledge base.",
            model="fallback",
            sources=retrieved_sources if retrieved_sources else None,
        )

    return ChatResponse(
        reply=f"I hear you asking about '{clean_text_for_speech(body.message)}'. I am ready to explore any open-ended topic with you.",
        model="open-ended-fallback",
        sources=None,
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


class SynthesizeRequest(BaseModel):
    text: str = Field(..., description="Text to synthesize into HD neural speech audio")
    voice: Optional[str] = Field(None, description="Neural voice identifier")


@router.post(
    "/synthesize",
    summary="Synthesize speech audio via Neural TTS (MP3)",
    description="Returns high-definition neural speech MP3 audio for direct playback and WebRTC avatar streaming.",
)
async def synthesize_speech(body: SynthesizeRequest):
    from fastapi.responses import Response
    from app.tts.edge_tts_adapter import EdgeTTSAdapter

    cleaned = clean_text_for_speech(body.text)
    if not cleaned:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Text cannot be empty.")

    try:
        adapter = EdgeTTSAdapter()
        chunks = []
        async for chunk in adapter.stream_speech(cleaned, body.voice):
            if chunk.data:
                chunks.append(chunk.data)
        audio_bytes = b"".join(chunks)
        return Response(content=audio_bytes, media_type="audio/mp3")
    except Exception as e:
        logger.error("TTS synthesis failed", extra={"error": str(e)})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"TTS error: {str(e)}")

