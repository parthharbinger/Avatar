# @avatar-sdk/client

> Embeddable real-time interactive AI avatar SDK — drop a photorealistic or 2D neural talking avatar into any web app in a few lines of code.

[![npm version](https://img.shields.io/badge/npm-0.1.0-blue.svg)](https://www.npmjs.com)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.4+-3178C6.svg?style=flat&logo=typescript)](https://www.typescriptlang.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## 📦 Installation

```bash
# npm
npm install @avatar-sdk/client

# yarn
yarn add @avatar-sdk/client

# pnpm
pnpm add @avatar-sdk/client
```

Or import directly from CDN in plain HTML/ES modules:
```html
<script type="module">
  import { createAvatarWidget } from "https://cdn.jsdelivr.net/npm/@avatar-sdk/client/dist/index.mjs";
</script>
```

---

## 🚀 Quick Start

### Option A: 1-Line Drop-in Widget (Recommended)

Drop a complete interactive AI avatar (with live voice microphone, Groq LLM intelligence, WebRTC video streaming, and lip-sync canvas) into any web app:

```typescript
import { createAvatarWidget } from "@avatar-sdk/client";

// Mount into any HTML container element (or floating: true for a bottom-right assistant)
const widget = createAvatarWidget({
  target: "#ai-concierge-slot",
  serverUrl: "http://localhost:8000",
  engine: "anam",                      // "anam" | "d-id" | "simli" | "akool" | "canvas"
  avatar: "female",                    // "female" (Emma) or "male" (David)
  title: "Emma — AI Concierge",
  welcomeMessage: "Hello! How can I assist you today?",
  systemPrompt: "You are Emma, a friendly AI concierge. Keep answers concise and helpful.",
});

// Programmatically trigger questions or speech
await widget.ask("Can you tell me about your flight deals?");
```

---

### Option B: Headless SDK (Custom UI Architecture)

For developers building a fully custom UI layout:

```typescript
import { AvatarClient } from "@avatar-sdk/client";

// 1. Create client instance
const avatar = new AvatarClient({
  serverUrl: "ws://localhost:8000",
  avatarId: "female",
});

// 2. Connect session
await avatar.connect();

// 3. Mount canvas into any element
avatar.mount(document.querySelector("#avatar-container")!);

// 4. Speak text
avatar.speak("Hello! I am your real-time interactive AI avatar.");

// 5. Interrupt mid-speech (barge-in)
avatar.interrupt();

// 6. Clean up
await avatar.destroy();
```

---

## ⚙️ Widget Options Reference (`AvatarWidgetOptions`)

| Option | Type | Default | Description |
|---|---|---|---|
| `target` | `HTMLElement \| string` | `document.body` | Target container element or CSS selector string (e.g. `"#my-slot"`). |
| `floating` | `boolean` | `false` | When `true`, renders as a floating interactive assistant pinned to the bottom-right. |
| `serverUrl` | `string` | `"http://localhost:8000"` | Base URL of the backend avatar microservice. |
| `engine` | `string` | `"d-id"` | Avatar streaming engine: `'anam'` \| `'d-id'` \| `'simli'` \| `'akool'` \| `'canvas'`. |
| `avatar` | `string` | `"female"` | Avatar persona: `'female'` (Emma/Mia) or `'male'` (David/Gabriel). |
| `voice` | `string` | auto-selected | Neural voice name (e.g. `'en-US-JennyNeural'`, `'en-US-ChristopherNeural'`). |
| `title` | `string` | `"AI Concierge"` | Header title displayed on the widget. |
| `welcomeMessage` | `string` | `"Hello!"` | First greeting spoken and displayed in chat history. |
| `systemPrompt` | `string` | default prompt | System instructions guiding the conversational LLM persona. |

---

## 🛠️ Widget API Methods

```typescript
// Ask conversational question (Groq LLM generates answer and speaks it)
const reply = await widget.ask("What is the refund policy?");

// Speak arbitrary text directly
await widget.speak("Your booking has been confirmed.");

// Switch between Male (David) and Female (Emma) personas dynamically
await widget.setAvatar("male");
await widget.setAvatar("female");

// Switch avatar streaming provider
await widget.setEngine("anam");
await widget.setEngine("canvas");

// Barge-in interruption (instantly halts speaking mid-sentence)
widget.interrupt();

// Clean up DOM and disconnect WebRTC / WebSocket streams
await widget.destroy();
```

---

## 📡 Headless Client Events (`AvatarClient`)

```typescript
avatar.on("connected",    ({ sessionId }) => console.log("Connected session:", sessionId));
avatar.on("speaking",     ({ speechId })  => console.log("Now speaking:", speechId));
avatar.on("ended",        ({ speechId })  => console.log("Finished speaking:", speechId));
avatar.on("interrupted",  ({ speechId })  => console.log("Interrupted:", speechId));
avatar.on("disconnected", ({ reason })    => console.log("Disconnected:", reason));
avatar.on("error",        ({ message })   => console.error("Error:", message));
```

---

## 🧪 Testing & Building

```bash
# Run unit tests
npm test

# Build ESM + CJS + TypeScript types
npm run build
```

---

## 📄 License
MIT License.
