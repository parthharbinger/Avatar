# @avatar-sdk/client

> Embeddable real-time 2D AI avatar — drop a talking, lip-synced avatar into any web app in a few lines of code.

## Installation

```bash
npm install @avatar-sdk/client
```

Or load from a CDN (UMD/ESM):
```html
<script type="module">
  import { AvatarClient } from "./dist/index.mjs";
</script>
```

---

## Quick Start

### Option A: 1-Line Drop-in Widget (Fastest)

Drop a complete interactive talking AI avatar (with live voice mic, LLM chat, and lip-sync canvas) into any web app:

```typescript
import { createAvatarWidget } from "@avatar-sdk/client";

// Mount directly into any HTML element (or use floating: true for bottom-right assistant)
createAvatarWidget({
  target: "#avatar-container",
  serverUrl: "http://localhost:8000",
  avatar: "emma", // built-in persona (no local assets needed!)
  title: "AI Concierge",
  welcomeMessage: "Hello! How can I help you today?",
  systemPrompt: "You are a helpful and concise AI assistant.",
});
```

### Option B: Headless SDK (Custom UI Architecture)

For developers building a custom UI layout:

```typescript
import { AvatarClient } from "@avatar-sdk/client";

// 1. Create client
const avatar = new AvatarClient({
  serverUrl: "ws://localhost:8000",
  avatarId: "female",
});

// 2. Connect session
await avatar.connect();

// 3. Mount canvas into any element
avatar.mount(document.querySelector("#avatar-container")!);

// 4. Speak
avatar.speak("Hello! I am your real-time AI avatar.");

// 5. Interrupt mid-speech (barge-in)
avatar.interrupt();

// 6. Clean up
await avatar.destroy();
```

---

## API Reference

### `new AvatarClient(options)`

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `serverUrl` | `string` | **required** | WebSocket URL of the backend, e.g. `ws://localhost:8000` |
| `avatarId` | `string` | `"default"` | Avatar identity to use |
| `reconnectDelayMs` | `number` | `2000` | Delay between reconnect attempts (ms) |
| `maxReconnectAttempts` | `number` | `5` | Max reconnect retries before giving up |

---

### `avatar.connect(): Promise<void>`
Creates a REST session on the server and opens the WebSocket connection. Resolves when the connection is fully established.

### `avatar.mount(container: HTMLElement): void`
Renders the 2D avatar canvas inside the given DOM element. Call after `connect()`.

### `avatar.speak(text: string): void`
Sends text to the server to be spoken. If already speaking, will interrupt the current speech first (barge-in).

### `avatar.interrupt(): void`
Immediately stops the avatar's current speech, clears audio, and resets the mouth to neutral.

### `avatar.on(event, listener): this`
Subscribe to avatar events.

### `avatar.off(event, listener): this`
Unsubscribe from avatar events.

### `avatar.destroy(): Promise<void>`
Stops all audio, removes the canvas, closes the WebSocket, and cleans up all listeners.

### `avatar.state: ConnectionState`
Current connection state: `"idle" | "connecting" | "connected" | "reconnecting" | "closed"`.

---

## Events

```typescript
avatar.on("connected",    ({ sessionId }) => console.log("Connected:", sessionId));
avatar.on("speaking",     ({ speechId })  => console.log("Now speaking:", speechId));
avatar.on("ended",        ({ speechId })  => console.log("Finished:", speechId));
avatar.on("interrupted",  ({ speechId })  => console.log("Interrupted:", speechId));
avatar.on("disconnected", ({ reason })    => console.log("Disconnected:", reason));
avatar.on("error",        ({ message })   => console.error("Error:", message));
avatar.on("viseme",       ({ shape, timeMs }) => console.log("Mouth:", shape));
```

| Event | Payload | Description |
|-------|---------|-------------|
| `connected` | `{ sessionId }` | WebSocket connection established |
| `speaking` | `{ speechId }` | Avatar has started speaking |
| `ended` | `{ speechId }` | Speech finished naturally |
| `interrupted` | `{ speechId }` | Speech was cut short |
| `disconnected` | `{ reason }` | Connection lost |
| `error` | `{ message }` | Server or network error |
| `viseme` | `{ shape, timeMs }` | Current mouth shape update |

---

## Building

```bash
npm run build      # Build ESM + CJS + types
npm run dev        # Watch mode
npm test           # Run tests
```

---

## WebSocket Protocol

The SDK communicates with the backend using this message protocol:

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
{ "type": "viseme_timeline", "speech_id": "...", "events": [{"t": 0, "v": "neutral"}] }
{ "type": "audio_chunk", "speech_id": "...", "chunk_index": 0, "data": "<base64 MP3>" }
{ "type": "end", "speech_id": "..." }
{ "type": "interrupted", "speech_id": "..." }
{ "type": "error", "message": "..." }
```

---

## TTFF Measurement

The SDK automatically logs Time-To-First-Frame to the browser console:
```
[AvatarSDK] TTFF: 287ms
```
Target: **< 500ms** on local network.
