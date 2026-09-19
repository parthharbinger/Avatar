# AI Avatar Platform — Comprehensive Technical Specification & Architecture Manual

## Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [End-to-End System Flow (Input to Output)](#2-end-to-end-system-flow-input-to-output)
   - [2.1 Conversational Turn & RAG Flow](#21-conversational-turn--rag-flow)
   - [2.2 2D Neural Canvas Engine Flow (Zero-GPU)](#22-2d-neural-canvas-engine-flow-zero-gpu)
   - [2.3 Live WebRTC Photorealistic Digital Human Flow](#23-live-webrtc-photorealistic-digital-human-flow)
   - [2.4 Cloud Video Studio Generation Flow (HeyGen)](#24-cloud-video-studio-generation-flow-heygen)
   - [2.5 Hands-Free Continuous Voice Loop & Barge-In FSM](#25-hands-free-continuous-voice-loop--barge-in-fsm)
3. [Folder Structure & Modular Breakdown](#3-folder-structure--modular-breakdown)
   - [3.1 Backend Application (`app/`)](#31-backend-application-app)
   - [3.2 Frontend & Client Web SDK (`sdk/`)](#32-frontend--client-web-sdk-sdk)
   - [3.3 Interactive Showcase Application (`demo/`)](#33-interactive-showcase-application-demo)
   - [3.4 Data & Storage Layer (`data/`)](#34-data--storage-layer-data)
   - [3.5 Test Suite (`tests/`)](#35-test-suite-tests)
4. [Technology Stack, APIs & Integrations](#4-technology-stack-apis--integrations)
   - [4.1 Backend Technologies](#41-backend-technologies)
   - [4.2 Large Language Models & RAG Engine](#42-large-language-models--rag-engine)
   - [4.3 Digital Human Video Streaming Providers](#43-digital-human-video-streaming-providers)
   - [4.4 Speech Synthesis (TTS) & Phoneme Engines](#44-speech-synthesis-tts--phoneme-engines)
   - [4.5 Frontend & Client SDK Stack](#45-frontend--client-sdk-stack)
5. [Feature Matrix & Usage Guide](#5-feature-matrix--usage-guide)
   - [5.1 REST Microservice API Reference](#51-rest-microservice-api-reference)
   - [5.2 Real-Time WebSocket Streaming Protocol](#52-real-time-websocket-streaming-protocol)
   - [5.3 TypeScript SDK Integration (`@avatar-sdk/client`)](#53-typescript-sdk-integration-avatar-sdkclient)
   - [5.4 RAG Document Knowledge & Custom Expert Profile Creation](#54-rag-document-knowledge--custom-expert-profile-creation)
   - [5.5 HeyGen Studio Cloud Video Generation](#55-heygen-studio-cloud-video-generation)
6. [Deployment & Configuration](#6-deployment--configuration)

---

## 1. Executive Summary

The **AI Avatar Platform** is an enterprise-grade, real-time conversational digital human system designed to deliver ultra-low latency (<500ms TTFF) conversational intelligence with photorealistic visual embodiment. 

The architecture supports a dual-engine rendering approach:
1. **2D Neural Canvas Engine**: A lightweight, zero-GPU client-side canvas renderer that transforms high-resolution static portraits into animated digital humans with realistic anatomical eye blinking, eyelid curvature, multi-layer mouth synthesis (Cupid's bow, dental arches, 3D tongue dynamics), and word-boundary synchronized speech via Microsoft Edge Neural TTS.
2. **Live WebRTC Digital Humans**: Enterprise video streaming integrating **D-ID**, **Simli**, **Anam.ai**, **Akool**, and **HeyGen** via sub-second WebRTC peer connections.

Coupled with **Groq LLM intelligence** (LLaMA 3.3 70B), **Hybrid BM25 RAG Document Grounding**, **Hands-Free Continuous Voice Loops**, and **Speech-Detected Barge-In Interruption**, the platform functions both as a standalone conversational microservice and as a plug-and-play drop-in Web SDK.

---

## 2. End-to-End System Flow (Input to Output)

```
+---------------------------------------------------------------------------------------------+
|                                    USER INPUT INTERACTION                                   |
|   (Speech via Web Speech ASR / Typed Query / Continuous Hands-Free Voice Loop / PDF Upload)  |
+---------------------------------------------------------------------------------------------+
                                               │
                                               ▼
+---------------------------------------------------------------------------------------------+
|                          1. ORCHESTRATION & BARGE-IN CONTROLLER                             |
|  - If speaking/thinking: AbortController cancels in-flight LLM & halts active audio/video.  |
|  - Validates user input & session state in SessionManager.                                  |
+---------------------------------------------------------------------------------------------+
                                               │
                                               ▼
+---------------------------------------------------------------------------------------------+
|                          2. RAG KNOWLEDGE RETRIEVAL & LLM INFERENCE                         |
|  - RAGService: Queries BM25 + Keyword Hybrid Index over profile's uploaded documents.       |
|  - Builds Grounded Prompt with retrieved passages & conversation history.                   |
|  - Groq LLM (LLaMA 3.3 70B Versatile): Streams or generates response (<150ms TTFT).        |
+---------------------------------------------------------------------------------------------+
                                               │
                         ┌─────────────────────┴─────────────────────┐
                         ▼                                           ▼
      [ ENGINE A: 2D NEURAL CANVAS ]              [ ENGINE B: LIVE WEBRTC DIGITAL HUMAN ]
                         │                                           │
                         ▼                                           ▼
+------------------------------------+      +------------------------------------------------+
| 3A. TTS & VISEME TIMELINE PIPELINE |      | 3B. WEBRTC STREAMING ADAPTER                   |
| - EdgeTTS streams MP3 audio chunks.|      | - D-ID / Simli / Anam / Akool / HeyGen API.    |
| - Extracts WordBoundary offsets.   |      | - Submits text/audio via provider session.     |
| - Viseme Mapper generates keyframe |      | - Provider renders cloud neural video frame.   |
|   timeline (open/round/dental/etc).|      | - Streams H.264/VP8 video packets via WebRTC.  |
+------------------------------------+      +------------------------------------------------+
                         │                                           │
                         ▼                                           ▼
+------------------------------------+      +------------------------------------------------+
| 4A. WEBSOCKET PROTOCOL EMISSION    |      | 4B. WEBRTC MEDIA PLAYBACK                      |
| - Sends `viseme_timeline` JSON.    |      | - Browser receives live MediaStream track.     |
| - Streams base64 `audio_chunk` msg.|      | - Renders in `<video id="avatar-video">`.      |
| - Emits `end` keyframe completion. |      | - Sub-400ms latency mouth-sync playback.       |
+------------------------------------+      +------------------------------------------------+
                         │
                         ▼
+-------------------------------------------------------------------+
| 5A. HIGH-FIDELITY CLIENT CANVAS & WEBAUDIO RENDERER               |
| - WebAudio API decodes & schedules audio playback.                |
| - Natural Human Blinking: Asymmetrical eyelid descent & creases.  |
| - Multi-Layer Mouth: Cupid's bow, oral cavity, teeth & tongue.    |
| - Breathing micro-motion synced to audio timeline.                |
+-------------------------------------------------------------------+
```

---

### 2.1 Conversational Turn & RAG Flow
1. **User Request**: The user submits a question via text input or microphone.
2. **Profile Resolution**: The system checks if an active `profile_id` is selected.
3. **RAG Passage Retrieval**:
   - `RAGService.search_passages(profile_id, query, top_k=3)` queries the in-memory inverted document index.
   - Calculates score weights using BM25 term frequency-inverse document frequency formulas across indexed chunks.
   - Extracts relevant citations and passage snippets.
4. **Prompt Construction**:
   - System prompt incorporates avatar persona rules and strict RAG grounding directives:
     ```
     Context information from documents:
     [1] (File: HR_Policy.pdf): "Employees receive 20 days of paid annual leave..."
     Answer the question based strictly on the above context.
     ```
5. **Inference Execution**:
   - Dispatches payload to selected LLM engine:
     - **Groq Cloud API** (`openai/gpt-oss-20b` / `llama-3.3-70b-versatile`): Ultra-fast LPU inference (<150ms).
     - **NVIDIA NIM Cloud API** (`meta/llama-3.2-11b-vision-instruct` / `nvidia/nemotron`): NVIDIA GPU-accelerated inference with multimodal reasoning.
6. **Chat History Update**:
   - Updates session history with `{ role: "user", content: query }` and `{ role: "assistant", content: reply }`.
   - Returns reply text and grounding citation metadata (`filename`, `score`, `snippet`) to the frontend.

---

### 2.2 2D Neural Canvas Engine Flow (Zero-GPU)
1. **Session Creation**: Client makes `POST /api/v1/sessions` &rarr; server allocates a UUID `session_id` and assigns a WebSocket endpoint `/api/v1/stream/{session_id}`.
2. **WebSocket Handshake**: Client establishes WebSocket connection; server responds with `{"type": "connected", "session_id": "..."}`.
3. **Speech Action**: Client sends `{"action": "speak", "text": "...", "voice": "en-US-JennyNeural"}`.
4. **Speech Pipeline (`run_speech_pipeline`)**:
   - Calls `EdgeTTSAdapter.stream_speech_with_boundaries(text, voice)`.
   - Edge-TTS yields binary MP3 audio chunks and `WordBoundary` timestamp events (`offset_ms`, `duration_ms`, `word`).
   - `from_word_boundaries()` computes viseme shapes (`open`, `round`, `dental`, `labiodental`, `bilabial`, `neutral`) matching phonetics.
   - Server streams `viseme_timeline` JSON followed by incremental `audio_chunk` messages.
5. **Client-Side Rendering**:
   - `SeamlessAudioEngine` buffers chunks and decodes them via `AudioContext.decodeAudioData()`.
   - `Renderer2D` updates facial geometry on every `requestAnimationFrame`:
     - **Eyelids**: Descending quadratic curve with skin tone gradient, orbital shadow, and lash fringe.
     - **Mouth**: Multi-layer rendering with throat cavity depth gradient, enamel dental arch, 3D tongue dynamics, and cubic Bezier Cupid's bow lip curves.
     - **Breathing**: Micro-harmonic sine displacement.

---

### 2.3 Live WebRTC Photorealistic Digital Human Flow
1. **WebRTC Offer Request**: Client calls `POST /api/v1/sessions/{session_id}/webrtc/offer?provider=d-id&avatar_id=female`.
2. **Provider Initialization**:
   - `DIDAdapter` / `SimliAdapter` / `AnamAdapter` calls the cloud streaming provider to create a live streaming session.
   - Provider returns an SDP Offer and ICE server credentials.
3. **PeerConnection Negotiation**:
   - Client creates `new RTCPeerConnection({ iceServers })`.
   - Sets remote description with SDP Offer, creates SDP Answer, and sends it via `POST /api/v1/sessions/{session_id}/webrtc/answer`.
   - ICE candidates are exchanged asynchronously via `/api/v1/sessions/{session_id}/webrtc/ice`.
4. **Media Stream Playback**:
   - WebRTC peer connection transitions to `"connected"`.
   - Provider streams high-definition video track (H.264/VP8) directly to the browser's `<video id="avatar-video">`.
5. **Interactive Speech**:
   - Subsequent conversational turns call `POST /api/v1/sessions/{session_id}/webrtc/speak` with `stream_id` and text.
   - Cloud provider renders lip-synced video frames into the active WebRTC stream in under 400ms.

---

### 2.4 Cloud Video Studio Generation Flow (HeyGen)
1. **Submission**: User inputs a script and avatar persona in the Studio tab and clicks "Generate".
2. **Generation Request**: `POST /api/v1/video/heygen/generate` with `{ text, avatar_id, title }`.
3. **Cloud Processing**: `HeyGenVideoService` calls HeyGen Cloud Video API (`/v2/video/generate`) and returns a `video_id`.
4. **Status Polling**: Frontend polls `GET /api/v1/video/heygen/{video_id}/status` every 3 seconds.
5. **Delivery**: When status reaches `"completed"`, the backend returns the signed MP4 `video_url`. The user can preview the video directly or download the MP4 file.

---

### 2.5 Hands-Free Continuous Voice Loop & Barge-In FSM
The voice interaction lifecycle is managed via a deterministic Finite State Machine (FSM):

```
       ┌──────────────────────────┐
       │          IDLE            │ ◄───────────────────────────┐
       └─────────────┬────────────┘                             │
                     │ User clicks Mic / Voice Loop             │
                     ▼                                          │
       ┌──────────────────────────┐                             │
       │        LISTENING         │                             │
       │   (SpeechRec active)     │                             │
       └─────────────┬────────────┘                             │
                     │ Final Transcript Received                │
                     ▼                                          │
       ┌──────────────────────────┐                             │
       │        PROCESSING        │                             │
       │   (Groq LLM + RAG)       │ ──[ Human Speech Detected ]─┤
       └─────────────┬────────────┘       (Barge-In Cancel)     │
                     │ LLM Response Ready                       │
                     ▼                                          │
       ┌──────────────────────────┐                             │
       │         SPEAKING         │                             │
       │   (Audio + Video Play)   │ ──[ Human Speech Detected ]─┘
       └─────────────┬────────────┘       (Barge-In Cancel &
                     │ Audio Playback Finished                      Restart Listening)
                     ▼
             [ Loop Active? ]
              ├── YES ──► (Back to LISTENING)
              └── NO  ──► (Back to IDLE)
```

- **Interruption Mechanism**: When state is `SPEAKING` or `PROCESSING` and interim speech energy is recognized (>2 characters), `triggerBargeInInterruption()`:
  1. Aborts in-flight `fetch` via `askAbortController.abort()`.
  2. Stops audio playback via `audio.stop()`.
  3. Sends `{"action": "interrupt"}` over WebSocket to cancel the server task.
  4. Transitions state directly to answering the newly spoken user query.

---

## 3. Folder Structure & Modular Breakdown

```
Avatar/
├── app/                              # Core Python FastAPI backend
│   ├── api/                          # REST & WebSocket API route handlers
│   │   ├── conversation.py           # Chatbot conversation endpoint with    RAG & Groq LLM
│   │   ├── costs.py                  # Telemetry, token accounting, and cost tracking
│   │   ├── heygen_video.py           # HeyGen cloud video generation & polling endpoints
│   │   ├── profiles.py               # Custom expert avatar profiles & document CRUD
│   │   ├── sessions.py               # Avatar session lifecycle & WebRTC signaling
│   │   └── websocket.py              # Real-time WebSocket audio/viseme streaming router
│   ├── avatar_providers/             # WebRTC Digital Human Provider Adapters
│   │   ├── base.py                   # Abstract BaseAvatarProvider interface
│   │   ├── akool_adapter.py          # Akool Streaming Avatar API integration
│   │   ├── anam_adapter.py           # Anam.ai Digital Human WebRTC integration
│   │   ├── did_adapter.py            # D-ID Agents WebRTC live streaming integration
│   │   ├── heygen_adapter.py         # HeyGen Interactive Streaming API integration
│   │   └── simli_adapter.py          # Simli low-latency WebRTC avatar integration
│   ├── orchestration/                # Stream orchestration & concurrency management
│   │   └── pipeline.py               # TTS -> WordBoundary -> Viseme -> WebSocket pipeline
│   ├── services/                     # Business logic & external AI service adapters
│   │   ├── document_parser.py        # PDF, DOCX, TXT, MD text extraction & token chunking
│   │   ├── heygen_video.py           # HeyGen Cloud Video generation & status polling service
│   │   └── rag_service.py            # Hybrid BM25 document indexing & passage retrieval
│   ├── sessions/                     # Session state storage & lifecycle management
│   │   ├── manager.py                # Async in-memory session store with auto-expiry
│   │   └── models.py                 # Session domain models & session state enums
│   ├── tts/                          # Text-to-Speech adapters
│   │   ├── base.py                   # Abstract BaseTTSAdapter & AudioChunk definitions
│   │   └── edge_tts_adapter.py       # Microsoft Edge Neural TTS streaming adapter
│   ├── viseme/                       # Phoneme & Viseme synchronization engine
│   │   ├── mapper.py                 # Character & WordBoundary to Viseme mapping logic
│   │   └── models.py                 # VisemeShape enum & VisemeEvent data structures
│   ├── config.py                     # Pydantic Settings (.env configuration loader)
│   ├── logging_config.py             # Structured JSON & console logging formatter
│   └── main.py                       # FastAPI application entrypoint & middleware setup
├── data/                             # Persistent profile metadata & document storage
│   ├── documents/                    # Raw uploaded knowledge files (PDF/DOCX/TXT/MD)
│   └── profiles.json                 # JSON store for custom named avatar expert profiles
├── demo/                             # Standalone interactive showcase application
│   └── index.html                    # Complete single-page UI with 2D/WebRTC/RAG/Voice
├── examples/                         # Reference SDK integration examples
│   └── vanilla-html/                 # Vanilla JS/HTML SDK integration example
├── sdk/                              # TypeScript Client & Drop-in Web Component SDK
│   ├── src/                          # TypeScript source code
│   │   ├── audio.ts                  # WebAudio playback & queue scheduling
│   │   ├── client.ts                 # Core AvatarClient WebSocket communication engine
│   │   ├── index.ts                  # SDK public export entrypoint
│   │   ├── renderer2d.ts             # 2D Neural Canvas Renderer with anatomical blinking/mouth
│   │   ├── transport.ts              # Resilient WebSocket transport with auto-reconnect
│   │   ├── types.ts                  # Public TypeScript interfaces & viseme type definitions
│   │   └── widget.ts                 # Drop-in AvatarWidget UI component with WebRTC & RAG
│   ├── package.json                  # NPM package manifest (`@avatar-sdk/client`)
│   ├── tsconfig.json                 # TypeScript compiler configuration
│   └── tsup.config.ts                # Tsup build configuration (ESM, CJS, DTS)
├── tests/                            # Pytest test suite
│   ├── test_api.py                   # REST & WebSocket endpoint integration tests
│   ├── test_session_manager.py       # Session concurrency & expiry unit tests
│   └── test_viseme_mapper.py         # Viseme mapping & word boundary unit tests
├── .env.example                      # Template environment variables
├── pyproject.toml                    # Python project dependencies & metadata
└── pytest.ini                        # Pytest configuration
```

---

### 3.1 Backend Application (`app/`)

- [`app/main.py`](file:///d:/Desktop/PARTH/Work/Project3(AI Avatar)/Avatar/app/main.py): Initializes the FastAPI application, configures CORS middleware (allowing cross-origin SDK connections), mounts static asset routes (`/demo`, `/assets`, `/sdk/dist`), registers all API routers, and performs startup health checks.
- [`app/config.py`](file:///d:/Desktop/PARTH/Work/Project3(AI Avatar)/Avatar/app/config.py): Defines `Settings` using `pydantic-settings`. Loads environment variables for Groq API keys, D-ID, Simli, Anam, Akool, HeyGen, and Edge-TTS voice settings.
- [`app/api/conversation.py`](file:///d:/Desktop/PARTH/Work/Project3(AI Avatar)/Avatar/app/api/conversation.py): Handles `POST /api/v1/chat/respond`. Integrates Groq LLM with hybrid RAG search over active profile documents, tracks inference costs, and returns grounded answers with citations.
- [`app/api/profiles.py`](file:///d:/Desktop/PARTH/Work/Project3(AI Avatar)/Avatar/app/api/profiles.py): REST API for Custom Avatar Expert Profiles. Supports creating profiles, uploading documents (PDF/DOCX/TXT/MD), indexing documents into the BM25 engine, and deleting documents.
- [`app/api/sessions.py`](file:///d:/Desktop/PARTH/Work/Project3(AI Avatar)/Avatar/app/api/sessions.py): Handles session creation, provider capability queries (`/api/v1/providers`), and WebRTC signaling endpoints (SDP offer generation, SDP answer submission, and ICE candidate exchange).
- [`app/api/websocket.py`](file:///d:/Desktop/PARTH/Work/Project3(AI Avatar)/Avatar/app/api/websocket.py): High-performance WebSocket endpoint (`/api/v1/stream/{session_id}`). Dispatches `"speak"`, `"interrupt"`, and `"ping"` actions, managing cancellable background streaming tasks.
- [`app/api/costs.py`](file:///d:/Desktop/PARTH/Work/Project3(AI Avatar)/Avatar/app/api/costs.py): Telemetry router providing live cost estimates and TTFF latency measurements across all providers and LLM tokens.
- [`app/api/heygen_video.py`](file:///d:/Desktop/PARTH/Work/Project3(AI Avatar)/Avatar/app/api/heygen_video.py): Handles HeyGen Cloud Studio video generation tasks and polling endpoints.
- [`app/services/rag_service.py`](file:///d:/Desktop/PARTH/Work/Project3(AI Avatar)/Avatar/app/services/rag_service.py): In-memory BM25 + Multi-Vector Hybrid Indexing engine. Chunks documents, indexes inverted term frequencies, and retrieves top matching passages with relevance scores.
- [`app/services/document_parser.py`](file:///d:/Desktop/PARTH/Work/Project3(AI Avatar)/Avatar/app/services/document_parser.py): Robust text extractor for PDF (via `pypdf`), DOCX (via `docx`), Markdown, and plain text with sliding window chunking (400 words, 50-word overlap).
- [`app/services/heygen_video.py`](file:///d:/Desktop/PARTH/Work/Project3(AI Avatar)/Avatar/app/services/heygen_video.py): Client service communicating with HeyGen REST API v2 for studio video generation.
- [`app/orchestration/pipeline.py`](file:///d:/Desktop/PARTH/Work/Project3(AI Avatar)/Avatar/app/orchestration/pipeline.py): Manages real-time audio/viseme streaming pipeline as an `asyncio.Task` that can be cancelled mid-stream upon barge-in interrupts.
- [`app/tts/edge_tts_adapter.py`](file:///d:/Desktop/PARTH/Work/Project3(AI Avatar)/Avatar/app/tts/edge_tts_adapter.py): Interfaces with Microsoft's Edge Neural TTS service to yield MP3 chunks and word-level timing boundaries.
- [`app/viseme/mapper.py`](file:///d:/Desktop/PARTH/Work/Project3(AI Avatar)/Avatar/app/viseme/mapper.py): Translates character sequences and TTS WordBoundaries into synchronized visual mouth shape timelines.

---

### 3.2 Frontend & Client Web SDK (`sdk/`)

- [`sdk/src/widget.ts`](file:///d:/Desktop/PARTH/Work/Project3(AI Avatar)/Avatar/sdk/src/widget.ts): Complete, self-contained interactive AI Avatar UI widget. Supports floating launcher, embedded cards, live WebRTC video tracks, 2D neural canvas, speech recognition, continuous voice loop, barge-in, and RAG document grounding.
- [`sdk/src/renderer2d.ts`](file:///d:/Desktop/PARTH/Work/Project3(AI Avatar)/Avatar/sdk/src/renderer2d.ts): High-fidelity 2D Canvas Renderer. Features anatomical eyelid curvature, asymmetric blink velocity (80ms close, 140ms open), persona-specific skin tone gradients, and multi-layer sculpted mouth rendering (Cupid's bow, oral cavity depth, enamel teeth, 3D tongue dynamics).
- [`sdk/src/client.ts`](file:///d:/Desktop/PARTH/Work/Project3(AI Avatar)/Avatar/sdk/src/client.ts): Low-level headless TypeScript client for developers building custom avatar user interfaces.
- [`sdk/src/audio.ts`](file:///d:/Desktop/PARTH/Work/Project3(AI Avatar)/Avatar/sdk/src/audio.ts): Low-latency WebAudio playback engine with queuing, precise millisecond elapsed-time tracking, and HTML5 Audio fallback.
- [`sdk/src/transport.ts`](file:///d:/Desktop/PARTH/Work/Project3(AI Avatar)/Avatar/sdk/src/transport.ts): WebSocket transport layer featuring exponential backoff auto-reconnection and heartbeat keep-alives.
- [`sdk/src/types.ts`](file:///d:/Desktop/PARTH/Work/Project3(AI Avatar)/Avatar/sdk/src/types.ts): Type definitions for viseme events, shapes (`open`, `round`, `dental`, `bilabial`, `labiodental`, `neutral`), and event listeners.

---

### 3.3 Interactive Showcase Application (`demo/`)

- [`demo/index.html`](file:///d:/Desktop/PARTH/Work/Project3(AI Avatar)/Avatar/demo/index.html): Modern single-page web app showcasing all features:
  - **Live Stage**: Real-time avatar container supporting instant switching between 2D Canvas and WebRTC streams (D-ID, Simli, Anam, Akool, HeyGen).
  - **Expert Profile & RAG Modal**: Interactive UI to create custom avatar experts, upload documents (PDF/DOCX/TXT), view indexed files, and manage knowledge bases.
  - **Continuous Voice Loop & Barge-In**: Real-time microphone turn-taking banner displaying active listening, thinking, and speaking states.
  - **HeyGen Cloud Studio**: Interface to submit video generation scripts and preview rendered MP4s.
  - **Telemetry Dashboard**: Live indicators for TTFF latency, viseme count, LLM response time, and provider readiness.

---

## 4. Technology Stack, APIs & Integrations

### 4.1 Backend Technologies
| Technology | Version / Purpose | Description |
| :--- | :--- | :--- |
| **Python** | 3.11+ | Core runtime environment |
| **FastAPI** | 0.115+ | Asynchronous high-throughput web framework |
| **Uvicorn** | Standard ASGI | Production-ready ASGI server with WebSockets support |
| **Pydantic v2** | 2.10+ | Strict data validation and environment configuration |
| **AioHTTP** | 3.11+ | Asynchronous HTTP client for provider communication |
| **PyPDF** | 5.3+ | Fast server-side PDF text extraction |
| **python-docx** | 1.1+ | Microsoft Word (.docx) document parsing |
| **Pytest & Pytest-Asyncio** | 8.3+ | Automated async test runner |

---

### 4.2 Large Language Models & RAG Engine
| Service / Library | Implementation | Latency / Cost |
| :--- | :--- | :--- |
| **Groq Cloud API** | `llama-3.3-70b-versatile` & `llama-3.1-8b-instant` | ~120–180ms TTFT (Ultra-Fast LPUs) |
| **Hybrid RAG Engine** | In-Memory Inverted Index + BM25 + Token Overlap | <5ms passage retrieval across uploaded PDFs |
| **Token Chunking** | 400-word sliding window with 50-word overlap | Optimized for conversational context retention |

---

### 4.3 Digital Human Video Streaming Providers
| Provider | Integration Type | Description |
| :--- | :--- | :--- |
| **D-ID** | WebRTC Live Streaming (`/talks/streams`) | Photorealistic digital presenters with sub-400ms latency |
| **Simli** | WebRTC Audio-to-Video API | Ultra-low latency facial animation streaming |
| **Anam.ai** | WebRTC Digital Human SDK (`@anam-ai/js-sdk`) | Realistic interactive persona streaming |
| **Akool** | Live Streaming API | Real-time interactive avatar video generation |
| **HeyGen** | Interactive Streaming & Cloud Video API v2 | Real-time streaming + Studio MP4 video rendering |

---

### 4.4 Speech Synthesis (TTS) & Phoneme Engines
| Provider / Tool | Format | Purpose |
| :--- | :--- | :--- |
| **Microsoft Edge Neural TTS** | MP3 Stream (~4KB/s) | 100% free neural speech with zero API key requirement |
| **Edge-TTS WordBoundary** | Millisecond metadata | Yields exact word start offsets and durations for lip sync |
| **Viseme Mapping Engine** | Keyframe timeline | Maps phonemes/letters to visual mouth shapes (`open`, `round`, etc.) |

---

### 4.5 Frontend & Client SDK Stack
| Technology | Role |
| :--- | :--- |
| **TypeScript 5.7+** | Type-safe SDK codebase |
| **Tsup / Rollup** | Dual bundle generator (ESM `dist/index.mjs` & CJS `dist/index.js` + DTS) |
| **HTML5 Canvas 2D** | 60 FPS procedural facial animation and eyelid/mouth synthesis |
| **WebAudio API** | Low-latency audio buffer decoding and playback synchronization |
| **Web Speech API** | Client-side speech-to-text with interim transcript streaming |
| **WebRTC API** | Direct peer-to-peer audio/video streaming with remote avatar engines |

---

## 5. Feature Matrix & Usage Guide

### 5.1 REST Microservice API Reference

#### 1. Create Conversational Session
- **Endpoint**: `POST /api/v1/sessions`
- **Request**:
  ```json
  {
    "avatar_id": "female"
  }
  ```
- **Response** (`201 Created`):
  ```json
  {
    "session_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "avatar_id": "female",
    "state": "created",
    "ws_url": "/api/v1/stream/3fa85f64-5717-4562-b3fc-2c963f66afa6"
  }
  ```

#### 2. Chat with RAG Document Knowledge
- **Endpoint**: `POST /api/v1/chat/respond`
- **Request**:
  ```json
  {
    "message": "What is the company refund policy?",
    "history": [
      { "role": "user", "content": "Hi" },
      { "role": "assistant", "content": "Hello! How can I assist you?" }
    ],
    "profile_id": "prof_abc123"
  }
  ```
- **Response** (`200 OK`):
  ```json
  {
    "reply": "According to the policy, refunds are processed within 14 business days.",
    "sources": [
      {
        "filename": "Refund_Policy_2026.pdf",
        "score": 8.45,
        "snippet": "All refund requests submitted within 30 days are processed within 14 business days..."
      }
    ]
  }
  ```

#### 3. Custom Expert Avatar Profiles & Document Upload
- **Create Profile**: `POST /api/v1/profiles`
  ```json
  {
    "name": "Dr. Aris — Medical Consultant",
    "persona": "female",
    "system_prompt": "You are Dr. Aris, a medical expert answering questions based on clinical guidelines."
  }
  ```
- **Upload Knowledge Document**: `POST /api/v1/profiles/{profile_id}/documents`
  - `Content-Type`: `multipart/form-data`
  - Form field: `file` (PDF, DOCX, TXT, MD)
- **List Profiles**: `GET /api/v1/profiles`
- **Delete Document**: `DELETE /api/v1/profiles/{profile_id}/documents/{doc_id}`

#### 4. WebRTC Video Session Negotiation
- **Request WebRTC Offer**: `POST /api/v1/sessions/{session_id}/webrtc/offer?provider=d-id&avatar_id=female`
- **Submit SDP Answer**: `POST /api/v1/sessions/{session_id}/webrtc/answer?provider=d-id`
- **Exchange ICE Candidate**: `POST /api/v1/sessions/{session_id}/webrtc/ice?provider=d-id`
- **Trigger Live WebRTC Speech**: `POST /api/v1/sessions/{session_id}/webrtc/speak?provider=d-id`

---

### 5.2 Real-Time WebSocket Streaming Protocol

Connect to `ws://localhost:8000/api/v1/stream/{session_id}`.

#### Client &rarr; Server Commands
1. **Speak**:
   ```json
   {
     "action": "speak",
     "text": "Hello! Welcome to our interactive platform.",
     "voice": "en-US-JennyNeural"
   }
   ```
2. **Interrupt (Barge-In)**:
   ```json
   {
     "action": "interrupt"
   }
   ```
3. **Ping / Heartbeat**:
   ```json
   {
     "action": "ping"
   }
   ```

#### Server &rarr; Client Events
1. **Connected Confirmation**: `{"type": "connected", "session_id": "..."}`
2. **Start of Speech Turn**: `{"type": "start", "speech_id": "..."}`
3. **Viseme Timeline**:
   ```json
   {
     "type": "viseme_timeline",
     "speech_id": "...",
     "events": [
       { "t": 0, "v": "open" },
       { "t": 120, "v": "dental" },
       { "t": 280, "v": "round" },
       { "t": 450, "v": "neutral" }
     ]
   }
   ```
4. **Audio Chunks**:
   ```json
   {
     "type": "audio_chunk",
     "speech_id": "...",
     "chunk_index": 0,
     "data": "<base64 encoded MP3 audio data>"
   }
   ```
5. **End of Speech Turn**: `{"type": "end", "speech_id": "..."}`
6. **Interrupted Notice**: `{"type": "interrupted", "speech_id": "..."}`

---

### 5.3 TypeScript SDK Integration (`@avatar-sdk/client`)

#### Option A: High-Level `AvatarWidget` (Drop-in UI)
```html
<!-- Container Slot -->
<div id="avatar-container" style="width: 400px; height: 500px;"></div>

<!-- Import SDK -->
<script type="module">
  import { AvatarWidget } from "http://localhost:8000/sdk/dist/index.mjs";

  const widget = new AvatarWidget({
    target: "#avatar-container",
    serverUrl: "http://localhost:8000",
    engine: "canvas",         // 'canvas' (2D Neural) | 'd-id' | 'anam' | 'simli'
    avatar: "female",         // 'female' (Emma) | 'male' (David)
    title: "Emma — AI Concierge",
    welcomeMessage: "Hello! How can I assist you today?",
    profileId: "prof_enterprise_rag" // Optional RAG knowledge profile
  });
</script>
```

#### Option B: Low-Level `AvatarClient` (Headless Custom UI)
```typescript
import { AvatarClient } from "@avatar-sdk/client";

const client = new AvatarClient({
  serverUrl: "ws://localhost:8000",
  avatarId: "female"
});

// 1. Connect WebSocket session
await client.connect();

// 2. Mount 2D Neural Canvas into DOM element
client.mount(document.getElementById("canvas-slot")!, "female");

// 3. Listen to avatar events
client.on("speaking", () => console.log("Avatar started speaking"));
client.on("viseme", ({ shape, timeMs }) => console.log(`Viseme: ${shape} at ${timeMs}ms`));
client.on("ended", () => console.log("Speech finished"));

// 4. Trigger speech
await client.speak("Hello! I am your custom digital human.");

// 5. Barge-in / Interrupt anytime
client.interrupt();
```

---

### 5.4 RAG Document Knowledge & Custom Expert Profile Creation
1. Open the demo app at `http://localhost:8000/demo/`.
2. Click **✨ Create Custom Expert Profile**.
3. Enter Profile Name (e.g. *"HR Benefits Advisor"*), Persona (*Female / Emma*), and System Prompt.
4. Drag and drop any `.pdf`, `.docx`, `.txt`, or `.md` file.
5. Click **✨ Save & Activate Profile**.
6. Ask questions via voice or text — the avatar will cite exact document passages and ground all responses in the uploaded files.

---

### 5.5 HeyGen Studio Cloud Video Generation
1. Switch to the **🎬 HeyGen Video Studio** tab in the demo application.
2. Select an avatar presenter from your connected HeyGen library.
3. Type the video script text.
4. Click **🚀 Generate Studio Video (HeyGen)**.
5. The cloud rendering engine processes the MP4 video and displays a live progress counter.
6. Once complete, preview the video directly in the browser or click **⬇️ Download Generated MP4 Video**.

---

## 6. Deployment & Configuration

### Environment Variables (`.env`)
```bash
# LLM Intelligence (Groq Cloud)
GROQ_API_KEY=gsk_your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile

# Real-Time TTS Configuration (Microsoft Edge Neural TTS - Free)
TTS_PROVIDER=edge-tts
EDGE_TTS_VOICE=en-US-JennyNeural
EDGE_TTS_VERIFY_SSL=false

# WebRTC Video Providers (Optional - populate as needed)
DID_API_KEY=your_did_api_key_here
SIMLI_API_KEY=your_simli_api_key_here
ANAM_API_KEY=your_anam_api_key_here
AKOOL_API_KEY=your_akool_api_key_here
HEYGEN_API_KEY=your_heygen_api_key_here

# Server Settings
PORT=8000
HOST=0.0.0.0
CORS_ORIGINS=*
```

### Running Locally with UV
```bash
# 1. Install dependencies
uv sync

# 2. Start backend server
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 3. Access Interactive Demo UI
# Open in browser: http://localhost:8000/demo/
```

### Running via Docker
```bash
# Build and launch container
docker compose up --build -d

# Verify logs
docker compose logs -f
```
