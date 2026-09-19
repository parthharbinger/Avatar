/**
 * AudioPlayer — queues and plays streaming MP3 audio chunks using Web Audio API.
 *
 * Strategy:
 *   - Each arriving base64 chunk is decoded via AudioContext.decodeAudioData().
 *   - Chunks are scheduled as AudioBufferSourceNodes chained back-to-back.
 *   - currentTime() returns the AudioContext clock offset from speech start,
 *     which the Renderer2D uses to synchronise viseme mouth shapes.
 */
export class AudioPlayer {
  private ctx: AudioContext | null = null;
  private currentSource: AudioBufferSourceNode | null = null;
  private rawChunks: Uint8Array[] = [];
  private totalBytes = 0;
  private speechStartContextTime = 0;
  private _isPlaying = false;
  private audioEl: HTMLAudioElement | null = null;
  private useNativeAudio = false;

  /** Initialise (or resume) the AudioContext — must be called after a user gesture */
  async init(): Promise<void> {
    if (!this.ctx || this.ctx.state === "closed") {
      const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      this.ctx = new AudioCtx();
    }
    if (this.ctx.state === "suspended") {
      await this.ctx.resume();
    }
  }

  private isBuffering = false;

  /** Call before the first chunk of a new speech turn arrives */
  startNewSpeech(): void {
    this.stop(); // clear any previous speech
    this.rawChunks = [];
    this.totalBytes = 0;
    this.speechStartContextTime = 0;
    this._isPlaying = false;
    this.isBuffering = true;
  }

  /**
   * Enqueue a base64-encoded MP3 chunk into the stream accumulator.
   * @param base64 - base64 string of raw MP3 bytes
   */
  async enqueueChunk(base64: string): Promise<void> {
    if (!this.isBuffering) return;

    const binary = atob(base64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
      bytes[i] = binary.charCodeAt(i);
    }

    this.rawChunks.push(bytes);
    this.totalBytes += bytes.length;
  }

  /**
   * Finalize and start playing the accumulated audio seamlessly.
   */
  async finishSpeech(onEnded?: () => void): Promise<void> {
    this.isBuffering = false;
    if (this.totalBytes === 0) {
      if (onEnded) onEnded();
      return;
    }

    // Concatenate all chunks into a single valid MP3 ArrayBuffer
    const fullBuffer = new Uint8Array(this.totalBytes);
    let offset = 0;
    for (const chunk of this.rawChunks) {
      fullBuffer.set(chunk, offset);
      offset += chunk.length;
    }

    try {
      if (this.ctx && this.ctx.state !== "closed") {
        if (this.ctx.state === "suspended") {
          await this.ctx.resume();
        }

        const audioBuffer = await this.ctx.decodeAudioData(fullBuffer.buffer.slice(0));
        
        // Stop any currently playing source
        if (this.currentSource) {
          try { this.currentSource.stop(); } catch { /* ignore */ }
        }

        const source = this.ctx.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(this.ctx.destination);

        this.speechStartContextTime = this.ctx.currentTime;
        this._isPlaying = true;
        source.start(this.speechStartContextTime);
        this.currentSource = source;

        source.onended = () => {
          if (this.currentSource === source) {
            this._isPlaying = false;
            this.currentSource = null;
            if (onEnded) onEnded();
          }
        };
        return;
      }
    } catch (err) {
      console.warn("[AvatarSDK] Web Audio decode failed, falling back to HTML5 Audio:", err);
    }

    // Fallback: HTML5 Audio Blob playback
    try {
      const blob = new Blob([fullBuffer], { type: "audio/mp3" });
      const url = URL.createObjectURL(blob);
      if (this.audioEl) {
        this.audioEl.pause();
        this.audioEl = null;
      }
      this.audioEl = new Audio(url);
      this.useNativeAudio = true;
      this._isPlaying = true;
      this.audioEl.onended = () => {
        this._isPlaying = false;
        URL.revokeObjectURL(url);
        if (onEnded) onEnded();
      };
      await this.audioEl.play();
    } catch (err) {
      console.error("[AvatarSDK] Audio playback error:", err);
      this._isPlaying = false;
      if (onEnded) onEnded();
    }
  }

  /**
   * Returns elapsed playback time in milliseconds since speech started.
   * Used by Renderer2D to look up the correct viseme from the timeline.
   */
  getCurrentTimeMs(): number {
    if (!this._isPlaying || !this.speechStartContextTime) return 0;
    if (this.useNativeAudio && this.audioEl) {
      return this.audioEl.currentTime * 1000;
    }
    if (!this.ctx || !this.currentSource) return 0;
    return Math.max(0, (this.ctx.currentTime - this.speechStartContextTime) * 1000);
  }

  /** Stop all playback immediately (barge-in / interrupt) */
  stop(): void {
    if (this.currentSource) {
      try { this.currentSource.stop(); } catch { /* ignore */ }
      this.currentSource = null;
    }
    if (this.audioEl) {
      try {
        this.audioEl.pause();
        this.audioEl.currentTime = 0;
      } catch { /* ignore */ }
      this.audioEl = null;
    }
    this.rawChunks = [];
    this.totalBytes = 0;
    this._isPlaying = false;
    this.speechStartContextTime = 0;
    this.useNativeAudio = false;
  }

  get isPlaying(): boolean {
    return this._isPlaying;
  }

  async destroy(): Promise<void> {
    this.stop();
    await this.ctx?.close();
    this.ctx = null;
  }
}
