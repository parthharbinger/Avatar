# Apex Travel & Flights — Client Demonstration App

An independent, distinct-domain web application (Travel & Vacation Booking Platform) demonstrating how any third-party app can drop in an interactive talking AI Avatar in **3 lines of code** using `@avatar-sdk/client`.

---

## 🌟 Zero-Boilerplate Client Integration

Notice that this client project has:
- ❌ **No local image assets** copied into the project.
- ❌ **No HTML canvas or lip-sync drawing code**.
- ❌ **No WebRTC signaling or audio decoding code**.
- ✅ **Just 3 lines of JavaScript** importing `@avatar-sdk/client`!

---

## 💻 How the SDK is Embedded in [`src/main.ts`](./src/main.ts)

```typescript
import { createAvatarWidget } from "@avatar-sdk/client";

// Initialize AI Travel Concierge Avatar in 1 call:
const concierge = createAvatarWidget({
  target: "#ai-concierge-slot",      // Any HTML element or selector (or floating: true)
  serverUrl: "http://localhost:8000",
  avatar: "emma",                    // Automatically resolves built-in persona
  title: "Emma — AI Concierge",
  welcomeMessage: "Welcome to Apex Travel! Ask me anything about flights or vacation deals.",
  systemPrompt: "You are Emma, Apex Travel's AI concierge. Answer flight queries politely and concisely.",
});
```

---

## 🚀 Running the Client App

### 1. Ensure Backend Service is Running
```bash
cd Avatar
uv run uvicorn app.main:app --reload --port 8000
```

### 2. Launch Client Website
```bash
cd demo-client
npm install
npm run dev
```

Open your browser at:
👉 **`http://localhost:5173/`**

---

## 🎯 Features Included Automatically by the SDK

1. **Photorealistic Synced Lip-Sync & Blinking**: Smooth Canvas rendering powered by backend WordBoundary phoneme timelines.
2. **🎙️ Voice Microphone Input**: Click the mic icon to ask questions with your voice.
3. **Conversational AI (Groq LLM)**: Intelligent travel assistance with real-time audio replies in `< 200 ms`.
4. **Barge-In Interruption**: Supports immediate mid-speech interruptions.
5. **Interactive Website Hooks**: Clicking travel destination cards triggers contextual questions directly to the concierge.
