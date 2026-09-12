/**
 * Renderer2D — draws the 2D avatar on an HTML Canvas element.
 *
 * Layers (bottom to top):
 *   1. Background fill
 *   2. Head / face circle
 *   3. Eyes (with randomised blinking)
 *   4. Mouth (driven by viseme timeline)
 *
 * The animation loop runs via requestAnimationFrame and queries
 * AudioPlayer.getCurrentTimeMs() to pick the correct mouth shape.
 */
import type { VisemeEvent, VisemeShape } from "./types";
import type { AudioPlayer } from "./audio";

interface EyeState {
  blinkProgress: number; // 0 = open, 1 = fully closed
  nextBlinkAt: number;   // ms timestamp for next blink
}

export class Renderer2D {
  private canvas: HTMLCanvasElement;
  private ctx: CanvasRenderingContext2D;
  private rafId: number | null = null;
  private timeline: VisemeEvent[] = [];
  private currentShape: VisemeShape = "neutral";
  private eye: EyeState = { blinkProgress: 0, nextBlinkAt: Date.now() + 2000 };

  constructor(container: HTMLElement) {
    this.canvas = document.createElement("canvas");
    this.canvas.width = 320;
    this.canvas.height = 320;
    this.canvas.style.cssText =
      "display:block;border-radius:50%;background:#1a1a2e;";
    container.appendChild(this.canvas);

    const ctx = this.canvas.getContext("2d");
    if (!ctx) throw new Error("Cannot get 2D canvas context.");
    this.ctx = ctx;

    this._drawNeutral();
  }

  /** Load a new viseme timeline for an upcoming speech turn */
  loadTimeline(events: VisemeEvent[]): void {
    this.timeline = [...events].sort((a, b) => a.t - b.t);
  }

  /** Start the animation loop, synchronised to AudioPlayer */
  startAnimation(audio: AudioPlayer): void {
    const loop = () => {
      const nowMs = audio.getCurrentTimeMs();
      this._updateViseme(nowMs);
      this._updateBlink();
      this._draw();
      this.rafId = requestAnimationFrame(loop);
    };
    this.rafId = requestAnimationFrame(loop);
  }

  /** Stop the animation loop and reset to neutral */
  stopAnimation(): void {
    if (this.rafId !== null) {
      cancelAnimationFrame(this.rafId);
      this.rafId = null;
    }
    this.currentShape = "neutral";
    this._drawNeutral();
  }

  private _updateViseme(nowMs: number): void {
    if (this.timeline.length === 0) return;
    // Binary search: find last event whose time <= nowMs
    let lo = 0, hi = this.timeline.length - 1, best = 0;
    while (lo <= hi) {
      const mid = (lo + hi) >> 1;
      if (this.timeline[mid].t <= nowMs) { best = mid; lo = mid + 1; }
      else hi = mid - 1;
    }
    this.currentShape = this.timeline[best].v;
  }

  private _updateBlink(): void {
    const now = Date.now();
    if (now >= this.eye.nextBlinkAt) {
      this.eye.blinkProgress = Math.min(1, this.eye.blinkProgress + 0.15);
      if (this.eye.blinkProgress >= 1) {
        this.eye.blinkProgress = 0;
        this.eye.nextBlinkAt = now + 2000 + Math.random() * 3000;
      }
    }
  }

  private _drawNeutral(): void {
    this._draw();
  }

  private _draw(): void {
    const { ctx, canvas } = this;
    const cx = canvas.width / 2;
    const cy = canvas.height / 2;
    const r = 130;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // — Head —
    const grad = ctx.createRadialGradient(cx - 20, cy - 20, 10, cx, cy, r);
    grad.addColorStop(0, "#4a90d9");
    grad.addColorStop(1, "#1a3a6e");
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.fillStyle = grad;
    ctx.fill();

    // — Eyes —
    this._drawEye(ctx, cx - 42, cy - 28);
    this._drawEye(ctx, cx + 42, cy - 28);

    // — Mouth —
    this._drawMouth(ctx, cx, cy + 48, this.currentShape);
  }

  private _drawEye(ctx: CanvasRenderingContext2D, x: number, y: number): void {
    const openH = 12;
    const h = openH * (1 - this.eye.blinkProgress);
    ctx.beginPath();
    ctx.ellipse(x, y, 14, Math.max(1, h), 0, 0, Math.PI * 2);
    ctx.fillStyle = "#ffffff";
    ctx.fill();
    // Pupil
    ctx.beginPath();
    ctx.arc(x, y, 7, 0, Math.PI * 2);
    ctx.fillStyle = "#111";
    ctx.fill();
  }

  private _drawMouth(
    ctx: CanvasRenderingContext2D,
    x: number,
    y: number,
    shape: VisemeShape
  ): void {
    ctx.fillStyle = "#1a0a0a";
    ctx.strokeStyle = "#ffb3a7";
    ctx.lineWidth = 2;

    switch (shape) {
      case "neutral":
        // Thin smile
        ctx.beginPath();
        ctx.moveTo(x - 28, y);
        ctx.quadraticCurveTo(x, y + 10, x + 28, y);
        ctx.strokeStyle = "#ffb3a7";
        ctx.lineWidth = 3;
        ctx.stroke();
        break;

      case "open":
        // Wide open oval — Ah/Eh
        ctx.beginPath();
        ctx.ellipse(x, y + 4, 28, 20, 0, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
        break;

      case "round":
        // Small round — Oh/Oo
        ctx.beginPath();
        ctx.ellipse(x, y + 4, 16, 16, 0, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
        break;

      case "bilabial":
        // Almost closed — M/B/P
        ctx.beginPath();
        ctx.ellipse(x, y, 28, 4, 0, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
        break;

      case "labiodental":
        // Bottom lip raised — F/V
        ctx.beginPath();
        ctx.ellipse(x, y + 2, 24, 10, 0, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
        break;

      case "dental":
        // Slightly open, wide — L/N/T
        ctx.beginPath();
        ctx.ellipse(x, y + 4, 26, 13, 0, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
        break;
    }
  }

  destroy(): void {
    this.stopAnimation();
    this.canvas.remove();
  }
}
