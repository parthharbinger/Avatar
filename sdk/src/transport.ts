/**
 * WebSocket transport layer.
 * Handles connection lifecycle, auto-reconnect, and message routing.
 * Consumers register onMessage and onClose callbacks.
 */
import type { ServerMessage } from "./types";

type MessageHandler = (msg: ServerMessage) => void;
type CloseHandler = (reason: string) => void;

export class Transport {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private _closed = false;

  constructor(
    private readonly url: string,
    private readonly reconnectDelayMs: number,
    private readonly maxReconnectAttempts: number,
    private readonly onMessage: MessageHandler,
    private readonly onClose: CloseHandler,
    private readonly onOpen: () => void
  ) {}

  connect(): void {
    this._closed = false;
    this._openSocket();
  }

  private _openSocket(): void {
    this.ws = new WebSocket(this.url);

    this.ws.onopen = () => {
      this.reconnectAttempts = 0;
      this.onOpen();
    };

    this.ws.onmessage = (event: MessageEvent) => {
      try {
        const msg: ServerMessage = JSON.parse(event.data as string);
        this.onMessage(msg);
      } catch {
        console.warn("[AvatarSDK] Failed to parse server message:", event.data);
      }
    };

    this.ws.onerror = (event) => {
      console.error("[AvatarSDK] WebSocket error:", event);
    };

    this.ws.onclose = (event) => {
      if (this._closed) {
        this.onClose("closed by client");
        return;
      }
      if (this.reconnectAttempts < this.maxReconnectAttempts) {
        this.reconnectAttempts++;
        console.warn(
          `[AvatarSDK] Disconnected. Reconnecting in ${this.reconnectDelayMs}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})...`
        );
        this.reconnectTimer = setTimeout(
          () => this._openSocket(),
          this.reconnectDelayMs
        );
      } else {
        this.onClose(`WebSocket closed: code=${event.code}`);
      }
    };
  }

  send(data: object): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    } else {
      console.warn("[AvatarSDK] Cannot send — WebSocket not open.");
    }
  }

  close(): void {
    this._closed = true;
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.ws?.close();
  }

  get isOpen(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}
