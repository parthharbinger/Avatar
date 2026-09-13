/**
 * AvatarWidget — Drop-in plug-and-play AI Avatar component.
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
      title: options.title || (isMale ? "David — AI Concierge" : "Emma — AI Concierge"),
      welcomeMessage: options.welcomeMessage || "Hello! How can I assist you today?",
      systemPrompt: options.systemPrompt || "You are a helpful, friendly AI concierge. Keep answers concise (1-2 sentences).",
    };

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
    this.options.title = isMale ? "David — AI Concierge" : "Emma — AI Concierge";

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

      // ── Anam.ai Direct Persona Streaming Handshake ──
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
          this._setStatus("Online ✓ (ANAM.AI Digital Human)", "ok");
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
          this._setStatus(`Online ✓ (${provider.toUpperCase()} Stream)`, "ok");
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

      this._setStatus(`${provider.toUpperCase()} Connected ✓ Ready`, "ok");

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
      this._setStatus("Online ✓ (2D Canvas)", "ok");
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
        setTimeout(() => this._setStatus("Online ✓", "ok"), 3000);
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

        setTimeout(() => this._setStatus("Online ✓", "ok"), 4000);
      } catch (err: any) {
        console.error(`[AvatarWidget] ${provider.toUpperCase()} speak error:`, err);
        this._setStatus("Speak error", "error");
      }
    } else if (this.client) {
      this.client.speak(text, { voice: this.options.voice });
    }
  }

  /** Ask conversational AI a question */
  async ask(query: string): Promise<string> {
    this.addMessage("user", query);
    this._setStatus("Thinking (Groq LLM)...", "speaking");

    try {
      const resp = await fetch(`${this.options.serverUrl}/api/v1/chat/respond`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: query,
          history: this.chatHistory,
          system_prompt: this.options.systemPrompt,
        }),
      });

      if (!resp.ok) throw new Error("Chat service unavailable");
      const data = await resp.json();
      const reply = data.reply || "I understand.";

      this.addMessage("avatar", reply);
      this.chatHistory.push({ role: "user", content: query });
      this.chatHistory.push({ role: "assistant", content: reply });

      await this.speak(reply);
      return reply;
    } catch (err: any) {
      this._setStatus("Error generating response", "error");
      throw err;
    }
  }

  /** Interrupt current speech */
  interrupt(): void {
    if (this.client) this.client.interrupt();
    if (this.anamClient) {
      try { this.anamClient.interruptPersona(); } catch (e) {}
    }
    this._setStatus("Interrupted", "");
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
      <div class="avatar-widget-header">
        <div style="display:flex; flex-direction:column; gap:2px; flex:1; min-width:0;">
          <span class="avatar-widget-title">${this._escape(this.options.title)}</span>
          <span class="avatar-widget-status">Connecting...</span>
        </div>
        <select class="avatar-widget-engine-select" title="Switch Avatar Engine">
          <option value="d-id" ${curEngine === "d-id" ? "selected" : ""}>🎬 D-ID</option>
          <option value="simli" ${curEngine === "simli" ? "selected" : ""}>⚡ Simli</option>
          <option value="anam" ${curEngine === "anam" ? "selected" : ""}>🤖 Anam.ai</option>
          <option value="akool" ${curEngine === "akool" ? "selected" : ""}>🎥 Akool</option>
          <option value="heygen" ${curEngine === "heygen" ? "selected" : ""}>🎞️ HeyGen</option>
          <option value="canvas" ${curEngine === "canvas" ? "selected" : ""}>⚡ 2D Canvas</option>
        </select>
      </div>
      <div class="avatar-widget-canvas-slot">
        <video class="avatar-widget-video" autoplay playsinline></video>
        <div class="avatar-widget-toolbar">
          <button class="avatar-persona-btn btn-persona-female ${!isMale ? "active" : ""}">👩 Emma</button>
          <button class="avatar-persona-btn btn-persona-male ${isMale ? "active" : ""}">👨 David</button>
        </div>
      </div>
      <div class="avatar-widget-history">
        <div class="avatar-msg avatar-msg-avatar"><b>${this._escape(this.options.title)}:</b> ${this._escape(this.options.welcomeMessage)}</div>
      </div>
      <div class="avatar-widget-input-bar">
        <input class="avatar-widget-input" type="text" placeholder="Ask me anything..." />
        <button class="avatar-widget-btn btn-widget-mic" title="Voice Input">🎙️</button>
        <button class="avatar-widget-btn btn-widget-send">Send</button>
      </div>
    `;

    this.container.appendChild(wrapper);
    return wrapper;
  }

  private _setupSpeechRecognition(): void {
    if ("webkitSpeechRecognition" in window || "SpeechRecognition" in window) {
      const SpeechRec = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
      this.recognition = new SpeechRec();
      this.recognition.continuous = false;
      this.recognition.interimResults = false;
      this.recognition.lang = "en-US";

      this.recognition.onresult = (e: any) => {
        const transcript = e.results[0][0].transcript;
        const input = this.rootEl.querySelector(".avatar-widget-input") as HTMLInputElement;
        if (input) input.value = transcript;
        this.ask(transcript);
      };

      this.recognition.onend = () => {
        this.isListening = false;
        const micBtn = this.rootEl.querySelector(".btn-widget-mic") as HTMLButtonElement;
        if (micBtn) {
          micBtn.classList.remove("listening");
          micBtn.textContent = "🎙️";
        }
      };
    }
  }

  private _bindEvents(): void {
    const input = this.rootEl.querySelector(".avatar-widget-input") as HTMLInputElement;
    const sendBtn = this.rootEl.querySelector(".btn-widget-send") as HTMLButtonElement;
    const micBtn = this.rootEl.querySelector(".btn-widget-mic") as HTMLButtonElement;
    const btnFem = this.rootEl.querySelector(".btn-persona-female") as HTMLButtonElement;
    const btnMale = this.rootEl.querySelector(".btn-persona-male") as HTMLButtonElement;
    const engineSelect = this.rootEl.querySelector(".avatar-widget-engine-select") as HTMLSelectElement;

    const handleSend = () => {
      const text = input.value.trim();
      if (!text) return;
      input.value = "";
      this.ask(text);
    };

    sendBtn.onclick = handleSend;
    input.onkeydown = (e) => {
      if (e.key === "Enter") handleSend();
    };

    if (btnFem) {
      btnFem.onclick = () => this.setAvatar("female");
    }
    if (btnMale) {
      btnMale.onclick = () => this.setAvatar("male");
    }

    if (engineSelect) {
      engineSelect.onchange = () => {
        this.setEngine(engineSelect.value as any);
      };
    }

    micBtn.onclick = () => {
      if (!this.recognition) {
        alert("Speech recognition not supported in this browser. Please type your message.");
        return;
      }
      if (this.isListening) {
        this.recognition.stop();
      } else {
        this.recognition.start();
        this.isListening = true;
        micBtn.classList.add("listening");
        micBtn.textContent = "🔴";
        this._setStatus("Listening to your voice...", "speaking");
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
