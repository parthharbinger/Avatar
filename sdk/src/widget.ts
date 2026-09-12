/**
 * AvatarWidget — Drop-in plug-and-play AI Avatar component.
 * Allows any website of any domain to embed a full interactive talking avatar
 * with voice input, conversational LLM, and lip-synced video in a single function call.
 */
import { AvatarClient } from "./client";

export interface AvatarWidgetOptions {
  /** Target container element or CSS selector string (e.g. "#ai-assistant") */
  target?: HTMLElement | string;
  /** Set to true to render as a floating bottom-right interactive assistant */
  floating?: boolean;
  /** Server URL of the avatar backend, e.g. "http://localhost:8000" */
  serverUrl?: string;
  /** Avatar persona: 'emma' / 'female', 'david' / 'male', or custom image URL */
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

export class AvatarWidget {
  private client: AvatarClient;
  private container: HTMLElement;
  private rootEl: HTMLElement;
  private chatHistory: Array<{ role: string; content: string }> = [];
  private options: Required<AvatarWidgetOptions>;
  private isListening = false;
  private recognition: any = null;

  constructor(options: AvatarWidgetOptions = {}) {
    const serverUrl = options.serverUrl || "http://localhost:8000";
    const wsUrl = serverUrl.replace("https://", "wss://").replace("http://", "ws://");

    this.options = {
      target: options.target || document.body,
      floating: options.floating ?? false,
      serverUrl,
      avatar: options.avatar || "female",
      voice: options.voice || (options.avatar === "male" || options.avatar === "david" ? "en-US-ChristopherNeural" : "en-US-JennyNeural"),
      title: options.title || "AI Assistant",
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

    // Initialize SDK Client
    this.client = new AvatarClient({
      serverUrl: wsUrl,
      avatarId: this.options.avatar,
    });

    this.rootEl = this._renderWidgetDOM();
    this._setupSpeechRecognition();
    this._bindEvents();
  }

  /** Initialize and connect the avatar */
  async init(): Promise<void> {
    const mountArea = this.rootEl.querySelector(".avatar-widget-canvas-slot") as HTMLElement;
    this.client.mount(mountArea, this.options.avatar);

    try {
      this._setStatus("Connecting...", "");
      await this.client.connect();
      this._setStatus("Online ✓", "ok");

      if (this.options.welcomeMessage) {
        this.addMessage("avatar", this.options.welcomeMessage);
        // Small delay before speaking greeting
        setTimeout(() => {
          this.client.speak(this.options.welcomeMessage, { voice: this.options.voice });
        }, 400);
      }
    } catch (err: any) {
      this._setStatus("Offline (Click to retry)", "error");
      console.error("[AvatarWidget] Connection error:", err);
    }
  }

  /** Speak arbitrary text */
  speak(text: string): void {
    this.addMessage("avatar", text);
    this.client.speak(text, { voice: this.options.voice });
  }

  /** Ask conversational AI a question */
  async ask(query: string): Promise<string> {
    this.addMessage("user", query);
    this._setStatus("Thinking...", "speaking");

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

      this.client.speak(reply, { voice: this.options.voice });
      return reply;
    } catch (err: any) {
      this._setStatus("Error generating response", "error");
      throw err;
    }
  }

  /** Interrupt current speech */
  interrupt(): void {
    this.client.interrupt();
    this._setStatus("Interrupted", "");
  }

  /** Add chat bubble to history */
  addMessage(role: "user" | "avatar", text: string): void {
    const historyEl = this.rootEl.querySelector(".avatar-widget-history") as HTMLElement;
    if (!historyEl) return;

    const bubble = document.createElement("div");
    bubble.className = `avatar-msg avatar-msg-${role}`;
    bubble.innerHTML = role === "user" ? `<b>You:</b> ${this._escape(text)}` : `<b>${this._escape(this.options.title)}:</b> ${this._escape(text)}`;
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
    const wrapper = document.createElement("div");
    wrapper.className = `avatar-widget-root ${isFloating ? "floating-widget" : "inline-widget"}`;

    wrapper.innerHTML = `
      <style>
        .avatar-widget-root {
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Plus Jakarta Sans", sans-serif;
          color: #f1f5f9;
          box-sizing: border-box;
          display: flex;
          flex-direction: column;
          background: rgba(15, 23, 42, 0.92);
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
          padding: 12px 16px;
          background: rgba(30, 41, 59, 0.8);
          border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        }
        .avatar-widget-title {
          font-size: 0.9rem;
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
          font-size: 0.75rem;
          color: #94a3b8;
        }
        .avatar-widget-status.ok { color: #34d399; }
        .avatar-widget-status.speaking { color: #38bdf8; font-weight: 600; }
        .avatar-widget-status.error { color: #f87171; }
        .avatar-widget-canvas-slot {
          width: 100%;
          height: 220px;
          background: #090d16;
          position: relative;
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
        <span class="avatar-widget-title">${this._escape(this.options.title)}</span>
        <span class="avatar-widget-status">Connecting...</span>
      </div>
      <div class="avatar-widget-canvas-slot"></div>
      <div class="avatar-widget-history"></div>
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

    micBtn.onclick = () => {
      if (!this.recognition) {
        alert("Speech recognition not supported in this browser.");
        return;
      }
      if (this.isListening) {
        this.recognition.stop();
      } else {
        this.recognition.start();
        this.isListening = true;
        micBtn.classList.add("listening");
        micBtn.textContent = "🔴";
        this._setStatus("Listening...", "speaking");
      }
    };

    this.client.on("speaking", () => this._setStatus("Speaking...", "speaking"));
    this.client.on("ended", () => this._setStatus("Online ✓", "ok"));
    this.client.on("interrupted", () => this._setStatus("Interrupted", ""));
    this.client.on("error", ({ message }) => this._setStatus(`Error: ${message}`, "error"));
  }

  private _escape(str: string): string {
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  /** Destroy widget and clean up DOM */
  async destroy(): Promise<void> {
    await this.client.destroy();
    this.rootEl.remove();
  }
}

/**
 * Functional factory helper for instant 1-line integration:
 * ```typescript
 * import { createAvatarWidget } from "@avatar-sdk/client";
 *
 * createAvatarWidget({ target: "#my-slot", avatar: "emma" });
 * ```
 */
export function createAvatarWidget(options?: AvatarWidgetOptions): AvatarWidget {
  const widget = new AvatarWidget(options);
  widget.init().catch(console.error);
  return widget;
}
