/**
 * AvatarClient — the main public API of @avatar-sdk/client
 *
 * Usage:
 * ```typescript
 * import { AvatarClient } from "@avatar-sdk/client";
 *
 * const avatar = new AvatarClient({ serverUrl: "ws://localhost:8000" });
 * await avatar.connect();
 * avatar.mount(document.querySelector("#avatar-container")!);
 * await avatar.speak("Hello! I am your AI assistant.");
 * // Later:
 * avatar.interrupt();
 * avatar.destroy();
 * ```
 */
import { Transport } from "./transport";
import { AudioPlayer } from "./audio";
import { Renderer2D } from "./renderer2d";
import type {
  AvatarClientOptions,
  AvatarEventListener,
  AvatarEventMap,
  AvatarEventType,
  ConnectionState,
  ServerMessage,
  VisemeEvent,
} from "./types";

export class AvatarClient {
  private readonly opts: Required<AvatarClientOptions>;
  private transport: Transport | null = null;
  private audio: AudioPlayer | null = null;
  private renderer: Renderer2D | null = null;
  private sessionId: string | null = null;
  private _state: ConnectionState = "idle";
  private readonly listeners: Map<string, Set<Function>> = new Map();

  // Timing for TTFF measurement
  private speakCalledAt = 0;

  constructor(options: AvatarClientOptions) {
    this.opts = {
      avatarId: "default",
      reconnectDelayMs: 2000,
      maxReconnectAttempts: 5,
      ...options,
    };
  }

  // ─── Connection ────────────────────────────────────────────────────────────

  /**
   * Create a session on the server and open the WebSocket stream.
   * Must be called before speak() or mount().
   */
  async connect(): Promise<void> {
    if (this._state !== "idle" && this._state !== "closed") {
      throw new Error("AvatarClient is already connected or connecting.");
    }
    this._setState("connecting");

    // 1. Create session via REST
    const httpBase = this.opts.serverUrl
      .replace("wss://", "https://")
      .replace("ws://", "http://");

    const resp = await fetch(`${httpBase}/api/v1/sessions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ avatar_id: this.opts.avatarId }),
    });

    if (!resp.ok) {
      this._setState("closed");
      throw new Error(`Failed to create session: ${resp.status} ${resp.statusText}`);
    }

    const { session_id, ws_url } = await resp.json();
    this.sessionId = session_id;

    // 2. Open WebSocket stream
    const wsUrl = `${this.opts.serverUrl}${ws_url}`;
    this.transport = new Transport(
      wsUrl,
      this.opts.reconnectDelayMs,
      this.opts.maxReconnectAttempts,
      (msg) => this._handleMessage(msg),
      (reason) => {
        this._setState("closed");
        this._emit("disconnected", { reason });
      },
      () => {
        this._setState("connected");
      }
    );
    this.transport.connect();

    // 3. Init audio player
    this.audio = new AudioPlayer();
    await this.audio.init();

    // Wait for connected confirmation from server
    return new Promise((resolve, reject) => {
      const timeout = setTimeout(
        () => reject(new Error("Connection timeout")),
        10_000
      );
      const off = this._once("connected", () => {
        clearTimeout(timeout);
        resolve();
      });
    });
  }

  /**
   * Mount the 2D avatar canvas into a container element.
   * @param container - Any HTML element to render the avatar inside.
   */
  mount(container: HTMLElement): void {
    if (this.renderer) this.renderer.destroy();
    this.renderer = new Renderer2D(container);
  }

  // ─── Speech Control ────────────────────────────────────────────────────────

  /**
   * Send text to the avatar to speak.
   * If the avatar is currently speaking, it will be interrupted first (barge-in).
   * @param text - The text string to speak.
   */
  speak(text: string): void {
    if (!this.transport?.isOpen) {
      throw new Error("Not connected. Call connect() first.");
    }
    this.speakCalledAt = performance.now();
    this.transport.send({ action: "speak", text });
  }

  /**
   * Interrupt the avatar mid-speech immediately.
   * The avatar will stop speaking and return to the neutral mouth state.
   */
  interrupt(): void {
    if (!this.transport?.isOpen) return;
    this.transport.send({ action: "interrupt" });
    this.audio?.stop();
    this.renderer?.stopAnimation();
  }

  // ─── Message Handling ──────────────────────────────────────────────────────

  private _handleMessage(msg: ServerMessage): void {
    switch (msg.type) {
      case "connected":
        this._emit("connected", { sessionId: msg.session_id ?? "" });
        break;

      case "start":
        this.audio?.startNewSpeech();
        this._emit("speaking", { speechId: msg.speech_id ?? "" });
        break;

      case "viseme_timeline":
        if (msg.events && this.renderer) {
          this.renderer.loadTimeline(msg.events as VisemeEvent[]);
          if (this.audio) this.renderer.startAnimation(this.audio);
        }
        break;

      case "audio_chunk":
        if (msg.data) {
          // Measure TTFF on first chunk
          if (this.speakCalledAt > 0) {
            const ttff = performance.now() - this.speakCalledAt;
            console.info(`[AvatarSDK] TTFF: ${ttff.toFixed(0)}ms`);
            this.speakCalledAt = 0;
          }
          this.audio?.enqueueChunk(msg.data);
        }
        break;

      case "end":
        this.renderer?.stopAnimation();
        this._emit("ended", { speechId: msg.speech_id ?? "" });
        break;

      case "interrupted":
        this.audio?.stop();
        this.renderer?.stopAnimation();
        this._emit("interrupted", { speechId: msg.speech_id ?? "" });
        break;

      case "error":
        this._emit("error", { message: msg.message ?? "Unknown error" });
        break;

      case "pong":
        break;
    }
  }

  // ─── Events ────────────────────────────────────────────────────────────────

  on<T extends AvatarEventType>(event: T, listener: AvatarEventListener<T>): this {
    if (!this.listeners.has(event)) this.listeners.set(event, new Set());
    this.listeners.get(event)!.add(listener);
    return this;
  }

  off<T extends AvatarEventType>(event: T, listener: AvatarEventListener<T>): this {
    this.listeners.get(event)?.delete(listener);
    return this;
  }

  private _once<T extends AvatarEventType>(
    event: T,
    listener: AvatarEventListener<T>
  ): () => void {
    const wrapper = (payload: AvatarEventMap[T]) => {
      listener(payload);
      this.off(event, wrapper as AvatarEventListener<T>);
    };
    this.on(event, wrapper as AvatarEventListener<T>);
    return () => this.off(event, wrapper as AvatarEventListener<T>);
  }

  private _emit<T extends AvatarEventType>(event: T, payload: AvatarEventMap[T]): void {
    this.listeners.get(event)?.forEach((fn) => fn(payload));
  }

  // ─── State ─────────────────────────────────────────────────────────────────

  private _setState(state: ConnectionState): void {
    this._state = state;
  }

  get state(): ConnectionState {
    return this._state;
  }

  get sessionID(): string | null {
    return this.sessionId;
  }

  // ─── Cleanup ───────────────────────────────────────────────────────────────

  /**
   * Destroy the client — stops audio, removes the canvas, closes WebSocket.
   */
  async destroy(): Promise<void> {
    this.transport?.close();
    this.renderer?.destroy();
    await this.audio?.destroy();
    this.listeners.clear();
    this._setState("closed");
  }
}
