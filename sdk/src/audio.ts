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
  private nextStartTime = 0;
  private speechStartContextTime = 0;
  private activeSources: AudioBufferSourceNode[] = [];
  private _isPlaying = false;

  /** Initialise (or resume) the AudioContext — must be called after a user gesture */
  async init(): Promise<void> {
    if (!this.ctx || this.ctx.state === "closed") {
      this.ctx = new AudioContext();
    }
    if (this.ctx.state === "suspended") {
      await this.ctx.resume();
    }
  }

  /** Call before the first chunk of a new speech turn arrives */
  startNewSpeech(): void {
    if (!this.ctx) throw new Error("AudioPlayer.init() must be called first.");
    this.stop(); // clear any previous speech
    this.nextStartTime = this.ctx.currentTime + 0.05; // tiny buffer for smooth start
    this.speechStartContextTime = this.nextStartTime;
    this._isPlaying = true;
  }

  /**
   * Decode a base64-encoded MP3 chunk and schedule it for gapless playback.
   * @param base64 - base64 string of raw MP3 bytes
   */
  async enqueueChunk(base64: string): Promise<void> {
    if (!this.ctx || !this._isPlaying) return;

    const binary = atob(base64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);

    let buffer: AudioBuffer;
    try {
      buffer = await this.ctx.decodeAudioData(bytes.buffer);
    } catch {
      console.warn("[AvatarSDK] Failed to decode audio chunk — skipping.");
      return;
    }

    const source = this.ctx.createBufferSource();
    source.buffer = buffer;
    source.connect(this.ctx.destination);

    // Schedule this chunk to start right after the previous one ends
    const startAt = Math.max(this.nextStartTime, this.ctx.currentTime);
    source.start(startAt);
    this.nextStartTime = startAt + buffer.duration;
    this.activeSources.push(source);

    source.onended = () => {
      this.activeSources = this.activeSources.filter((s) => s !== source);
      if (this.activeSources.length === 0) this._isPlaying = false;
    };
  }

  /**
   * Returns elapsed playback time in milliseconds since speech started.
   * Used by Renderer2D to look up the correct viseme from the timeline.
   */
  getCurrentTimeMs(): number {
    if (!this.ctx || !this._isPlaying) return 0;
    return Math.max(0, (this.ctx.currentTime - this.speechStartContextTime) * 1000);
  }

  /** Stop all playback immediately (barge-in / interrupt) */
  stop(): void {
    this.activeSources.forEach((s) => {
      try { s.stop(); } catch { /* ignore if already stopped */ }
    });
    this.activeSources = [];
    this._isPlaying = false;
    this.nextStartTime = 0;
    this.speechStartContextTime = 0;
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
