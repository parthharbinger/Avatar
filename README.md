# Real-Time 2D AI Avatar — Backend Microservice + Frontend SDK

> A zero-budget, embeddable real-time talking avatar system. Your own HeyGen — as a microservice and SDK.

[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.141-green)](https://fastapi.tiangolo.com)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.4-blue)](https://typescriptlang.org)

---

## What This Is

A production-grade microservice that turns text input into a **live, lip-synced 2D avatar** streamed to any web app via WebSocket — with an embeddable TypeScript SDK that lets a developer integrate it in under 30 minutes.

**Architecture**: Text → Edge-TTS → Viseme Mapper → WebSocket stream → Browser Canvas Renderer

---

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- Docker + Docker Compose (optional)

### 1. Clone & Setup

```bash
git clone <your-repo-url>
cd Avatar
cp .env.example .env
```

### 2. Run with Docker (Recommended)

```bash
docker compose up --build
```

Server starts at: http://localhost:8000

### 3. Run Locally (Development)

```bash
# Install dependencies
pip install uv
uv sync

# Start the server
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Open the Demo

Open `demo/index.html` in your browser (or serve it with any static server):

```bash
cd demo
npx serve .
```

Navigate to http://localhost:3000, click **Connect**, then **Speak**.

---

## API Reference

Interactive docs auto-generated at:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Service health + active session count |
| `POST` | `/api/v1/sessions` | Create a new avatar session |
| `GET` | `/api/v1/sessions/{id}` | Get session info |
| `DELETE` | `/api/v1/sessions/{id}` | Terminate a session |
| `WS` | `/api/v1/stream/{id}` | Real-time avatar stream |

### WebSocket Protocol

**Client → Server:**
```json
{ "action": "speak", "text": "Hello world" }
{ "action": "interrupt" }
{ "action": "ping" }
```

**Server → Client:**
```json
{ "type": "connected", "session_id": "..." }
{ "type": "start", "speech_id": "..." }
{ "type": "viseme_timeline", "events": [{"t": 0, "v": "neutral"}, {"t": 80, "v": "open"}] }
{ "type": "audio_chunk", "chunk_index": 0, "data": "<base64 MP3>" }
{ "type": "end", "speech_id": "..." }
{ "type": "interrupted", "speech_id": "..." }
```

---

## SDK Usage

```typescript
import { AvatarClient } from "@avatar-sdk/client";

const avatar = new AvatarClient({ serverUrl: "ws://localhost:8000" });

await avatar.connect();
avatar.mount(document.querySelector("#avatar"));
avatar.speak("Hello! I am your AI avatar.");

// Interrupt mid-speech
avatar.interrupt();

// Cleanup
await avatar.destroy();
```

See [sdk/README.md](./sdk/README.md) for full API reference.

---

## Running Tests

```bash
# Backend tests (19 tests)
uv run pytest tests/ -v

# SDK build verification
cd sdk && npm run build
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TTS_PROVIDER` | `edge-tts` | TTS provider (`edge-tts`, `elevenlabs`) |
| `EDGE_TTS_VOICE` | `en-US-AriaNeural` | Edge-TTS voice name |
| `ELEVENLABS_API_KEY` | — | ElevenLabs API key (if using ElevenLabs) |
| `SESSION_TIMEOUT_SECONDS` | `300` | Idle session TTL |
| `MAX_CONCURRENT_SESSIONS` | `20` | Max active sessions |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

---

## Architecture Overview

See [ARCHITECTURE.md](./ARCHITECTURE.md) for full design decisions, trade-off analysis, latency measurements, and scalability path.

### Key Design Choice: Client-Side 2D Rendering

Instead of encoding avatar video server-side (which requires GPU + expensive infrastructure), we stream **audio chunks + viseme timeline** to the browser, where a Canvas-based renderer animates the avatar locally. This achieves:

- **$0 running cost** — no GPU required
- **< 400ms TTFF** — no video encoding bottleneck  
- **~32KB/s bandwidth** — vs 500KB–2MB/s for video streaming

---

## Known Limitations

- Single-instance only (in-memory sessions, no clustering)
- Viseme timing is approximated from character rate (~77ms/char)
- Voice input (ASR) is configured but not yet wired
- 2D geometric avatar (photorealism is out of scope)

---

## Project Structure

```
Avatar/
├── app/                    # FastAPI backend
│   ├── api/               # REST + WebSocket routes
│   ├── sessions/          # Session state machine
│   ├── tts/               # TTS adapter (Edge-TTS, ElevenLabs)
│   ├── viseme/            # Phoneme → mouth shape mapper
│   ├── orchestration/     # Async TTS → stream pipeline
│   ├── config.py          # Pydantic settings
│   └── main.py            # FastAPI app + lifespan
├── sdk/                   # TypeScript SDK (@avatar-sdk/client)
│   ├── src/
│   │   ├── client.ts      # AvatarClient main class
│   │   ├── transport.ts   # WebSocket manager + reconnect
│   │   ├── audio.ts       # Web Audio API chunk player
│   │   ├── renderer2d.ts  # Canvas avatar renderer
│   │   └── types.ts       # Public type definitions
│   └── dist/              # Built SDK (ESM + CJS + types)
├── demo/                  # Minimal integration example
│   └── index.html
├── tests/                 # pytest suite (19 tests)
├── ARCHITECTURE.md
├── Dockerfile
└── docker-compose.yml
```
