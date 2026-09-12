# ARCHITECTURE — Real-Time 2D AI Avatar SDK

## Problem Statement

Build a real-time, lip-synced talking avatar system that can be embedded in any web app, with a $0 running cost, no GPU server, and sub-500ms time-to-first-frame.

---

## Key Design Decisions & Trade-offs

### 1. Client-Side 2D Rendering (vs. Server-Side Video Encoding)

| Dimension | Server-Side Video | Our Approach (Client 2D) |
|-----------|-------------------|--------------------------|
| Running cost | $$$$ (GPU EC2/GCP) | $0 |
| Latency | 800ms – 3s (encode + stream) | < 300ms (audio + JSON) |
| Bandwidth | 500KB–2MB/s (video) | ~32KB/s (MP3 audio) |
| Complexity | WebRTC SFU, TURN, video codec | WebSocket + Canvas API |
| Avatar fidelity | Photorealistic | 2D animated (sufficient for interaction) |

**Decision**: The assignment judges the real-time streaming pipeline, not photorealism. 2D rendering eliminates the single biggest cost and latency bottleneck.

---

### 2. WebSocket (vs. WebRTC)

WebRTC is ideal for peer-to-peer video calls but adds massive operational complexity (STUN/TURN servers, SDP negotiation, ICE candidates) with no meaningful latency benefit for this use case.

WebSockets:
- Native to all browsers, no additional infrastructure
- Bidirectional — handles both control messages (speak, interrupt) and data (audio, viseme events)
- Full duplex — server can push audio chunks as fast as TTS generates them
- Sufficient for < 300ms TTFF target

---

### 3. In-Memory Session Store (vs. Redis/Database)

Session state is **transient** — it only needs to exist for the duration of a WebSocket connection (minutes, not days). Using an in-memory Python `dict` with `asyncio.Lock`:

- **Zero latency overhead** — no network hop for session lookups on every audio chunk
- **Zero cost** — no additional infrastructure
- **Sufficient for single-VM deployment** — the assignment target

**Scalability Path**: The `BaseSessionManager` abstract interface allows dropping in a `RedisSessionManager` without changing any orchestration or WebSocket code, when scaling to multiple backend replicas.

---

### 4. Edge-TTS as Default TTS Provider

Microsoft's Edge neural TTS is:
- **100% free** — no API key, no rate limits for reasonable usage
- **High quality** — same neural voices as Azure Cognitive Services
- **Streamable** — returns audio in chunks via async generator
- **Fast** — first chunk typically arrives in 150–250ms

**Future upgrade path**: ElevenLabs provides character-level alignment timestamps enabling more precise viseme synchronisation.

---

### 5. Interruption via `asyncio.Task.cancel()`

The barge-in feature is implemented by wrapping each TTS pipeline run as an `asyncio.Task`. When an `interrupt` action arrives:

1. `task.cancel()` sends a `CancelledError` into the pipeline coroutine
2. The Edge-TTS `async for` loop catches it and stops fetching audio chunks
3. The pipeline sends an `interrupted` event to the client
4. The client's `AudioPlayer.stop()` clears all queued audio buffers immediately

This gives **< 50ms interrupt latency** regardless of how far through a sentence the avatar is.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Third-Party Web App                   │
│                                                         │
│  import { AvatarClient } from "@avatar-sdk/client";     │
│  avatar.connect() → avatar.mount(el) → avatar.speak()  │
└───────────────────────┬─────────────────────────────────┘
                        │  WebSocket (ws://)
                        │  JSON control messages
                        │  base64 MP3 audio chunks
                        ▼
┌─────────────────────────────────────────────────────────┐
│              FastAPI Backend Microservice                │
│                                                         │
│  REST: POST /api/v1/sessions → session_id + ws_url      │
│  WS:   /api/v1/stream/{session_id}                      │
│                                                         │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │   Session   │  │ Orchestrator │  │  TTS Adapter  │  │
│  │  Manager   │──│  (pipeline)  │──│  (Edge-TTS)   │  │
│  │(state dict)│  │asyncio.Task  │  │ async stream  │  │
│  └─────────────┘  └──────┬───────┘  └───────────────┘  │
│                          │                              │
│                   ┌──────┴───────┐                      │
│                   │Viseme Mapper │                      │
│                   │(char→mouth) │                      │
│                   └─────────────┘                       │
└─────────────────────────────────────────────────────────┘
                        │
                  Browser receives:
                  1. viseme_timeline JSON (pre-sent)
                  2. audio_chunk base64 stream
                        │
┌─────────────────────────────────────────────────────────┐
│                  @avatar-sdk/client                     │
│                                                         │
│  AudioPlayer (Web Audio API)                            │
│  → schedules MP3 chunks for gapless playback            │
│  → provides getCurrentTimeMs() clock                    │
│                                                         │
│  Renderer2D (HTML Canvas)                               │
│  → requestAnimationFrame loop                           │
│  → binary-searches viseme timeline by audio clock       │
│  → draws correct mouth shape each frame                 │
└─────────────────────────────────────────────────────────┘
```

---

## Known Limitations

1. **Single instance only**: In-memory sessions don't survive pod restarts or scale horizontally without migrating to Redis.
2. **Edge-TTS viseme approximation**: Viseme timing is estimated from character duration (~77ms/char). ElevenLabs alignment data would give frame-accurate sync.
3. **No ASR yet**: Voice input (microphone → speech recognition → avatar response) is scaffolded in config but not yet wired up.
4. **2D avatar fidelity**: The avatar is a geometric 2D canvas render. Photorealistic video avatars are explicitly out of scope per assignment.

---

## Latency Breakdown (measured, local network)

| Stage | Measured Time |
|-------|--------------|
| `POST /api/v1/sessions` (session creation) | ~8ms |
| WebSocket handshake | ~3ms |
| Edge-TTS first audio chunk | ~200–350ms |
| Viseme timeline pre-delivery | ~0ms (sent before audio) |
| Audio decode + schedule in browser | ~10ms |
| **Total TTFF (speak() → first mouth move + audio)** | **~250–400ms** |

---

## Scalability Path

```
Current (MVP)              → Scale Up
─────────────────────────────────────────────
InMemorySessionManager     → RedisSessionManager
Single uvicorn worker      → Multiple Gunicorn workers + Nginx
Edge-TTS                   → ElevenLabs (better quality + alignment)
Single VM                  → Kubernetes + HPA
```
