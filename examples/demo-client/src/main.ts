/**
 * Apex Travel & Flights — Client Application
 * Demonstrates how an independent business website embeds the Avatar SDK with 1 call.
 */
import { createAvatarWidget } from "@avatar-sdk/client";

// ── Drop-in AI Avatar Concierge Integration (D-ID Photorealistic Live Video) ──
const concierge = createAvatarWidget({
  target: "#ai-concierge-slot",
  serverUrl: "http://localhost:8000",
  engine: "d-id", // Photorealistic D-ID Live WebRTC Video Stream
  avatar: "emma", // Built-in persona (Alyssa on D-ID)
  voice: "en-US-JennyNeural",
  title: "Emma — AI Concierge",
  welcomeMessage: "Welcome to Apex Travel! Ask me anything about flights, hotel deals, or your upcoming vacation.",
  systemPrompt: "You are Emma, the friendly AI Travel Concierge at Apex Global Travel. Help travelers with flight queries, vacation suggestions, and baggage info. Keep answers natural and under 2 sentences.",
});

// Allow website elements (destination cards, search buttons) to interact with the concierge
(window as any).askConcierge = (query: string) => {
  concierge.ask(query);
};
