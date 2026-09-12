/**
 * Renderer2D — renders a photorealistic AI avatar on HTML Canvas with
 * synchronized lip-sync morphing, natural eye blinking, and breathing micro-motion.
 */
import type { VisemeEvent, VisemeShape } from "./types";
import type { AudioPlayer } from "./audio";

export interface AvatarIdentity {
  name: string;
  imageSrc: string;
  mouthYRatio: number; // Ratio from top of image where mouth is located (e.g. 0.62)
  eyeYRatio: number;   // Ratio where eyes are located (e.g. 0.42)
}

export class Renderer2D {
  private canvas: HTMLCanvasElement;
  private ctx: CanvasRenderingContext2D;
  private rafId: number | null = null;
  private timeline: VisemeEvent[] = [];
  private currentShape: VisemeShape = "neutral";
  
  // Smoothing parameters
  private mouthOpen = 0;       // 0 to 1
  private mouthWidth = 1;      // 0.6 to 1.2
  private mouthRoundness = 0;  // 0 to 1
  private jawDrop = 0;

  // Blinking & idle animation
  private blinkVal = 0;
  private nextBlink = Date.now() + 2500;
  private avatarImg: HTMLImageElement | null = null;
  private isImgLoaded = false;
  private mouthYRatio = 0.355;
  private eyeYRatio = 0.255;

  constructor(container: HTMLElement, imageSrc: string = "assets/avatar_female.jpg") {
    this.canvas = document.createElement("canvas");
    this.canvas.width = 400;
    this.canvas.height = 400;
    this.canvas.style.cssText =
      "display:block;width:100%;height:100%;border-radius:16px;object-fit:cover;background:#0d1117;";
    container.appendChild(this.canvas);

    const ctx = this.canvas.getContext("2d");
    if (!ctx) throw new Error("Cannot get 2D canvas context.");
    this.ctx = ctx;

    this.setImage(imageSrc);
    this._startIdleLoop();
  }

  /** Set or change avatar portrait image */
  setImage(src: string): void {
    this.isImgLoaded = false;
    const img = new Image();
    if (src.startsWith("http://") || src.startsWith("https://")) {
      img.crossOrigin = "anonymous";
    }
    img.onload = () => {
      this.avatarImg = img;
      this.isImgLoaded = true;
      this._draw();
    };
    img.onerror = () => {
      // Fallback to gradient if image fails to load
      this.isImgLoaded = false;
      this._draw();
    };
    img.src = src;
  }

  /** Load a new viseme timeline for an upcoming speech turn */
  loadTimeline(events: VisemeEvent[]): void {
    this.timeline = [...events].sort((a, b) => a.t - b.t);
  }

  private _startIdleLoop(): void {
    const loop = () => {
      this._updateBlink();
      this._updateMouthPhysics(0.12);
      this._draw();
      this.rafId = requestAnimationFrame(loop);
    };
    this.rafId = requestAnimationFrame(loop);
  }

  /** Start speech animation synchronised to AudioPlayer */
  startAnimation(audio: AudioPlayer): void {
    if (this.rafId !== null) cancelAnimationFrame(this.rafId);

    const loop = () => {
      const nowMs = audio.getCurrentTimeMs();
      this._updateViseme(nowMs);
      this._updateBlink();
      this._updateMouthPhysics(0.25);
      this._draw();
      this.rafId = requestAnimationFrame(loop);
    };
    this.rafId = requestAnimationFrame(loop);
  }

  /** Stop speech animation loop and reset mouth */
  stopAnimation(): void {
    this.currentShape = "neutral";
    this.timeline = [];
    if (this.rafId !== null) {
      cancelAnimationFrame(this.rafId);
    }
    this._startIdleLoop();
  }

  private _updateViseme(nowMs: number): void {
    if (this.timeline.length === 0) {
      this.currentShape = "neutral";
      return;
    }
    // Binary search for closest viseme keyframe
    let lo = 0, hi = this.timeline.length - 1, best = 0;
    while (lo <= hi) {
      const mid = (lo + hi) >> 1;
      if (this.timeline[mid].t <= nowMs) {
        best = mid;
        lo = mid + 1;
      } else {
        hi = mid - 1;
      }
    }
    this.currentShape = this.timeline[best].v;
  }

  private _updateMouthPhysics(speed: number): void {
    let targetOpen = 0;
    let targetWidth = 1.0;
    let targetRound = 0.0;
    let targetJaw = 0.0;

    switch (this.currentShape) {
      case "open": // Ah, Eh
        targetOpen = 0.85;
        targetWidth = 1.1;
        targetJaw = 4.0;
        break;
      case "round": // Oh, Oo
        targetOpen = 0.65;
        targetWidth = 0.7;
        targetRound = 0.9;
        targetJaw = 3.0;
        break;
      case "dental": // L, N, T, S
        targetOpen = 0.35;
        targetWidth = 1.15;
        targetJaw = 1.5;
        break;
      case "labiodental": // F, V
        targetOpen = 0.25;
        targetWidth = 0.95;
        targetJaw = 1.0;
        break;
      case "bilabial": // M, B, P
        targetOpen = 0.05;
        targetWidth = 1.0;
        targetJaw = 0.5;
        break;
      case "neutral":
      default:
        targetOpen = 0.0;
        targetWidth = 1.0;
        targetRound = 0.0;
        targetJaw = 0.0;
        break;
    }

    // Smooth spring lerp
    this.mouthOpen += (targetOpen - this.mouthOpen) * speed;
    this.mouthWidth += (targetWidth - this.mouthWidth) * speed;
    this.mouthRoundness += (targetRound - this.mouthRoundness) * speed;
    this.jawDrop += (targetJaw - this.jawDrop) * speed;
  }

  private _updateBlink(): void {
    const now = Date.now();
    if (now >= this.nextBlink) {
      this.blinkVal = Math.min(1, this.blinkVal + 0.18);
      if (this.blinkVal >= 1) {
        this.blinkVal = 0;
        this.nextBlink = now + 2500 + Math.random() * 3500;
      }
    }
  }

  private _draw(): void {
    const { ctx, canvas } = this;
    const w = canvas.width;
    const h = canvas.height;
    const cx = w / 2;
    const cy = h / 2;

    ctx.clearRect(0, 0, w, h);

    // Subtle natural breathing micro-motion
    const breathe = Math.sin(Date.now() / 1200) * 1.5;

    if (this.isImgLoaded && this.avatarImg) {
      // 1. Draw High-Res Photorealistic Avatar Portrait
      ctx.save();
      // Draw image with breathing motion
      ctx.drawImage(this.avatarImg, 0, breathe, w, h);
      ctx.restore();

      // 2. Realistic Eye Blinks (Subtle upper eyelid shading)
      if (this.blinkVal > 0.05) {
        this._drawRealisticBlink(ctx, w * 0.455, h * this.eyeYRatio + breathe, 18, this.blinkVal);
        this._drawRealisticBlink(ctx, w * 0.545, h * this.eyeYRatio + breathe, 18, this.blinkVal);
      }

      // 3. Realistic Dynamic Mouth Blend
      const mouthX = cx;
      const mouthY = h * this.mouthYRatio + breathe + this.jawDrop * 0.5;
      this._drawRealisticMouth(ctx, mouthX, mouthY);

    } else {
      // High-quality procedural fallback
      this._drawProceduralAvatar(ctx, cx, cy + breathe);
    }
  }

  private _drawRealisticBlink(
    ctx: CanvasRenderingContext2D,
    x: number,
    y: number,
    radius: number,
    progress: number
  ): void {
    ctx.save();
    ctx.beginPath();
    ctx.ellipse(x, y, radius, radius * 0.65 * progress, 0, 0, Math.PI * 2);
    ctx.fillStyle = "rgba(180, 130, 110, 0.95)";
    ctx.fill();
    // Eyelash line
    ctx.beginPath();
    ctx.ellipse(x, y + (radius * 0.3 * progress), radius, 1.5, 0, 0, Math.PI);
    ctx.strokeStyle = "rgba(40, 20, 15, 0.85)";
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.restore();
  }

  private _drawRealisticMouth(ctx: CanvasRenderingContext2D, x: number, y: number): void {
    const openH = this.mouthOpen * 14;
    const baseW = 28 * this.mouthWidth;

    if (this.mouthOpen < 0.05) {
      // Natural resting mouth — subtle clean lip line
      ctx.save();
      ctx.beginPath();
      ctx.moveTo(x - baseW, y);
      ctx.quadraticCurveTo(x, y + 2.5, x + baseW, y);
      ctx.strokeStyle = "rgba(120, 50, 45, 0.4)";
      ctx.lineWidth = 1.8;
      ctx.stroke();
      ctx.restore();
      return;
    }

    ctx.save();

    // 1. Oral cavity (depth)
    ctx.beginPath();
    ctx.ellipse(x, y + openH * 0.2, baseW, Math.max(1, openH), 0, 0, Math.PI * 2);
    const cavityGrad = ctx.createRadialGradient(x, y, 2, x, y, openH + 10);
    cavityGrad.addColorStop(0, "#4a121a");
    cavityGrad.addColorStop(1, "#180507");
    ctx.fillStyle = cavityGrad;
    ctx.fill();

    // 2. Teeth (upper & lower)
    if (this.mouthOpen > 0.15) {
      ctx.fillStyle = "rgba(245, 242, 238, 0.92)";
      // Upper teeth row
      ctx.beginPath();
      ctx.ellipse(x, y - openH * 0.3, baseW * 0.75, Math.min(4, openH * 0.35), 0, 0, Math.PI);
      ctx.fill();
      // Lower teeth row (visible on wide open)
      if (this.mouthOpen > 0.5) {
        ctx.beginPath();
        ctx.ellipse(x, y + openH * 0.6, baseW * 0.6, Math.min(3, openH * 0.25), 0, Math.PI, Math.PI * 2);
        ctx.fill();
      }
    }

    // 3. Tongue
    if (this.mouthOpen > 0.3) {
      ctx.beginPath();
      ctx.ellipse(x, y + openH * 0.55, baseW * 0.55, openH * 0.35, 0, 0, Math.PI);
      ctx.fillStyle = "rgba(195, 80, 85, 0.85)";
      ctx.fill();
    }

    // 4. Upper Lip Contour
    ctx.beginPath();
    ctx.moveTo(x - baseW - 2, y);
    ctx.quadraticCurveTo(x - baseW * 0.4, y - openH * 0.4 - 2, x, y - openH * 0.25);
    ctx.quadraticCurveTo(x + baseW * 0.4, y - openH * 0.4 - 2, x + baseW + 2, y);
    ctx.quadraticCurveTo(x, y - openH * 0.1, x - baseW - 2, y);
    const upperLipGrad = ctx.createLinearGradient(x, y - 6, x, y);
    upperLipGrad.addColorStop(0, "rgba(190, 85, 80, 0.85)");
    upperLipGrad.addColorStop(1, "rgba(140, 50, 50, 0.9)");
    ctx.fillStyle = upperLipGrad;
    ctx.fill();

    // 5. Lower Lip Contour
    ctx.beginPath();
    ctx.moveTo(x - baseW - 2, y);
    ctx.quadraticCurveTo(x, y + openH + 5, x + baseW + 2, y);
    ctx.quadraticCurveTo(x, y + openH * 0.8, x - baseW - 2, y);
    const lowerLipGrad = ctx.createLinearGradient(x, y, x, y + openH + 6);
    lowerLipGrad.addColorStop(0, "rgba(160, 60, 60, 0.9)");
    lowerLipGrad.addColorStop(1, "rgba(210, 95, 90, 0.85)");
    ctx.fillStyle = lowerLipGrad;
    ctx.fill();

    // 6. Subtle lip shine / highlight
    ctx.beginPath();
    ctx.ellipse(x, y + openH + 2, baseW * 0.35, 1.5, 0, 0, Math.PI * 2);
    ctx.fillStyle = "rgba(255, 255, 255, 0.25)";
    ctx.fill();

    ctx.restore();
  }

  private _drawProceduralAvatar(ctx: CanvasRenderingContext2D, cx: number, cy: number): void {
    const r = 140;
    const grad = ctx.createRadialGradient(cx - 20, cy - 20, 10, cx, cy, r);
    grad.addColorStop(0, "#4a90d9");
    grad.addColorStop(1, "#1a3a6e");
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.fillStyle = grad;
    ctx.fill();

    // Eyes
    const blinkH = 12 * (1 - this.blinkVal);
    ctx.fillStyle = "#ffffff";
    ctx.beginPath();
    ctx.ellipse(cx - 45, cy - 30, 15, Math.max(1, blinkH), 0, 0, Math.PI * 2);
    ctx.ellipse(cx + 45, cy - 30, 15, Math.max(1, blinkH), 0, 0, Math.PI * 2);
    ctx.fill();

    // Pupils
    ctx.fillStyle = "#111827";
    ctx.beginPath();
    ctx.arc(cx - 45, cy - 30, 7, 0, Math.PI * 2);
    ctx.arc(cx + 45, cy - 30, 7, 0, Math.PI * 2);
    ctx.fill();

    // Mouth
    this._drawRealisticMouth(ctx, cx, cy + 45);
  }

  destroy(): void {
    this.stopAnimation();
    if (this.rafId !== null) cancelAnimationFrame(this.rafId);
    this.canvas.remove();
  }
}
