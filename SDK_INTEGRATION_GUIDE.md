# AI Avatar SDK (`@avatar-sdk/client`) — Integration Guide

> A lightweight, framework-agnostic TypeScript/JavaScript SDK to drop a talking, real-time interactive AI avatar into any web application in minutes.

---

## 📦 1. Installation

Install the package into your web project:

```bash
# npm
npm install @avatar-sdk/client

# yarn
yarn add @avatar-sdk/client

# pnpm
pnpm add @avatar-sdk/client
```

Or load directly via CDN in plain HTML:
```html
<script type="module">
  import { createAvatarWidget } from "https://cdn.jsdelivr.net/npm/@avatar-sdk/client/dist/index.mjs";
</script>
```

---

## ⚡ 2. Quickstart Integrations by Framework

### A. Vanilla JavaScript / Plain HTML

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>My App with AI Avatar</title>
</head>
<body>

  <!-- Container element where the avatar will render -->
  <div id="avatar-slot" style="width: 360px; height: 500px;"></div>

  <script type="module">
    import { createAvatarWidget } from "@avatar-sdk/client";

    const widget = createAvatarWidget({
      target: "#avatar-slot",
      serverUrl: "http://localhost:8000",
      engine: "anam",                      // "anam" | "d-id" | "simli" | "akool" | "canvas"
      avatar: "female",                    // "female" (Emma) or "male" (David)
      title: "AI Customer Concierge",
      welcomeMessage: "Hello! How can I assist you today?",
      systemPrompt: "You are a friendly customer concierge. Keep answers helpful and concise.",
    });

    // Make avatar speak programmatically
    widget.speak("Welcome to our online store!");
  </script>
</body>
</html>
```

---

### B. React (Next.js App Router / Vite / CRA)

```tsx
import React, { useEffect, useRef } from "react";
import { createAvatarWidget, AvatarWidget } from "@avatar-sdk/client";

export function AIAvatarConcierge() {
  const containerRef = useRef<HTMLDivElement>(null);
  const widgetRef = useRef<AvatarWidget | null>(null);

  useEffect(() => {
    if (!containerRef.current || widgetRef.current) return;

    // Initialize Widget
    widgetRef.current = createAvatarWidget({
      target: containerRef.current,
      serverUrl: process.env.NEXT_PUBLIC_AVATAR_API_URL || "http://localhost:8000",
      engine: "anam", // Photorealistic WebRTC or "canvas"
      avatar: "female",
      title: "Emma — Support Specialist",
      welcomeMessage: "Hi there! Feel free to ask me anything.",
      systemPrompt: "You are Emma, an AI customer support specialist.",
    });

    // Clean up on component unmount
    return () => {
      widgetRef.current?.destroy();
      widgetRef.current = null;
    };
  }, []);

  return (
    <div className="avatar-wrapper">
      <div ref={containerRef} style={{ width: "360px", minHeight: "480px" }} />
    </div>
  );
}
```

---

### C. Vue 3 (Composition API)

```vue
<template>
  <div ref="avatarContainer" class="avatar-container"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';
import { createAvatarWidget, type AvatarWidget } from '@avatar-sdk/client';

const avatarContainer = ref<HTMLElement | null>(null);
let widget: AvatarWidget | null = null;

onMounted(() => {
  if (avatarContainer.value) {
    widget = createAvatarWidget({
      target: avatarContainer.value,
      serverUrl: 'http://localhost:8000',
      engine: 'anam',
      avatar: 'female',
      title: 'AI Assistant',
      welcomeMessage: 'How can I help you today?',
    });
  }
});

onUnmounted(() => {
  widget?.destroy();
});
</script>
```

---

## ⚙️ 3. Full Configuration Reference (`AvatarWidgetOptions`)

| Option | Type | Default | Description |
|---|---|---|---|
| `target` | `HTMLElement \| string` | `document.body` | Container element or CSS selector string (e.g. `"#my-slot"`). |
| `floating` | `boolean` | `false` | When `true`, renders as a floating widget pinned to the bottom-right corner. |
| `serverUrl` | `string` | `"http://localhost:8000"` | Base URL of the backend microservice. |
| `engine` | `string` | `"d-id"` | Avatar Engine: `'anam'` \| `'d-id'` \| `'simli'` \| `'akool'` \| `'canvas'`. |
| `avatar` | `string` | `"female"` | Presenter persona: `'female'` (Emma/Mia) or `'male'` (David/Gabriel). |
| `voice` | `string` | auto-selected | Voice name (e.g. `'en-US-JennyNeural'`, `'en-US-ChristopherNeural'`). |
| `title` | `string` | `"AI Concierge"` | Header display title in the UI. |
| `welcomeMessage` | `string` | `"Hello!"` | First greeting spoken and displayed in chat history. |
| `systemPrompt` | `string` | default prompt | System instructions governing conversational LLM replies. |

---

## 🛠️ 4. Programmatic API Methods (`AvatarWidget`)

```typescript
// 1. Ask conversational question (Avatar thinks via Groq LLM and replies with voice)
const replyText = await widget.ask("What are your business opening hours?");

// 2. Direct speech output (Avatar speaks exact phrase)
await widget.speak("Thank you for your order! Your confirmation is #48291.");

// 3. Switch between Male and Female personas dynamically
await widget.setAvatar("male");   // Switches to David
await widget.setAvatar("female"); // Switches to Emma

// 4. Switch avatar streaming engine
await widget.setEngine("anam");   // Switches to Anam.ai Digital Human
await widget.setEngine("canvas"); // Switches to Lightweight 2D Canvas

// 5. Barge-in interruption (instantly halts speaking mid-sentence)
widget.interrupt();

// 6. Clean up resources & disconnect streams
await widget.destroy();
```

---

## 🎨 5. Headless SDK for Custom UI Architecture (`AvatarClient`)

If your project requires complete custom UI controls without the default widget:

```typescript
import { AvatarClient } from "@avatar-sdk/client";

// 1. Create client instance
const client = new AvatarClient({
  serverUrl: "ws://localhost:8000",
  avatarId: "female",
});

// 2. Subscribe to real-time events
client.on("connected", ({ sessionId }) => console.log("Connected session:", sessionId));
client.on("speaking", () => console.log("Avatar is speaking"));
client.on("interrupted", () => console.log("Speech interrupted"));
client.on("error", (err) => console.error("Avatar error:", err));

// 3. Connect & Mount
await client.connect();
client.mount(document.getElementById("my-custom-canvas")!);

// 4. Trigger speech
client.speak("Hello! This is completely custom UI.");
```

---

## 🔒 6. Production Best Practices

1. **Host Behind HTTPS/WSS**: Always host both backend and frontend behind SSL in production to ensure WebRTC camera/mic permissions and WebSockets connect seamlessly.
2. **CORS Configuration**: Set `CORS_ORIGINS=["https://your-frontend-domain.com"]` in your backend `.env` file.
3. **Session Re-use**: Use a single `AvatarWidget` instance per page and call `widget.destroy()` when unmounting or navigating away.
