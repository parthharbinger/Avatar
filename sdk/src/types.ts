/**
 * Public type definitions for @avatar-sdk/client
 */

/** Configuration options for AvatarClient */
export interface AvatarClientOptions {
  /** WebSocket URL of the avatar backend, e.g. "ws://localhost:8000" */
  serverUrl: string;
  /** Avatar identity to use. Defaults to "default". */
  avatarId?: string;
  /** Milliseconds before reconnect is attempted on connection loss. Default: 2000 */
  reconnectDelayMs?: number;
  /** Max reconnect attempts before giving up. Default: 5 */
  maxReconnectAttempts?: number;
}

/** Viseme mouth shape names matching the backend's VisemeShape enum */
export type VisemeShape =
  | "neutral"
  | "open"
  | "round"
  | "bilabial"
  | "labiodental"
  | "dental";

/** A single keyframe in the viseme animation timeline */
export interface VisemeEvent {
  /** Time offset in milliseconds from start of speech */
  t: number;
  /** Mouth shape to display */
  v: VisemeShape;
}

/** All event types emitted by AvatarClient */
export type AvatarEventType =
  | "connected"
  | "disconnected"
  | "speaking"
  | "ended"
  | "interrupted"
  | "error"
  | "viseme";

/** Payload for each event type */
export interface AvatarEventMap {
  connected: { sessionId: string };
  disconnected: { reason: string };
  speaking: { speechId: string };
  ended: { speechId: string };
  interrupted: { speechId: string };
  error: { message: string };
  viseme: { shape: VisemeShape; timeMs: number };
}

/** Typed event listener callback */
export type AvatarEventListener<T extends AvatarEventType> = (
  payload: AvatarEventMap[T]
) => void;

/** Connection state of the AvatarClient */
export type ConnectionState =
  | "idle"
  | "connecting"
  | "connected"
  | "reconnecting"
  | "closed";

/** Incoming server message types */
export interface ServerMessage {
  type:
    | "connected"
    | "start"
    | "viseme_timeline"
    | "audio_chunk"
    | "end"
    | "interrupted"
    | "error"
    | "pong";
  speech_id?: string;
  session_id?: string;
  events?: VisemeEvent[];
  data?: string; // base64 audio chunk
  chunk_index?: number;
  message?: string;
}

// ── RAG / Avatar Profile Types ─────────────────────────────────────────────────

/** A document that has been indexed for an avatar profile */
export interface ProfileDocument {
  doc_id: string;
  filename: string;
  chunk_count: number;
  uploaded_at: string;
}

/** An avatar expert profile with a name, persona, and document knowledge base */
export interface AvatarProfile {
  profile_id: string;
  name: string;
  /** Avatar visual preset: 'male' | 'female' */
  persona: string;
  system_prompt: string;
  created_at: string;
  documents: ProfileDocument[];
}

/** Options for creating a new avatar expert profile */
export interface CreateProfileOptions {
  name: string;
  persona?: "male" | "female";
  system_prompt?: string;
}

/** Voice conversation turn-taking state */
export type ConversationState =
  | "idle"          // Mic off, no voice loop
  | "listening"     // Actively listening for user speech
  | "processing"    // LLM generating response
  | "speaking";     // Avatar speaking
