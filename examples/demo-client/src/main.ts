/**
 * Apex Travel & Flights — Client Application
 * Demonstrates how an independent business website embeds the Avatar SDK with 1 call
 * and dynamically switches between Emma (Female) and David (Male) personas.
 */
import { createAvatarWidget } from "@avatar-sdk/client";

// ── Drop-in AI Avatar Concierge Integration ──
const concierge = createAvatarWidget({
  target: "#ai-concierge-slot",
  serverUrl: "http://localhost:8000",
  engine: "d-id", // Photorealistic D-ID Live WebRTC Video Stream with 2D fallback
  avatar: "female", // Emma by default
  voice: "en-US-JennyNeural",
  title: "Emma — AI Concierge",
  welcomeMessage: "Welcome to Apex Travel! Ask me anything about flights, hotel deals, or your upcoming vacation.",
  systemPrompt: "You are Emma, the friendly AI Travel Concierge at Apex Global Travel. Help travelers with flight queries, vacation suggestions, and baggage info. Keep answers natural, under 2 sentences, and in pure plain text without emojis, symbols, logos, or markdown formatting.",
});

// Expose persona switching on window for website controls
(window as any).switchPersona = (gender: "female" | "male") => {
  const isMale = gender === "male";
  concierge.setAvatar(isMale ? "male" : "female");

  // Update website UI active pills
  const btnEmma = document.getElementById("portal-btn-emma");
  const btnDavid = document.getElementById("portal-btn-david");
  if (btnEmma && btnDavid) {
    if (isMale) {
      btnDavid.classList.add("active");
      btnEmma.classList.remove("active");
    } else {
      btnEmma.classList.add("active");
      btnDavid.classList.remove("active");
    }
  }
};

// Expose ask method for flight and destination card clicks
(window as any).askConcierge = (query: string) => {
  concierge.ask(query);
};

// Expose engine switcher
(window as any).switchEngine = (engine: "d-id" | "simli" | "anam" | "akool" | "heygen" | "canvas") => {
  concierge.setEngine(engine);
};
