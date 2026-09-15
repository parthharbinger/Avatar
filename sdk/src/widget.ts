/**
 * AvatarWidget â€” Drop-in plug-and-play AI Avatar component.
 * Embeds photorealistic live video streaming avatar powered by D-ID, Simli, Anam.ai, Akool, and HeyGen with Groq LLM intelligence.
 */
import { AvatarClient } from "./client";
import { Renderer2D } from "./renderer2d";

export interface AvatarWidgetOptions {
  /** Target container element or CSS selector string (e.g. "#ai-concierge-slot") */
  target?: HTMLElement | string;
  /** Set to true to render as a floating bottom-right interactive assistant */
  floating?: boolean;
  /** Server URL of the avatar backend, e.g. "http://localhost:8000" */
  serverUrl?: string;
  /** Avatar engine: 'd-id' | 'simli' | 'anam' | 'akool' | 'heygen' | 'canvas'. Default: 'd-id' */
  engine?: "d-id" | "simli" | "anam" | "akool" | "heygen" | "canvas" | "edge-tts" | "webrtc";
  /** Avatar persona: 'female' / 'emma', 'male' / 'david' */
  avatar?: string;
  /** Voice name, e.g. 'en-US-JennyNeural', 'en-US-ChristopherNeural' */
  voice?: string;
  /** Title header displayed in the widget */
  title?: string;
  /** Initial welcome message spoken/displayed on startup */
  welcomeMessage?: string;
  /** Custom system prompt guiding the conversational AI persona */
  systemPrompt?: string;
  /** Optional avatar expert profile ID â€” enables RAG document knowledge for this profile */
  profileId?: string;
}

const DID_POSTER_FEMALE = "https://clips-presenters.d-id.com/v2/Alyssa_NoHands_BlackShirt_Home/Mvn6Nalx90/y0J6MTfOaZ/image.png";
const DID_POSTER_MALE = "https://clips-presenters.d-id.com/v2/Adam/0GLJgELXjc/j0HIbyxjap/image.png";

export class AvatarWidget {
  private client: AvatarClient | null = null;
  private renderer: Renderer2D | null = null;
  private container: HTMLElement;
  private rootEl: HTMLElement;
  private videoEl: HTMLVideoElement | null = null;
  private canvasSlot: HTMLElement | null = null;
  private chatHistory: Array<{ role: string; content: string }> = [];
  private options: Required<AvatarWidgetOptions>;
  private isListening = false;
  private recognition: any = null;

  // â”€â”€ Continuous Voice Loop â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  /** When true, mic auto-restarts after each turn (hands-free conversation loop) */
  private voiceLoopActive = false;
  /** Current state of the voice conversation turn-taking FSM */
  private convState: "idle" | "listening" | "processing" | "speaking" = "idle";
  /** Timer to debounce final transcript submission */
  private silenceTimer: ReturnType<typeof setTimeout> | null = null;
  /** Accumulated interim transcript during current mic turn */
  private interimTranscript = "";
  /** AbortController for in-flight LLM ask() fetch â€” enables barge-in cancellation */
  private askAbortController: AbortController | null = null;

  // â”€â”€ RAG Profile â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  /** Currently selected expert profile ID for RAG-augmented responses */
  private activeProfileId: string | null = null;

  // WebRTC Streaming State (D-ID / Simli / Anam / Akool / HeyGen)
  private peerConnection: RTCPeerConnection | null = null;
  private anamClient: any = null;
  private activeSessionId: string | null = null;
  private activeStreamId: string | null = null;
  private providerSessionId: string | null = null;
  private isConnecting = false;

  constructor(options: AvatarWidgetOptions = {}) {
    const serverUrl = options.serverUrl || "http://localhost:8000";
    const engine = options.engine || "d-id";
    const avatar = (options.avatar || "female").toLowerCase();
    const isMale = avatar === "male" || avatar === "david";

    this.options = {
      target: options.target || document.body,
      floating: options.floating ?? false,
      serverUrl,
      engine,
      avatar: isMale ? "male" : "female",
      voice: options.voice || (isMale ? "en-US-ChristopherNeural" : "en-US-JennyNeural"),
      title: options.title || (isMale ? "David â€” AI Concierge" : "Emma â€” AI Concierge"),
      welcomeMessage: options.welcomeMessage || "Hello! How can I assist you today?",
      systemPrompt: options.systemPrompt || "You are a helpful, friendly AI concierge. Keep answers concise (1-2 sentences).",
      profileId: options.profileId || "",
    };
    // Apply profile ID from options
    if (options.profileId) {
      this.activeProfileId = options.profileId;
    }

    // Resolve target container
    if (typeof this.options.target === "string") {
      const el = document.querySelector(this.options.target);
      if (!el) throw new Error(`Target container '${this.options.target}' not found.`);
      this.container = el as HTMLElement;
    } else {
      this.container = this.options.target;
    }

    this.rootEl = this._renderWidgetDOM();
    this.canvasSlot = this.rootEl.querySelector(".avatar-widget-canvas-slot") as HTMLElement;
    this.videoEl = this.rootEl.querySelector(".avatar-widget-video") as HTMLVideoElement;

    // Configure Pure Live Video element with official Presenter Poster
    if (this.videoEl) {
      this.videoEl.poster = isMale ? DID_POSTER_MALE : DID_POSTER_FEMALE;
      this.videoEl.style.display = "block";
    }

    // Only mount 2D canvas if explicitly configured with engine: "canvas"
    if ((this.options.engine === "canvas" || this.options.engine === "edge-tts") && this.canvasSlot) {
      this.renderer = new Renderer2D(this.canvasSlot, this.options.avatar);
    }

    this._setupSpeechRecognition();
    this._bindEvents();
  }

  /** Initialize and connect the avatar stream */
  async init(): Promise<void> {
    if (this.options.engine === "canvas" || this.options.engine === "edge-tts") {
      await this._initCanvasStream();
    } else {
      await this._initWebRTCStream();
    }
  }

  /** Switch between Male (David / Adam) and Female (Emma / Alyssa) personas dynamically */
  async setAvatar(avatarId: string): Promise<void> {
    const lower = avatarId.toLowerCase();
    const isMale = lower === "male" || lower === "david";
    const normId = isMale ? "male" : "female";

    this.options.avatar = normId;
    this.options.voice = isMale ? "en-US-ChristopherNeural" : "en-US-JennyNeural";
    this.options.title = isMale ? "David â€” AI Concierge" : "Emma â€” AI Concierge";

    // Update Header Title
    const titleEl = this.rootEl.querySelector(".avatar-widget-title") as HTMLElement;
    if (titleEl) titleEl.textContent = this.options.title;

    // Update Avatar Persona Toolbar Buttons
    const btnFem = this.rootEl.querySelector(".btn-persona-female") as HTMLElement;
    const btnMale = this.rootEl.querySelector(".btn-persona-male") as HTMLElement;
    if (btnFem && btnMale) {
      if (isMale) {
        btnMale.classList.add("active");
        btnFem.classList.remove("active");
      } else {
        btnFem.classList.add("active");
        btnMale.classList.remove("active");
      }
    }

    // Update Presenter Poster immediately
    if (this.videoEl) {
      this.videoEl.poster = isMale ? DID_POSTER_MALE : DID_POSTER_FEMALE;
      this.videoEl.srcObject = null;
    }

    if (this.renderer) {
      this.renderer.setImage(normId);
    }

    // Re-create WebRTC Stream for the selected persona
    if (this.options.engine !== "canvas" && this.options.engine !== "edge-tts") {
      await this._initWebRTCStream();
    }
  }

  /** Switch engine ('d-id' | 'simli' | 'anam' | 'akool' | 'heygen' | 'canvas') */
  async setEngine(engine: "d-id" | "simli" | "anam" | "akool" | "heygen" | "canvas" | "webrtc" | "edge-tts"): Promise<void> {
    this.options.engine = engine as any;
    
    // Sync dropdown value in UI
    const select = this.rootEl.querySelector(".avatar-widget-engine-select") as HTMLSelectElement;
    if (select) {
      select.value = engine === "edge-tts" ? "canvas" : engine === "webrtc" ? "d-id" : engine;
    }

    if (engine === "canvas" || engine === "edge-tts") {
      if (this.videoEl) this.videoEl.style.display = "none";
      if (!this.renderer && this.canvasSlot) {
        this.renderer = new Renderer2D(this.canvasSlot, this.options.avatar);
      }
      await this._initCanvasStream();
    } else {
      if (this.renderer) {
        this.renderer.destroy();
        this.renderer = null;
      }
      if (this.videoEl) {
        this.videoEl.style.display = "block";
      }
      await this._initWebRTCStream();
    }
  }

  /** Connect Photorealistic WebRTC Video Stream (D-ID / Simli / Anam / Akool / HeyGen) */
  private async _initWebRTCStream(): Promise<void> {
    if (this.isConnecting) return;
    this.isConnecting = true;
    const provider = this.options.engine === "webrtc" ? "d-id" : this.options.engine;
    this._setStatus(`Connecting ${provider.toUpperCase()} WebRTC...`, "");

    try {
      if (this.peerConnection) {
        try { this.peerConnection.close(); } catch(e){}
        this.peerConnection = null;
      }

      // 1. Create REST session
      const sessResp = await fetch(`${this.options.serverUrl}/api/v1/sessions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ avatar_id: this.options.avatar }),
      });
      if (!sessResp.ok) throw new Error("Failed to create avatar session");
      const sessData = await sessResp.json();
      this.activeSessionId = sessData.session_id;

      // 2. Fetch WebRTC Offer from backend adapter
      const offerResp = await fetch(
        `${this.options.serverUrl}/api/v1/sessions/${this.activeSessionId}/webrtc/offer?avatar_id=${this.options.avatar}&provider=${provider}`,
        { method: "POST" }
      );
      if (!offerResp.ok) {
        const err = await offerResp.json();
        throw new Error(err.detail || `${provider.toUpperCase()} WebRTC offer creation failed. Ensure API key is configured.`);
      }

      const offerData = await offerResp.json();
      this.activeStreamId = offerData.stream_id;
      this.providerSessionId = offerData.did_session_id;

      // â”€â”€ Anam.ai Direct Persona Streaming Handshake â”€â”€
      if (provider === "anam") {
        const apiKey = offerData.api_key;
        const personaId = offerData.persona_id;
        const personaConfig = offerData.persona_config || { personaId };

        if (this.anamClient) {
          try { await this.anamClient.stopStreaming(); } catch (e) {}
        }

        const { unsafe_createClientWithApiKey } = await import("@anam-ai/js-sdk");
        this.anamClient = unsafe_createClientWithApiKey(apiKey, personaConfig);

        if (this.videoEl) {
          this.videoEl.style.display = "block";
          this.videoEl.id = this.videoEl.id || ("anam-video-" + Math.random().toString(36).substring(2, 9));
          await this.anamClient.streamToVideoElement(this.videoEl.id);
          this._setStatus("Online âœ“ (ANAM.AI Digital Human)", "ok");
        }
        return;
      }

      // 3. Setup RTCPeerConnection
      this.peerConnection = new RTCPeerConnection({
        iceServers: offerData.ice_servers || [{ urls: ["stun:stun.l.google.com:19302"] }],
      });

      this.peerConnection.ontrack = (event) => {
        if (event.track.kind === "video" && this.videoEl) {
          this.videoEl.srcObject = event.streams[0];
          this.videoEl.style.display = "block";
          this.videoEl.play().catch(console.warn);
          this._setStatus(`Online âœ“ (${provider.toUpperCase()} Stream)`, "ok");
        }
      };

      this.peerConnection.onicecandidate = (event) => {
        if (event.candidate) {
          fetch(`${this.options.serverUrl}/api/v1/sessions/${this.activeSessionId}/webrtc/ice?provider=${provider}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              stream_id: this.activeStreamId,
              candidate: event.candidate,
              provider_session_id: this.providerSessionId,
            }),
          }).catch(console.warn);
        }
      };

      this.peerConnection.onconnectionstatechange = () => {
        if (
          this.peerConnection?.connectionState === "disconnected" ||
          this.peerConnection?.connectionState === "failed" ||
          this.peerConnection?.connectionState === "closed"
        ) {
          this._setStatus("Stream idle. Ready to talk.", "");
        }
      };

      // 4. Set Remote Description & Create SDP Answer
      await this.peerConnection.setRemoteDescription(new RTCSessionDescription(offerData.offer));
      const answer = await this.peerConnection.createAnswer();
      await this.peerConnection.setLocalDescription(answer);

      // 5. Submit SDP Answer to Backend
      await fetch(`${this.options.serverUrl}/api/v1/sessions/${this.activeSessionId}/webrtc/answer?provider=${provider}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          stream_id: this.activeStreamId,
          answer: answer,
          provider_session_id: this.providerSessionId,
        }),
      });

      this._setStatus(`${provider.toUpperCase()} Connected âœ“ Ready`, "ok");

    } catch (err: any) {
      console.error(`[AvatarWidget] ${provider.toUpperCase()} Stream Error:`, err);
      this._setStatus(`${err.message}`, "error");
    } finally {
      this.isConnecting = false;
    }
  }

  /** Initialize 2D Canvas Stream via WebSocket (only if explicitly set) */
  private async _initCanvasStream(): Promise<void> {
    const wsUrl = this.options.serverUrl.replace("https://", "wss://").replace("http://", "ws://");
    if (this.client) {
      try { await this.client.destroy(); } catch(e){}
    }
    this.client = new AvatarClient({
      serverUrl: wsUrl,
      avatarId: this.options.avatar,
    });
    try {
      await this.client.connect();
      if (this.canvasSlot && !this.renderer) {
        this.client.mount(this.canvasSlot, this.options.avatar);
      }
      this._setStatus("Online âœ“ (2D Canvas)", "ok");
    } catch (err: any) {
      console.warn("[AvatarWidget] Canvas connect error:", err);
    }
  }

  /** Speak arbitrary text through live video stream */
  async speak(text: string): Promise<void> {
    const provider = this.options.engine === "webrtc" ? "d-id" : this.options.engine;
    this._setStatus(`Speaking (${provider.toUpperCase()})...`, "speaking");

    // If Anam.ai engine is active, use Anam data channel talk command
    if (provider === "anam" && this.anamClient) {
      this._setStatus("Speaking (ANAM.AI)...", "speaking");
      try {
        await this.anamClient.talk(text);
        setTimeout(() => this._setStatus("Online âœ“", "ok"), 3000);
      } catch (err: any) {
        console.error("[AvatarWidget] Anam speak error:", err);
        this._setStatus("Speak error", "error");
      }
      return;
    }

    // If WebRTC stream is not active or closed, reconnect first
    if (this.options.engine !== "canvas" && this.options.engine !== "edge-tts") {
      if (!this.activeStreamId || this.peerConnection?.connectionState !== "connected") {
        await this._initWebRTCStream();
      }
    }

    if (this.activeStreamId) {
      try {
        const resp = await fetch(
          `${this.options.serverUrl}/api/v1/sessions/${this.activeSessionId}/webrtc/speak?provider=${provider}`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              stream_id: this.activeStreamId,
              text: text,
              voice: this.options.voice,
              provider_session_id: this.providerSessionId,
            }),
          }
        );

        if (!resp.ok) {
          // If stream expired, re-create once and retry speak
          await this._initWebRTCStream();
          await fetch(
            `${this.options.serverUrl}/api/v1/sessions/${this.activeSessionId}/webrtc/speak?provider=${provider}`,
            {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                stream_id: this.activeStreamId,
                text: text,
                voice: this.options.voice,
                provider_session_id: this.providerSessionId,
              }),
            }
          );
        }

        setTimeout(() => this._setStatus("Online âœ“", "ok"), 4000);
      } catch (err: any) {
        console.error(`[AvatarWidget] ${provider.toUpperCase()} speak error:`, err);
        this._setStatus("Speak error", "error");
      }
    } else if (this.client) {
      this.client.speak(text, { voice: this.options.voice });
    }
  }

  /** Ask conversational AI a question â€” supports AbortController for barge-in cancellation */
  async ask(query: string, signal?: AbortSignal): Promise<string> {
    this.addMessage("user", query);
    this._setStatus("Thinking (Groq LLM)...", "speaking");
    this.convState = "processing";

    try {
      const resp = await fetch(`${this.options.serverUrl}/api/v1/chat/respond`, {
        method: "POST",
        signal,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: query,
          history: this.chatHistory,
          system_prompt: this.options.systemPrompt,
          // Inject active profile for RAG document context
          profile_id: this.activeProfileId || undefined,
        }),
      });

      if (!resp.ok) throw new Error("Chat service unavailable");
      const data = await resp.json();
      const reply = data.reply || "I understand.";

      this.addMessage("avatar", reply);
      this.chatHistory.push({ role: "user", content: query });
      this.chatHistory.push({ role: "assistant", content: reply });

      this.convState = "speaking";
      await this.speak(reply);

      // After avatar finishes speaking, restart listening if voice loop is active
      if (this.voiceLoopActive) {
        this._restartListening();
      } else {
        this.convState = "idle";
      }

      return reply;
    } catch (err: any) {
      if (err.name === "AbortError") {
        // Barge-in cancelled the request â€” don't show error
        return "";
      }
      this._setStatus("Error generating response", "error");
      this.convState = "idle";
      throw err;
    }
  }

  /** Interrupt current speech â€” stops audio, animation, and video stream avatar speech */
  interrupt(): void {
    // Abort in-flight LLM fetch (barge-in)
    if (this.askAbortController) {
      this.askAbortController.abort();
      this.askAbortController = null;
    }
    // Stop canvas/WebSocket avatar
    if (this.client) this.client.interrupt();
    // Stop Anam avatar
    if (this.anamClient) {
      try { this.anamClient.interruptPersona(); } catch (e) {}
    }
    // Signal WebRTC provider to stop avatar speech
    if (this.activeSessionId && this.activeStreamId) {
      const provider = this.options.engine === "webrtc" ? "d-id" : this.options.engine;
      fetch(
        `${this.options.serverUrl}/api/v1/sessions/${this.activeSessionId}/webrtc/interrupt?provider=${provider}`,
        { method: "POST" }
      ).catch(() => {});
    }
    this._setStatus("Interrupted â€” Listening...", "speaking");
    this.convState = "idle";
  }

  /** Add chat bubble to history */
  addMessage(role: "user" | "avatar", text: string): void {
    const historyEl = this.rootEl.querySelector(".avatar-widget-history") as HTMLElement;
    if (!historyEl) return;

    const bubble = document.createElement("div");
    bubble.className = `avatar-msg avatar-msg-${role}`;
    bubble.innerHTML =
      role === "user"
        ? `<b>You:</b> ${this._escape(text)}`
        : `<b>${this._escape(this.options.title)}:</b> ${this._escape(text)}`;
    historyEl.appendChild(bubble);
    historyEl.scrollTop = historyEl.scrollHeight;
  }

  private _setStatus(msg: string, cls: string): void {
    const st = this.rootEl.querySelector(".avatar-widget-status") as HTMLElement;
    if (st) {
      st.textContent = msg;
      st.className = `avatar-widget-status ${cls}`;
    }
  }

  private _renderWidgetDOM(): HTMLElement {
    const isFloating = this.options.floating;
    const isMale = this.options.avatar === "male" || this.options.avatar === "david";
    const wrapper = document.createElement("div");
    wrapper.className = `avatar-widget-root ${isFloating ? "floating-widget" : "inline-widget"}`;

    const curEngine = this.options.engine === "webrtc" ? "d-id" : this.options.engine === "edge-tts" ? "canvas" : this.options.engine;

    wrapper.innerHTML = `
      <style>
        .avatar-widget-root {
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Plus Jakarta Sans", sans-serif;
          color: #f1f5f9;
          box-sizing: border-box;
          display: flex;
          flex-direction: column;
          background: rgba(15, 23, 42, 0.94);
          backdrop-filter: blur(16px);
          border: 1px solid rgba(255, 255, 255, 0.12);
          border-radius: 20px;
          overflow: hidden;
          box-shadow: 0 20px 40px rgba(0,0,0,0.5);
          width: 100%;
          max-width: 360px;
        }
        .avatar-widget-root.floating-widget {
          position: fixed;
          bottom: 24px;
          right: 24px;
          z-index: 99999;
          width: 340px;
        }
        .avatar-widget-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 10px 14px;
          background: rgba(30, 41, 59, 0.85);
          border-bottom: 1px solid rgba(255, 255, 255, 0.08);
          gap: 8px;
        }
        .avatar-widget-title {
          font-size: 0.86rem;
          font-weight: 700;
          display: flex;
          align-items: center;
          gap: 6px;
        }
        .avatar-widget-title::before {
          content: "";
          display: inline-block;
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background: #10b981;
          box-shadow: 0 0 8px #10b981;
        }
        .avatar-widget-status {
          font-size: 0.70rem;
          color: #94a3b8;
        }
        .avatar-widget-status.ok { color: #34d399; }
        .avatar-widget-status.speaking { color: #38bdf8; font-weight: 600; }
        .avatar-widget-status.error { color: #f87171; }
        .avatar-widget-engine-select {
          background: rgba(15, 23, 42, 0.85);
          border: 1px solid rgba(255, 255, 255, 0.15);
          color: #38bdf8;
          font-family: inherit;
          font-size: 0.72rem;
          font-weight: 600;
          padding: 4px 8px;
          border-radius: 8px;
          outline: none;
          cursor: pointer;
        }
        .avatar-widget-engine-select:focus {
          border-color: #6366f1;
        }
        .avatar-widget-canvas-slot {
          width: 100%;
          height: 240px;
          background: #090d16;
          position: relative;
          overflow: hidden;
        }
        .avatar-widget-video {
          width: 100%;
          height: 100%;
          object-fit: cover;
          display: block;
          background: #090d16;
        }
        .avatar-widget-toolbar {
          position: absolute;
          bottom: 8px;
          left: 50%;
          transform: translateX(-50%);
          display: flex;
          gap: 6px;
          background: rgba(15, 23, 42, 0.85);
          backdrop-filter: blur(8px);
          padding: 4px 8px;
          border-radius: 999px;
          border: 1px solid rgba(255,255,255,0.15);
          z-index: 10;
        }
        .avatar-persona-btn {
          background: transparent;
          border: none;
          color: #94a3b8;
          font-size: 0.75rem;
          font-weight: 600;
          padding: 3px 8px;
          border-radius: 999px;
          cursor: pointer;
          transition: all 0.2s;
        }
        .avatar-persona-btn.active {
          background: #6366f1;
          color: #ffffff;
        }
        .avatar-widget-history {
          height: 100px;
          overflow-y: auto;
          padding: 10px 12px;
          display: flex;
          flex-direction: column;
          gap: 6px;
          background: rgba(10, 14, 26, 0.6);
          font-size: 0.8rem;
        }
        .avatar-msg {
          padding: 6px 10px;
          border-radius: 8px;
          line-height: 1.35;
          max-width: 90%;
        }
        .avatar-msg-user {
          align-self: flex-end;
          background: rgba(99, 102, 241, 0.35);
          color: #e0e7ff;
        }
        .avatar-msg-avatar {
          align-self: flex-start;
          background: rgba(255, 255, 255, 0.08);
          color: #cbd5e1;
        }
        .avatar-widget-input-bar {
          display: flex;
          gap: 6px;
          padding: 10px;
          background: rgba(30, 41, 59, 0.6);
          border-top: 1px solid rgba(255, 255, 255, 0.08);
        }
        .avatar-widget-input {
          flex: 1;
          padding: 8px 12px;
          border-radius: 10px;
          border: 1px solid rgba(255,255,255,0.12);
          background: rgba(15, 23, 42, 0.7);
          color: #f8fafc;
          font-size: 0.85rem;
          outline: none;
        }
        .avatar-widget-input:focus {
          border-color: #6366f1;
        }
        .avatar-widget-btn {
          border: none;
          border-radius: 10px;
          padding: 8px 12px;
          font-weight: 600;
          cursor: pointer;
          font-size: 0.85rem;
          transition: transform 0.1s, opacity 0.2s;
        }
        .avatar-widget-btn:active { transform: scale(0.96); }
        .btn-widget-mic {
          background: rgba(255,255,255,0.08);
          color: #f1f5f9;
        }
        .btn-widget-mic.listening {
          background: #ef4444;
          animation: pulse 1s infinite;
        }
        .btn-widget-send {
          background: linear-gradient(135deg, #6366f1, #4f46e5);
          color: #fff;
        }
      </style>
      <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        .avatar-widget-root {
          font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          color: #f1f5f9;
          box-sizing: border-box;
          display: flex;
          flex-direction: column;
          background: rgba(10, 15, 30, 0.96);
          backdrop-filter: blur(20px);
          border: 1px solid rgba(255, 255, 255, 0.10);
          border-radius: 20px;
          overflow: hidden;
          box-shadow: 0 24px 60px rgba(0,0,0,0.6), 0 0 0 1px rgba(99,102,241,0.15);
          width: 100%;
          max-width: 380px;
        }
        .avatar-widget-root.floating-widget {
          position: fixed;
          bottom: 24px;
          right: 24px;
          z-index: 99999;
          width: 360px;
        }
        .avatar-widget-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 10px 14px;
          background: rgba(20, 30, 55, 0.90);
          border-bottom: 1px solid rgba(255, 255, 255, 0.07);
          gap: 8px;
        }
        .avatar-widget-title {
          font-size: 0.86rem;
          font-weight: 700;
          display: flex;
          align-items: center;
          gap: 6px;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        .avatar-widget-title .status-dot {
          flex-shrink: 0;
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background: #10b981;
          box-shadow: 0 0 8px #10b981;
        }
        .avatar-widget-status {
          font-size: 0.68rem;
          color: #64748b;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        .avatar-widget-status.ok { color: #34d399; }
        .avatar-widget-status.speaking { color: #38bdf8; font-weight: 600; }
        .avatar-widget-status.error { color: #f87171; }
        .header-controls { display: flex; gap: 6px; align-items: center; flex-shrink: 0; }
        .avatar-widget-engine-select {
          background: rgba(15, 23, 42, 0.85);
          border: 1px solid rgba(255, 255, 255, 0.15);
          color: #38bdf8;
          font-family: inherit;
          font-size: 0.70rem;
          font-weight: 600;
          padding: 4px 6px;
          border-radius: 8px;
          outline: none;
          cursor: pointer;
        }
        .btn-profile-manager {
          background: rgba(99,102,241,0.18);
          border: 1px solid rgba(99,102,241,0.40);
          color: #a5b4fc;
          border-radius: 8px;
          padding: 4px 8px;
          font-size: 0.70rem;
          font-weight: 700;
          cursor: pointer;
          transition: all 0.2s;
          white-space: nowrap;
        }
        .btn-profile-manager:hover { background: rgba(99,102,241,0.32); }
        .avatar-widget-canvas-slot {
          width: 100%;
          height: 240px;
          background: #060a14;
          position: relative;
          overflow: hidden;
        }
        .avatar-widget-video {
          width: 100%;
          height: 100%;
          object-fit: cover;
          display: block;
          background: #060a14;
        }
        .avatar-widget-toolbar {
          position: absolute;
          bottom: 8px;
          left: 50%;
          transform: translateX(-50%);
          display: flex;
          gap: 6px;
          background: rgba(10, 15, 30, 0.88);
          backdrop-filter: blur(10px);
          padding: 4px 8px;
          border-radius: 999px;
          border: 1px solid rgba(255,255,255,0.12);
          z-index: 10;
        }
        .avatar-persona-btn {
          background: transparent;
          border: none;
          color: #94a3b8;
          font-size: 0.75rem;
          font-weight: 600;
          padding: 3px 10px;
          border-radius: 999px;
          cursor: pointer;
          transition: all 0.2s;
        }
        .avatar-persona-btn.active { background: #6366f1; color: #fff; }
        .active-profile-badge {
          position: absolute;
          top: 8px;
          left: 8px;
          background: rgba(16, 185, 129, 0.18);
          border: 1px solid rgba(16, 185, 129, 0.40);
          color: #34d399;
          font-size: 0.64rem;
          font-weight: 700;
          padding: 2px 8px;
          border-radius: 999px;
          backdrop-filter: blur(8px);
          display: none;
          z-index: 10;
          max-width: 180px;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        .active-profile-badge.visible { display: block; }
        .voice-indicator {
          position: absolute;
          top: 8px;
          right: 8px;
          background: rgba(239, 68, 68, 0.18);
          border: 1px solid rgba(239,68,68,0.40);
          color: #f87171;
          font-size: 0.64rem;
          font-weight: 700;
          padding: 2px 8px;
          border-radius: 999px;
          backdrop-filter: blur(8px);
          display: none;
          z-index: 10;
          animation: voicePulse 1.2s ease-in-out infinite;
        }
        .voice-indicator.visible { display: block; }
        @keyframes voicePulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
        .avatar-widget-history {
          height: 110px;
          overflow-y: auto;
          padding: 10px 12px;
          display: flex;
          flex-direction: column;
          gap: 6px;
          background: rgba(6, 10, 20, 0.65);
          font-size: 0.79rem;
        }
        .avatar-widget-history::-webkit-scrollbar { width: 4px; }
        .avatar-widget-history::-webkit-scrollbar-track { background: transparent; }
        .avatar-widget-history::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.12); border-radius: 4px; }
        .avatar-msg {
          padding: 6px 10px;
          border-radius: 10px;
          line-height: 1.4;
          max-width: 88%;
          word-break: break-word;
        }
        .avatar-msg-user { align-self: flex-end; background: rgba(99, 102, 241, 0.28); color: #c7d2fe; }
        .avatar-msg-avatar { align-self: flex-start; background: rgba(255, 255, 255, 0.07); color: #cbd5e1; }
        .avatar-widget-input-bar {
          display: flex;
          gap: 6px;
          padding: 10px;
          background: rgba(15, 22, 40, 0.70);
          border-top: 1px solid rgba(255, 255, 255, 0.07);
        }
        .avatar-widget-input {
          flex: 1;
          padding: 8px 12px;
          border-radius: 10px;
          border: 1px solid rgba(255,255,255,0.10);
          background: rgba(10, 15, 30, 0.75);
          color: #f8fafc;
          font-size: 0.84rem;
          outline: none;
          font-family: inherit;
          transition: border-color 0.2s;
        }
        .avatar-widget-input:focus { border-color: #6366f1; }
        .avatar-widget-btn {
          border: none;
          border-radius: 10px;
          padding: 8px 12px;
          font-weight: 600;
          cursor: pointer;
          font-size: 0.84rem;
          transition: transform 0.12s, opacity 0.2s, background 0.2s;
          font-family: inherit;
        }
        .avatar-widget-btn:active { transform: scale(0.95); }
        .btn-widget-mic {
          background: rgba(255,255,255,0.08);
          color: #f1f5f9;
          position: relative;
        }
        .btn-widget-mic.voice-loop {
          background: rgba(99,102,241,0.30);
          color: #a5b4fc;
          box-shadow: 0 0 12px rgba(99,102,241,0.4);
          animation: micGlow 1.8s ease-in-out infinite;
        }
        .btn-widget-mic.listening {
          background: rgba(239,68,68,0.30);
          color: #fca5a5;
          box-shadow: 0 0 12px rgba(239,68,68,0.4);
          animation: micGlow 0.8s ease-in-out infinite;
        }
        @keyframes micGlow {
          0%, 100% { box-shadow: 0 0 8px currentColor; }
          50% { box-shadow: 0 0 18px currentColor; }
        }
        .btn-widget-send {
          background: linear-gradient(135deg, #6366f1, #4f46e5);
          color: #fff;
        }
        .btn-widget-send:hover { opacity: 0.9; }
        /* â”€â”€ Profile Manager Modal â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
        .profile-modal-overlay {
          position: fixed; inset: 0;
          background: rgba(0,0,0,0.72);
          backdrop-filter: blur(6px);
          z-index: 1000000;
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 16px;
        }
        .profile-modal {
          background: linear-gradient(160deg, #0f172a 0%, #1e1b4b 100%);
          border: 1px solid rgba(99,102,241,0.30);
          border-radius: 20px;
          padding: 24px;
          width: 100%;
          max-width: 440px;
          max-height: 90vh;
          overflow-y: auto;
          box-shadow: 0 32px 80px rgba(0,0,0,0.7);
          color: #f1f5f9;
          font-family: 'Inter', sans-serif;
        }
        .profile-modal h3 {
          font-size: 1.1rem;
          font-weight: 700;
          margin: 0 0 4px;
          background: linear-gradient(90deg, #a5b4fc, #818cf8);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
        }
        .profile-modal .subtitle {
          font-size: 0.78rem;
          color: #64748b;
          margin: 0 0 20px;
        }
        .pm-label {
          font-size: 0.78rem;
          font-weight: 600;
          color: #94a3b8;
          margin-bottom: 6px;
          display: block;
        }
        .pm-input {
          width: 100%;
          padding: 9px 12px;
          border-radius: 10px;
          border: 1px solid rgba(255,255,255,0.12);
          background: rgba(10,15,30,0.70);
          color: #f8fafc;
          font-size: 0.85rem;
          font-family: inherit;
          outline: none;
          box-sizing: border-box;
          margin-bottom: 14px;
          transition: border-color 0.2s;
        }
        .pm-input:focus { border-color: #6366f1; }
        .pm-select {
          width: 100%;
          padding: 9px 12px;
          border-radius: 10px;
          border: 1px solid rgba(255,255,255,0.12);
          background: rgba(10,15,30,0.80);
          color: #f8fafc;
          font-size: 0.85rem;
          font-family: inherit;
          outline: none;
          box-sizing: border-box;
          margin-bottom: 14px;
          cursor: pointer;
        }
        .pm-file-drop {
          border: 2px dashed rgba(99,102,241,0.35);
          border-radius: 12px;
          padding: 20px;
          text-align: center;
          cursor: pointer;
          transition: all 0.2s;
          margin-bottom: 14px;
          background: rgba(99,102,241,0.06);
        }
        .pm-file-drop:hover, .pm-file-drop.dragover {
          border-color: #6366f1;
          background: rgba(99,102,241,0.12);
        }
        .pm-file-drop .drop-icon { font-size: 1.8rem; margin-bottom: 6px; }
        .pm-file-drop .drop-text { font-size: 0.82rem; color: #94a3b8; }
        .pm-file-drop .drop-formats { font-size: 0.72rem; color: #64748b; margin-top: 4px; }
        .pm-file-name {
          font-size: 0.78rem;
          color: #34d399;
          padding: 6px 10px;
          background: rgba(16,185,129,0.10);
          border-radius: 8px;
          margin-bottom: 14px;
          display: none;
        }
        .pm-file-name.visible { display: block; }
        .pm-btn-row { display: flex; gap: 10px; margin-top: 4px; }
        .pm-btn {
          flex: 1;
          padding: 10px;
          border-radius: 10px;
          border: none;
          font-size: 0.84rem;
          font-weight: 700;
          font-family: inherit;
          cursor: pointer;
          transition: all 0.2s;
        }
        .pm-btn-primary { background: linear-gradient(135deg,#6366f1,#4f46e5); color:#fff; }
        .pm-btn-primary:hover { opacity: 0.88; }
        .pm-btn-secondary { background: rgba(255,255,255,0.07); color: #94a3b8; }
        .pm-btn-secondary:hover { background: rgba(255,255,255,0.12); }
        .pm-profiles-list { margin-bottom: 18px; }
        .pm-profile-item {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 10px 12px;
          border-radius: 12px;
          background: rgba(255,255,255,0.04);
          border: 1px solid rgba(255,255,255,0.07);
          margin-bottom: 8px;
          transition: all 0.2s;
          cursor: pointer;
        }
        .pm-profile-item:hover { background: rgba(99,102,241,0.12); border-color: rgba(99,102,241,0.30); }
        .pm-profile-item.selected { background: rgba(99,102,241,0.20); border-color: rgba(99,102,241,0.55); }
        .pm-profile-avatar { font-size: 1.5rem; }
        .pm-profile-info { flex: 1; min-width: 0; }
        .pm-profile-name { font-size: 0.86rem; font-weight: 700; }
        .pm-profile-docs { font-size: 0.70rem; color: #64748b; margin-top: 2px; }
        .pm-profile-docs.has-docs { color: #34d399; }
        .pm-delete-btn {
          background: rgba(239,68,68,0.15);
          border: 1px solid rgba(239,68,68,0.30);
          color: #f87171;
          border-radius: 7px;
          padding: 3px 8px;
          font-size: 0.70rem;
          cursor: pointer;
          transition: all 0.2s;
        }
        .pm-delete-btn:hover { background: rgba(239,68,68,0.30); }
        .pm-section-title {
          font-size: 0.72rem;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.08em;
          color: #475569;
          margin: 16px 0 10px;
        }
        .pm-status { font-size: 0.78rem; color: #34d399; min-height: 1.4em; margin-bottom: 10px; }
        .pm-status.error { color: #f87171; }
        .pm-divider { border: none; border-top: 1px solid rgba(255,255,255,0.07); margin: 18px 0; }
      </style>
      <div class="avatar-widget-header">
        <div style="display:flex; flex-direction:column; gap:2px; flex:1; min-width:0;">
          <span class="avatar-widget-title"><span class="status-dot"></span>${this._escape(this.options.title)}</span>
          <span class="avatar-widget-status">Connecting...</span>
        </div>
        <div class="header-controls">
          <button class="btn-profile-manager" title="Manage Expert Profiles">ðŸ‘¤ Profiles</button>
          <select class="avatar-widget-engine-select" title="Switch Avatar Engine">
            <option value="d-id" ${curEngine === "d-id" ? "selected" : ""}>ðŸŽ¬ D-ID</option>
            <option value="simli" ${curEngine === "simli" ? "selected" : ""}>âš¡ Simli</option>
            <option value="anam" ${curEngine === "anam" ? "selected" : ""}>ðŸ¤– Anam.ai</option>
            <option value="akool" ${curEngine === "akool" ? "selected" : ""}>ðŸŽ¥ Akool</option>
            <option value="heygen" ${curEngine === "heygen" ? "selected" : ""}>ðŸŽžï¸ HeyGen</option>
            <option value="canvas" ${curEngine === "canvas" ? "selected" : ""}>âš¡ 2D Canvas</option>
          </select>
        </div>
      </div>
      <div class="avatar-widget-canvas-slot">
        <video class="avatar-widget-video" autoplay playsinline></video>
        <span class="active-profile-badge"></span>
        <span class="voice-indicator">ðŸŽ™ï¸ Listening...</span>
        <div class="avatar-widget-toolbar">
          <button class="avatar-persona-btn btn-persona-female ${!isMale ? "active" : ""}">ðŸ‘© Emma</button>
          <button class="avatar-persona-btn btn-persona-male ${isMale ? "active" : ""}">ðŸ‘¨ David</button>
        </div>
      </div>
      <div class="avatar-widget-history">
        <div class="avatar-msg avatar-msg-avatar"><b>${this._escape(this.options.title)}:</b> ${this._escape(this.options.welcomeMessage)}</div>
      </div>
      <div class="avatar-widget-input-bar">
        <input class="avatar-widget-input" type="text" placeholder="Ask me anything...">
        <button class="avatar-widget-btn btn-widget-mic" title="Click once to start hands-free voice conversation">ðŸŽ™ï¸</button>
        <button class="avatar-widget-btn btn-widget-send">Send</button>
      </div>
    `;

    this.container.appendChild(wrapper);
    return wrapper;
  }

  private _setupSpeechRecognition(): void {
    if (!("webkitSpeechRecognition" in window || "SpeechRecognition" in window)) return;

    const SpeechRec = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    this.recognition = new SpeechRec();
    this.recognition.continuous = true;    // Don't auto-stop â€” we manage turns ourselves
    this.recognition.interimResults = true; // Get partial results for barge-in detection
    this.recognition.lang = "en-US";

    // â”€â”€ Result Handler â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    this.recognition.onresult = (e: any) => {
      let finalTranscript = "";
      let interimTranscript = "";

      for (let i = e.resultIndex; i < e.results.length; i++) {
        const result = e.results[i];
        if (result.isFinal) {
          finalTranscript += result[0].transcript;
        } else {
          interimTranscript += result[0].transcript;
        }
      }

      // Show live interim text in input
      const input = this.rootEl.querySelector(".avatar-widget-input") as HTMLInputElement;
      if (input && (finalTranscript || interimTranscript)) {
        input.value = finalTranscript || interimTranscript;
      }

      // â”€â”€ Barge-In Detection â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
      // If avatar is speaking or processing and we detect user speech, interrupt immediately
      if ((this.convState === "speaking" || this.convState === "processing") &&
          (interimTranscript.trim().length > 3 || finalTranscript.trim().length > 0)) {
        this.interrupt();
        this.convState = "listening";
        this._updateVoiceUI();
      }

      // â”€â”€ Final Transcript: Submit Query â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
      if (finalTranscript.trim()) {
        // Clear any pending silence timer
        if (this.silenceTimer) {
          clearTimeout(this.silenceTimer);
          this.silenceTimer = null;
        }
        this.interimTranscript = "";
        const query = finalTranscript.trim();
        if (input) input.value = "";

        // Cancel previous LLM request if still in-flight
        if (this.askAbortController) {
          this.askAbortController.abort();
        }
        this.askAbortController = new AbortController();
        const signal = this.askAbortController.signal;

        this.convState = "processing";
        this._updateVoiceUI();
        this.ask(query, signal).catch(() => {});
      } else {
        this.interimTranscript = interimTranscript;
      }
    };

    // â”€â”€ Speech End Handler â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    this.recognition.onspeechend = () => {
      // Give a brief moment for final result to arrive before stopping
      this.silenceTimer = setTimeout(() => {
        if (this.recognition && this.isListening) {
          try { this.recognition.stop(); } catch { /* ignore */ }
        }
      }, 600);
    };

    // â”€â”€ End Handler: Auto-Restart in Voice Loop Mode â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    this.recognition.onend = () => {
      this.isListening = false;
      if (this.silenceTimer) {
        clearTimeout(this.silenceTimer);
        this.silenceTimer = null;
      }
      // If voice loop is still active and we're not processing/speaking, restart
      if (this.voiceLoopActive && this.convState === "listening") {
        this._restartListening();
      } else if (!this.voiceLoopActive) {
        this._updateVoiceUI(false);
      }
    };

    this.recognition.onerror = (e: any) => {
      console.warn("[AvatarWidget] Speech recognition error:", e.error);
      if (e.error === "no-speech" || e.error === "aborted") return; // Non-fatal
      this.isListening = false;
      // Auto-restart on network errors during voice loop
      if (this.voiceLoopActive) {
        setTimeout(() => this._restartListening(), 800);
      }
    };
  }

  /** Restart speech recognition for the next voice loop turn */
  private _restartListening(): void {
    if (!this.recognition || !this.voiceLoopActive) return;
    this.convState = "listening";
    this._updateVoiceUI();
    try {
      this.recognition.stop();
    } catch { /* ignore if already stopped */ }
    setTimeout(() => {
      if (!this.voiceLoopActive || !this.recognition) return;
      try {
        this.recognition.start();
        this.isListening = true;
        this._setStatus("Listening... (speak anytime)", "speaking");
      } catch { /* browser may throw if already running */ }
    }, 250);
  }

  /** Update mic button and voice indicator UI based on current state */
  private _updateVoiceUI(active = true): void {
    const micBtn = this.rootEl.querySelector(".btn-widget-mic") as HTMLButtonElement;
    const voiceIndicator = this.rootEl.querySelector(".voice-indicator") as HTMLElement;
    if (!micBtn) return;

    if (!active || (!this.voiceLoopActive && !this.isListening)) {
      micBtn.classList.remove("listening", "voice-loop");
      micBtn.textContent = "ðŸŽ™ï¸";
      micBtn.title = "Click once to start hands-free voice conversation";
      if (voiceIndicator) voiceIndicator.classList.remove("visible");
      return;
    }

    if (this.voiceLoopActive) {
      if (this.convState === "listening") {
        micBtn.classList.add("listening");
        micBtn.classList.remove("voice-loop");
        micBtn.textContent = "ðŸ”´";
        if (voiceIndicator) { voiceIndicator.textContent = "ðŸŽ™ï¸ Listening..."; voiceIndicator.classList.add("visible"); }
      } else if (this.convState === "processing") {
        micBtn.classList.remove("listening");
        micBtn.classList.add("voice-loop");
        micBtn.textContent = "ðŸŸ¡";
        if (voiceIndicator) { voiceIndicator.textContent = "ðŸ¤” Thinking..."; voiceIndicator.classList.add("visible"); }
      } else if (this.convState === "speaking") {
        micBtn.classList.remove("listening");
        micBtn.classList.add("voice-loop");
        micBtn.textContent = "ðŸ’¬";
        if (voiceIndicator) { voiceIndicator.textContent = "ðŸ’¬ Speaking..."; voiceIndicator.classList.add("visible"); }
      } else {
        micBtn.classList.remove("listening");
        micBtn.classList.add("voice-loop");
        micBtn.textContent = "ðŸŽ™ï¸";
        if (voiceIndicator) voiceIndicator.classList.remove("visible");
      }
      micBtn.title = "Hands-Free Voice Active â€” click to stop";
    }
  }

  private _bindEvents(): void {
    const input = this.rootEl.querySelector(".avatar-widget-input") as HTMLInputElement;
    const sendBtn = this.rootEl.querySelector(".btn-widget-send") as HTMLButtonElement;
    const micBtn = this.rootEl.querySelector(".btn-widget-mic") as HTMLButtonElement;
    const btnFem = this.rootEl.querySelector(".btn-persona-female") as HTMLButtonElement;
    const btnMale = this.rootEl.querySelector(".btn-persona-male") as HTMLButtonElement;
    const engineSelect = this.rootEl.querySelector(".avatar-widget-engine-select") as HTMLSelectElement;
    const btnProfileMgr = this.rootEl.querySelector(".btn-profile-manager") as HTMLButtonElement;

    // Text send
    const handleSend = () => {
      const text = input.value.trim();
      if (!text) return;
      input.value = "";
      if (this.askAbortController) this.askAbortController.abort();
      this.askAbortController = new AbortController();
      this.ask(text, this.askAbortController.signal).catch(() => {});
    };
    sendBtn.onclick = handleSend;
    input.onkeydown = (e) => { if (e.key === "Enter") handleSend(); };

    // Persona switchers
    if (btnFem) btnFem.onclick = () => this.setAvatar("female");
    if (btnMale) btnMale.onclick = () => this.setAvatar("male");

    // Engine select
    if (engineSelect) engineSelect.onchange = () => this.setEngine(engineSelect.value as any);

    // â”€â”€ Microphone: Toggle Hands-Free Voice Loop â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    micBtn.onclick = () => {
      if (!this.recognition) {
        alert("Speech recognition is not supported in this browser. Please use Chrome or Edge.");
        return;
      }

      if (this.voiceLoopActive) {
        // Deactivate voice loop
        this.voiceLoopActive = false;
        this.convState = "idle";
        try { this.recognition.stop(); } catch { /* ignore */ }
        this.isListening = false;
        this._updateVoiceUI(false);
        this._setStatus("Voice mode off", "ok");
      } else {
        // Activate voice loop â€” start listening immediately
        this.voiceLoopActive = true;
        this.convState = "listening";
        try {
          this.recognition.start();
          this.isListening = true;
        } catch {
          // Already started â€” safe to ignore
        }
        this._updateVoiceUI();
        this._setStatus("ðŸŽ™ï¸ Hands-free voice active â€” speak anytime to interrupt", "speaking");
      }
    };

    // â”€â”€ Profile Manager Button â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    if (btnProfileMgr) {
      btnProfileMgr.onclick = () => this._openProfileModal();
    }
  }

  // â”€â”€ Profile Management â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

  /** Set the active expert profile for RAG-augmented responses */
  setProfile(profileId: string | null, displayName?: string): void {
    this.activeProfileId = profileId;
    const badge = this.rootEl.querySelector(".active-profile-badge") as HTMLElement;
    if (badge) {
      if (profileId && displayName) {
        badge.textContent = `ðŸ“„ ${displayName}`;
        badge.classList.add("visible");
      } else {
        badge.classList.remove("visible");
      }
    }
  }

  /** Open the Profile Manager modal */
  private async _openProfileModal(): Promise<void> {
    const overlay = document.createElement("div");
    overlay.className = "profile-modal-overlay";
    overlay.innerHTML = `
      <div class="profile-modal">
        <h3>ðŸ‘¤ Avatar Expert Profiles</h3>
        <p class="subtitle">Create a named AI expert with document knowledge (PDF, DOCX, TXT, MD)</p>

        <div class="pm-section-title">Saved Profiles</div>
        <div class="pm-profiles-list" id="pm-profiles-list">Loading...</div>

        <hr class="pm-divider">
        <div class="pm-section-title">Create New Expert</div>

        <label class="pm-label">Expert Name</label>
        <input class="pm-input" id="pm-name" type="text" placeholder="e.g. AI Expert Adam, Policy Specialist">

        <label class="pm-label">Avatar Persona</label>
        <select class="pm-select" id="pm-persona">
          <option value="female">ðŸ‘© Emma â€” Female (Default)</option>
          <option value="male">ðŸ‘¨ David â€” Male</option>
        </select>

        <label class="pm-label">Knowledge Document <span style="color:#475569">(optional â€” upload PDF / DOCX / TXT / MD)</span></label>
        <div class="pm-file-drop" id="pm-file-drop">
          <div class="drop-icon">ðŸ“‚</div>
          <div class="drop-text">Click to choose or drag & drop a file</div>
          <div class="drop-formats">Supported: PDF, DOCX, TXT, MD â€¢ Max 20 MB</div>
          <input type="file" id="pm-file-input" accept=".pdf,.docx,.txt,.md" style="display:none">
        </div>
        <div class="pm-file-name" id="pm-file-name"></div>

        <div class="pm-status" id="pm-status"></div>
        <div class="pm-btn-row">
          <button class="pm-btn pm-btn-primary" id="pm-create-btn">âœ¨ Create Expert Profile</button>
          <button class="pm-btn pm-btn-secondary" id="pm-close-btn">Close</button>
        </div>
      </div>
    `;
    document.body.appendChild(overlay);

    // Close on overlay click
    overlay.addEventListener("click", (e) => { if (e.target === overlay) overlay.remove(); });
    const closeBtn = overlay.querySelector("#pm-close-btn") as HTMLButtonElement;
    closeBtn.onclick = () => overlay.remove();

    // File input setup
    let selectedFile: File | null = null;
    const fileDrop = overlay.querySelector("#pm-file-drop") as HTMLElement;
    const fileInput = overlay.querySelector("#pm-file-input") as HTMLInputElement;
    const fileNameEl = overlay.querySelector("#pm-file-name") as HTMLElement;

    fileDrop.onclick = () => fileInput.click();
    fileDrop.ondragover = (e) => { e.preventDefault(); fileDrop.classList.add("dragover"); };
    fileDrop.ondragleave = () => fileDrop.classList.remove("dragover");
    fileDrop.ondrop = (e) => {
      e.preventDefault();
      fileDrop.classList.remove("dragover");
      const f = e.dataTransfer?.files[0];
      if (f) { selectedFile = f; fileNameEl.textContent = `ðŸ“„ ${f.name}`; fileNameEl.classList.add("visible"); }
    };
    fileInput.onchange = () => {
      const f = fileInput.files?.[0];
      if (f) { selectedFile = f; fileNameEl.textContent = `ðŸ“„ ${f.name}`; fileNameEl.classList.add("visible"); }
    };

    // Load existing profiles
    const listEl = overlay.querySelector("#pm-profiles-list") as HTMLElement;
    const statusEl = overlay.querySelector("#pm-status") as HTMLElement;

    const loadProfiles = async () => {
      try {
        const resp = await fetch(`${this.options.serverUrl}/api/v1/profiles`);
        const profiles = await resp.json();
        if (!profiles.length) {
          listEl.innerHTML = `<div style="color:#475569; font-size:0.78rem; padding:8px 0">No profiles yet. Create one below.</div>`;
          return;
        }
        listEl.innerHTML = profiles.map((p: any) => {
          const docCount = p.documents ? p.documents.length : 0;
          const isSelected = p.profile_id === this.activeProfileId;
          const selCls = isSelected ? "selected" : "";
          const docCls = docCount > 0 ? "has-docs" : "";
          const docTxt = docCount > 0 ? ("📄 " + docCount + " document(s)") : "No documents yet";
          const ava = p.persona === "male" ? "👨" : "👩";
          const eName = this._escape(p.name);
          return `<div class="pm-profile-item ${selCls}" data-pid="${p.profile_id}" data-name="${eName}"><span class="pm-profile-avatar">${ava}</span><div class="pm-profile-info"><div class="pm-profile-name">${eName}</div><div class="pm-profile-docs ${docCls}">${docTxt}</div></div><button class="pm-delete-btn" data-pid="${p.profile_id}">🗑️</button></div>`;
        }).join("");

        // Select profile on click
        listEl.querySelectorAll(".pm-profile-item").forEach(item => {
          item.addEventListener("click", (e: Event) => {
            const target = e.target as HTMLElement;
            if (target.classList.contains("pm-delete-btn")) return;
            const pid = (item as HTMLElement).dataset.pid!;
            const name = (item as HTMLElement).dataset.name!;
            this.setProfile(pid, name);
            // Update avatar persona to match
            const selectedProfile = profiles.find((p: any) => p.profile_id === pid);
            if (selectedProfile) {
              this.setAvatar(selectedProfile.persona);
              // Update title with profile name
              const titleEl = this.rootEl.querySelector(".avatar-widget-title") as HTMLElement;
              if (titleEl) titleEl.innerHTML = `<span class="status-dot"></span>${this._escape(selectedProfile.name)}`;
            }
            statusEl.textContent = `âœ… Active: ${name}`;
            statusEl.className = "pm-status";
            listEl.querySelectorAll(".pm-profile-item").forEach(i => i.classList.remove("selected"));
            item.classList.add("selected");
          });
        });

        // Delete buttons
        listEl.querySelectorAll(".pm-delete-btn").forEach(btn => {
          btn.addEventListener("click", async (e: Event) => {
            e.stopPropagation();
            const pid = (btn as HTMLElement).dataset.pid!;
            if (!confirm("Delete this profile and all its documents?")) return;
            await fetch(`${this.options.serverUrl}/api/v1/profiles/${pid}`, { method: "DELETE" });
            if (this.activeProfileId === pid) this.setProfile(null);
            loadProfiles();
          });
        });
      } catch (err) {
        listEl.innerHTML = `<div style="color:#f87171; font-size:0.78rem">Could not load profiles. Is the backend running?</div>`;
      }
    };
    await loadProfiles();

    // Create profile
    const createBtn = overlay.querySelector("#pm-create-btn") as HTMLButtonElement;
    createBtn.onclick = async () => {
      const nameInput = overlay.querySelector("#pm-name") as HTMLInputElement;
      const personaSelect = overlay.querySelector("#pm-persona") as HTMLSelectElement;
      const name = nameInput.value.trim();
      if (!name) { statusEl.textContent = "Please enter a name."; statusEl.className = "pm-status error"; return; }

      createBtn.disabled = true;
      createBtn.textContent = "Creating...";
      statusEl.textContent = "";

      try {
        // Step 1: Create profile
        const createResp = await fetch(`${this.options.serverUrl}/api/v1/profiles`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name, persona: personaSelect.value }),
        });
        if (!createResp.ok) throw new Error("Failed to create profile");
        const profile = await createResp.json();

        // Step 2: Upload document if selected
        if (selectedFile) {
          statusEl.textContent = "Indexing document...";
          const fd = new FormData();
          fd.append("file", selectedFile);
          const uploadResp = await fetch(
            `${this.options.serverUrl}/api/v1/profiles/${profile.profile_id}/documents`,
            { method: "POST", body: fd }
          );
          if (!uploadResp.ok) {
            const err = await uploadResp.json();
            throw new Error(err.detail || "Document indexing failed");
          }
        }

        statusEl.textContent = `âœ… Profile "${name}" created!`;
        statusEl.className = "pm-status";
        nameInput.value = "";
        fileNameEl.classList.remove("visible");
        selectedFile = null;
        createBtn.textContent = "âœ¨ Create Expert Profile";
        createBtn.disabled = false;

        // Auto-activate the new profile
        this.setProfile(profile.profile_id, name);
        this.setAvatar(personaSelect.value);
        const titleEl = this.rootEl.querySelector(".avatar-widget-title") as HTMLElement;
        if (titleEl) titleEl.innerHTML = `<span class="status-dot"></span>${this._escape(name)}`;

        await loadProfiles();
      } catch (err: any) {
        statusEl.textContent = `Error: ${err.message}`;
        statusEl.className = "pm-status error";
        createBtn.textContent = "âœ¨ Create Expert Profile";
        createBtn.disabled = false;
      }
    };
  }

  private _escape(str: string): string {
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  /** Destroy widget and clean up DOM */
  async destroy(): Promise<void> {
    if (this.anamClient) {
      try { await this.anamClient.stopStreaming(); } catch (e) {}
      this.anamClient = null;
    }
    if (this.peerConnection) {
      try { this.peerConnection.close(); } catch (e) {}
    }
    if (this.client) {
      await this.client.destroy();
    }
    if (this.renderer) {
      this.renderer.destroy();
    }
    this.rootEl.remove();
  }
}

/**
 * Functional factory helper for instant 1-line integration:
 * ```typescript
 * import { createAvatarWidget } from "@avatar-sdk/client";
 *
 * createAvatarWidget({ target: "#my-slot", engine: "d-id", avatar: "female" });
 * ```
 */
export function createAvatarWidget(options?: AvatarWidgetOptions): AvatarWidget {
  const widget = new AvatarWidget(options);
  widget.init().catch(console.error);
  return widget;
}
