/**
 * Renderer2D — High-fidelity 2D Neural Canvas Renderer.
 * Features Whole-Face 15-Viseme Photorealistic Animation with Seamless Alpha-Crossfading,
 * anatomical eyelid curvature with natural skin blending, and breathing micro-motion.
 */
import type { VisemeEvent, VisemeShape } from "./types";
import type { AudioPlayer } from "./audio";

// 4x4 Grid coordinates for the 15-Viseme Whole-Face Sprite Atlas
const VISEME_GRID: Record<string, { col: number; row: number }> = {
  neutral: { col: 0, row: 0 },
  sil: { col: 0, row: 0 },
  aa: { col: 1, row: 0 },   // 'Ah' - wide open jaw
  O: { col: 2, row: 0 },    // 'Oh' - open oval circle
  U: { col: 3, row: 0 },    // 'Oo' / 'W' - small tight circle pucker
  E: { col: 0, row: 1 },    // 'Ee' - wide smile teeth
  eh: { col: 1, row: 1 },   // 'Eh' - open smile
  I: { col: 2, row: 1 },    // 'Ay' / 'Ii' - stretched teeth
  ih: { col: 3, row: 1 },   // 'Ii' - open dental
  SS: { col: 0, row: 2 },   // 'L' / 'S' / 'Z' - dental sibilant
  FF: { col: 1, row: 2 },   // 'F' / 'V' - lower lip under upper teeth
  TH: { col: 2, row: 2 },   // 'Th' - tongue touching upper teeth
  DD: { col: 3, row: 2 },   // 'T' / 'D' / 'N' - alveolar tongue
  PP: { col: 0, row: 3 },   // 'M' / 'B' / 'P' - bilabial closed lips
  kk: { col: 1, row: 3 },   // 'K' / 'G' - velar
  CH: { col: 2, row: 3 },   // 'Sh' / 'Ch' / 'Zh' - pursed lips
  RR: { col: 3, row: 3 },   // 'R' / 'Rest' - relaxed open
  // Legacy aliases
  open: { col: 1, row: 0 },
  round: { col: 2, row: 0 },
  dental: { col: 0, row: 2 },
  labiodental: { col: 1, row: 2 },
  bilabial: { col: 0, row: 3 },
};

export class Renderer2D {
  private canvas: HTMLCanvasElement;
  private ctx: CanvasRenderingContext2D;
  private rafId: number | null = null;
  private timeline: VisemeEvent[] = [];
  
  // 15-Viseme Whole-Face Crossfade state
  private currViseme: string = "neutral";
  private prevViseme: string = "neutral";
  private blendWeight = 1.0; // 0.0 to 1.0
  private lastFrameTime = performance.now();

  // Smoothing parameters for procedural fallback
  private mouthOpen = 0;       // 0 to 1
  private mouthWidth = 1;      // 0.6 to 1.3
  private mouthRoundness = 0;  // 0 to 1
  private jawDrop = 0;

  // Natural Blinking & micro-motion
  private blinkVal = 0;
  private blinkDirection = 1;  // 1 = closing, -1 = opening
  private nextBlink = Date.now() + 2500;
  
  // Asset images
  private avatarImg: HTMLImageElement | null = null;
  private visemeAtlasImg: HTMLImageElement | null = null;
  private isImgLoaded = false;
  private isAtlasLoaded = false;
  private isMale = false;

  constructor(container: HTMLElement, imageSrc: string = "female") {
    this.canvas = document.createElement("canvas");
    this.canvas.width = 400;
    this.canvas.height = 400;
    this.canvas.style.cssText =
      "display:block;width:100%;height:100%;border-radius:18px;object-fit:cover;background:#090d16;";
    container.appendChild(this.canvas);

    const ctx = this.canvas.getContext("2d");
    if (!ctx) {
      this.ctx = {} as CanvasRenderingContext2D;
      return;
    }
    this.ctx = ctx;

    this.setImage(imageSrc);
    this._startIdleLoop();
  }

  /** Set or change avatar portrait image (supports 'female'/'emma', 'male'/'david', or custom URL) */
  setImage(src: string = "female"): void {
    this.isImgLoaded = false;
    this.isAtlasLoaded = false;
    let resolvedSrc = src;
    let atlasSrc = "http://localhost:8000/assets/full_face_female_atlas.jpg";
    const lower = src.toLowerCase();

    if (lower === "ecommerce" || lower === "elena" || lower === "retail") {
      resolvedSrc = "http://localhost:8000/assets/avatar_ecommerce.jpg";
      atlasSrc = "http://localhost:8000/assets/full_face_female_atlas.jpg";
      this.isMale = false;
    } else if (lower === "healthcare" || lower === "maya" || lower === "medical" || lower === "doctor") {
      resolvedSrc = "http://localhost:8000/assets/avatar_healthcare.jpg";
      atlasSrc = "http://localhost:8000/assets/full_face_female_atlas.jpg";
      this.isMale = false;
    } else if (lower === "banking" || lower === "alexander" || lower === "finance" || lower === "bank") {
      resolvedSrc = "http://localhost:8000/assets/avatar_banking.jpg";
      atlasSrc = "http://localhost:8000/assets/full_face_male_atlas.jpg";
      this.isMale = true;
    } else if (lower === "female" || lower === "emma" || lower === "default" || lower === "") {
      resolvedSrc = "http://localhost:8000/assets/avatar_female.jpg";
      atlasSrc = "http://localhost:8000/assets/full_face_female_atlas.jpg";
      this.isMale = false;
    } else if (lower === "male" || lower === "david" || lower === "adam") {
      resolvedSrc = "http://localhost:8000/assets/avatar_male.jpg";
      atlasSrc = "http://localhost:8000/assets/full_face_male_atlas.jpg";
      this.isMale = true;
    } else {
      this.isMale = lower.includes("male") || lower.includes("david") || lower.includes("adam") || lower.includes("banking") || lower.includes("alexander");
      atlasSrc = this.isMale
        ? "http://localhost:8000/assets/full_face_male_atlas.jpg"
        : "http://localhost:8000/assets/full_face_female_atlas.jpg";
    }

    // 1. Load Base Portrait (Fallback)
    const img = new Image();
    if (resolvedSrc.startsWith("http://") || resolvedSrc.startsWith("https://")) {
      img.crossOrigin = "anonymous";
    }
    img.onload = () => {
      this.avatarImg = img;
      this.isImgLoaded = true;
      this._draw();
    };
    img.onerror = () => {
      if (resolvedSrc.includes("/assets/")) {
        const altImg = new Image();
        altImg.onload = () => {
          this.avatarImg = altImg;
          this.isImgLoaded = true;
          this._draw();
        };
        altImg.onerror = () => {
          this.isImgLoaded = false;
          this._draw();
        };
        altImg.src = resolvedSrc.replace("http://localhost:8000/", "./");
      } else {
        this.isImgLoaded = false;
        this._draw();
      }
    };
    img.src = resolvedSrc;

    // 2. Load Whole-Face 15-Viseme Sprite Atlas
    const atlas = new Image();
    if (atlasSrc.startsWith("http://") || atlasSrc.startsWith("https://")) {
      atlas.crossOrigin = "anonymous";
    }
    atlas.onload = () => {
      this.visemeAtlasImg = atlas;
      this.isAtlasLoaded = true;
    };
    atlas.onerror = () => {
      if (atlasSrc.includes("/assets/")) {
        const altAtlas = new Image();
        altAtlas.onload = () => {
          this.visemeAtlasImg = altAtlas;
          this.isAtlasLoaded = true;
        };
        altAtlas.onerror = () => {
          this.isAtlasLoaded = false;
        };
        altAtlas.src = atlasSrc.replace("http://localhost:8000/", "./");
      } else {
        this.isAtlasLoaded = false;
      }
    };
    atlas.src = atlasSrc;
  }

  /** Load a new viseme timeline for an upcoming speech turn */
  loadTimeline(events: VisemeEvent[]): void {
    this.timeline = [...events].sort((a, b) => a.t - b.t);
  }

  private _startIdleLoop(): void {
    const loop = (timestamp: number) => {
      const dt = Math.min(0.1, (timestamp - this.lastFrameTime) * 0.001);
      this.lastFrameTime = timestamp;

      this._updateBlink();
      this._updateCrossfade(dt);
      this._updateMouthPhysics(0.14);
      this._draw();
      this.rafId = requestAnimationFrame(loop);
    };
    this.lastFrameTime = performance.now();
    this.rafId = requestAnimationFrame(loop);
  }

  /** Start speech animation synchronised to AudioPlayer */
  startAnimation(audio: AudioPlayer): void {
    if (this.rafId !== null) cancelAnimationFrame(this.rafId);

    const loop = (timestamp: number) => {
      const dt = Math.min(0.1, (timestamp - this.lastFrameTime) * 0.001);
      this.lastFrameTime = timestamp;

      const nowMs = audio.getCurrentTimeMs();
      this._updateViseme(nowMs);
      this._updateCrossfade(dt);
      this._updateBlink();
      this._updateMouthPhysics(0.28);
      this._draw();
      this.rafId = requestAnimationFrame(loop);
    };
    this.lastFrameTime = performance.now();
    this.rafId = requestAnimationFrame(loop);
  }

  /** Stop speech animation loop and reset face to neutral */
  stopAnimation(): void {
    this.currViseme = "neutral";
    this.prevViseme = "neutral";
    this.blendWeight = 1.0;
    this.timeline = [];
    if (this.rafId !== null) {
      cancelAnimationFrame(this.rafId);
    }
    this._startIdleLoop();
  }

  private _updateViseme(nowMs: number): void {
    if (this.timeline.length === 0) {
      if (this.currViseme !== "neutral") {
        this.prevViseme = this.currViseme;
        this.currViseme = "neutral";
        this.blendWeight = 0.0;
      }
      return;
    }
    // Anticipate speech onset by 35ms (coarticulation pre-roll)
    const effectiveTime = nowMs + 35;
    let lo = 0, hi = this.timeline.length - 1, best = 0;
    while (lo <= hi) {
      const mid = (lo + hi) >> 1;
      if (this.timeline[mid].t <= effectiveTime) {
        best = mid;
        lo = mid + 1;
      } else {
        hi = mid - 1;
      }
    }
    const targetShape = this.timeline[best].v || "neutral";
    if (targetShape !== this.currViseme) {
      this.prevViseme = this.currViseme;
      this.currViseme = targetShape;
      this.blendWeight = 0.0;
    }
  }

  private _updateCrossfade(dt: number): void {
    if (this.blendWeight < 1.0) {
      // Smooth 40-50ms whole-face crossfade transition (speed factor ~24)
      this.blendWeight = Math.min(1.0, this.blendWeight + dt * 24.0);
    }
  }

  private _updateMouthPhysics(speed: number): void {
    let targetOpen = 0;
    let targetWidth = 1.0;
    let targetRound = 0.0;
    let targetJaw = 0.0;

    switch (this.currViseme) {
      case "aa":
      case "open":
        targetOpen = 0.88; targetWidth = 1.12; targetRound = 0.0; targetJaw = 4.0; break;
      case "E":
      case "eh":
        targetOpen = 0.75; targetWidth = 1.25; targetRound = 0.0; targetJaw = 3.2; break;
      case "O":
      case "round":
        targetOpen = 0.72; targetWidth = 0.74; targetRound = 0.95; targetJaw = 3.2; break;
      case "U":
        targetOpen = 0.45; targetWidth = 0.62; targetRound = 1.0; targetJaw = 2.0; break;
      case "I":
      case "ih":
        targetOpen = 0.42; targetWidth = 1.22; targetRound = 0.0; targetJaw = 1.8; break;
      case "SS":
      case "DD":
      case "TH":
      case "dental":
      case "kk":
      case "nn":
      case "RR":
        targetOpen = 0.36; targetWidth = 1.16; targetRound = 0.0; targetJaw = 1.6; break;
      case "CH":
        targetOpen = 0.45; targetWidth = 0.95; targetRound = 0.6; targetJaw = 2.0; break;
      case "FF":
      case "labiodental":
        targetOpen = 0.24; targetWidth = 1.04; targetRound = 0.1; targetJaw = 1.0; break;
      case "PP":
      case "bilabial":
        targetOpen = 0.04; targetWidth = 0.96; targetRound = 0.0; targetJaw = 0.2; break;
      case "sil":
      case "neutral":
      default:
        targetOpen = 0.0; targetWidth = 1.0; targetRound = 0.0; targetJaw = 0.0; break;
    }

    this.mouthOpen += (targetOpen - this.mouthOpen) * speed;
    this.mouthWidth += (targetWidth - this.mouthWidth) * speed;
    this.mouthRoundness += (targetRound - this.mouthRoundness) * speed;
    this.jawDrop += (targetJaw - this.jawDrop) * speed;
  }

  private _updateBlink(): void {
    const now = Date.now();
    if (now >= this.nextBlink) {
      if (this.blinkDirection === 1) {
        this.blinkVal += 0.24;
        if (this.blinkVal >= 1.0) {
          this.blinkVal = 1.0;
          this.blinkDirection = -1;
        }
      } else {
        this.blinkVal -= 0.16;
        if (this.blinkVal <= 0.0) {
          this.blinkVal = 0.0;
          this.blinkDirection = 1;
          this.nextBlink = now + 2400 + Math.random() * 3600;
        }
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

    // Natural breathing micro-motion
    const now = Date.now() * 0.0018;
    const breathe = Math.sin(now) * 1.5;

    if (this.isAtlasLoaded && this.visemeAtlasImg) {
      // ── 1. Whole-Face Viseme Stitching & Alpha-Crossfading ──
      const atlas = this.visemeAtlasImg;
      const tileW = atlas.width / 4;
      const tileH = atlas.height / 4;

      const prevGrid = VISEME_GRID[this.prevViseme] || VISEME_GRID.neutral;
      const currGrid = VISEME_GRID[this.currViseme] || VISEME_GRID.neutral;

      ctx.save();

      // Draw Previous Full-Face Frame (Fading Out)
      if (this.blendWeight < 1.0) {
        ctx.globalAlpha = Math.max(0, 1.0 - this.blendWeight);
        const sx = prevGrid.col * tileW;
        const sy = prevGrid.row * tileH;
        ctx.drawImage(atlas, sx, sy, tileW, tileH, 0, breathe, w, h);
      }

      // Draw Current Target Full-Face Frame (Fading In)
      ctx.globalAlpha = Math.min(1.0, this.blendWeight);
      const sx = currGrid.col * tileW;
      const sy = currGrid.row * tileH;
      ctx.drawImage(atlas, sx, sy, tileW, tileH, 0, breathe, w, h);

      ctx.restore();

      // ── 2. Anatomical Eye Blinking on Full Face ──
      const eyeL_X = this.isMale ? w * 0.395 : w * 0.405;
      const eyeR_X = this.isMale ? w * 0.615 : w * 0.605;
      const eyeY = (this.isMale ? h * 0.370 : h * 0.380) + breathe;
      const eyeW = this.isMale ? 26 : 24;
      const eyeH = this.isMale ? 14 : 13;

      if (this.blinkVal > 0.02) {
        this._drawRealisticBlink(ctx, eyeL_X, eyeY, eyeW, eyeH, this.blinkVal, this.isMale);
        this._drawRealisticBlink(ctx, eyeR_X, eyeY, eyeW, eyeH, this.blinkVal, this.isMale);
      }

    } else if (this.isImgLoaded && this.avatarImg) {
      // Fallback: Static Portrait + Procedural Lip-Sync
      ctx.save();
      ctx.drawImage(this.avatarImg, 0, breathe, w, h);
      ctx.restore();

      const eyeL_X = this.isMale ? w * 0.395 : w * 0.405;
      const eyeR_X = this.isMale ? w * 0.615 : w * 0.605;
      const eyeY = (this.isMale ? h * 0.370 : h * 0.380) + breathe;
      const eyeW = this.isMale ? 26 : 24;
      const eyeH = this.isMale ? 14 : 13;

      if (this.blinkVal > 0.02) {
        this._drawRealisticBlink(ctx, eyeL_X, eyeY, eyeW, eyeH, this.blinkVal, this.isMale);
        this._drawRealisticBlink(ctx, eyeR_X, eyeY, eyeW, eyeH, this.blinkVal, this.isMale);
      }

      const mouthX = this.isMale ? w * 0.502 : w * 0.505;
      const mouthY = (this.isMale ? h * 0.655 : h * 0.645) + breathe + (this.jawDrop * 0.5);
      const baseMouthW = this.isMale ? 40 : 36;
      this._drawRealisticMouth(ctx, mouthX, mouthY, baseMouthW, this.isMale);

    } else {
      this._drawProceduralAvatar(ctx, cx, cy + breathe);
    }
  }

  private _drawRealisticBlink(
    ctx: CanvasRenderingContext2D,
    x: number,
    y: number,
    width: number,
    height: number,
    blinkVal: number,
    isMale: boolean
  ): void {
    ctx.save();
    
    // 1. Orbital socket soft ambient shadow
    const shadowGrad = ctx.createRadialGradient(x, y - 2, 2, x, y, width * 0.7);
    shadowGrad.addColorStop(0, "rgba(50, 20, 15, 0.25)");
    shadowGrad.addColorStop(1, "rgba(0, 0, 0, 0)");
    ctx.fillStyle = shadowGrad;
    ctx.beginPath();
    ctx.ellipse(x, y, width * 0.65, height * 0.75, 0, 0, Math.PI * 2);
    ctx.fill();

    // 2. Descending upper eyelid with natural curvature
    const lidDescent = height * 1.05 * blinkVal;
    ctx.beginPath();
    ctx.moveTo(x - width * 0.5, y);
    ctx.quadraticCurveTo(x, y - height * 0.45, x + width * 0.5, y);
    ctx.quadraticCurveTo(x, y - height * 0.45 + lidDescent, x - width * 0.5, y);
    ctx.closePath();

    // Persona-specific skin tone gradient
    const skinGrad = ctx.createLinearGradient(x, y - height * 0.5, x, y + height * 0.5);
    if (isMale) {
      skinGrad.addColorStop(0, "rgba(180, 130, 105, 0.98)");
      skinGrad.addColorStop(0.6, "rgba(195, 145, 120, 0.98)");
      skinGrad.addColorStop(1, "rgba(155, 105, 80, 0.98)");
    } else {
      skinGrad.addColorStop(0, "rgba(215, 165, 145, 0.98)");
      skinGrad.addColorStop(0.6, "rgba(228, 180, 160, 0.98)");
      skinGrad.addColorStop(1, "rgba(185, 135, 115, 0.98)");
    }
    ctx.fillStyle = skinGrad;
    ctx.fill();

    // 3. Eyelid crease / fold line
    ctx.beginPath();
    ctx.moveTo(x - width * 0.42, y - height * 0.25);
    ctx.quadraticCurveTo(x, y - height * 0.5, x + width * 0.42, y - height * 0.25);
    ctx.strokeStyle = isMale ? "rgba(110, 65, 50, 0.4)" : "rgba(140, 85, 70, 0.35)";
    ctx.lineWidth = 1.2;
    ctx.stroke();

    // 4. Curved Eyelash Fringe along the lower edge of the descending lid
    if (blinkVal > 0.3) {
      const lashY = y - height * 0.45 + lidDescent;
      ctx.beginPath();
      ctx.moveTo(x - width * 0.5, y);
      ctx.quadraticCurveTo(x, lashY, x + width * 0.5, y);
      ctx.strokeStyle = isMale ? "rgba(35, 20, 15, 0.85)" : "rgba(25, 12, 10, 0.95)";
      ctx.lineWidth = isMale ? 1.8 : 2.4;
      ctx.stroke();

      if (!isMale && blinkVal > 0.7) {
        ctx.beginPath();
        ctx.moveTo(x + width * 0.4, y);
        ctx.quadraticCurveTo(x + width * 0.55, y - 2, x + width * 0.6, y - 4);
        ctx.stroke();
      }
    }

    // 5. Lower waterline glint / tear film
    if (blinkVal > 0.8) {
      ctx.beginPath();
      ctx.moveTo(x - width * 0.35, y + 1.5);
      ctx.quadraticCurveTo(x, y + 2.5, x + width * 0.35, y + 1.5);
      ctx.strokeStyle = "rgba(255, 255, 255, 0.55)";
      ctx.lineWidth = 0.8;
      ctx.stroke();
    }

    ctx.restore();
  }

  private _drawRealisticMouth(
    ctx: CanvasRenderingContext2D,
    x: number,
    y: number,
    baseW: number,
    isMale: boolean
  ): void {
    const openH = this.mouthOpen * 22;
    const dynamicW = baseW * this.mouthWidth;
    const halfW = dynamicW * 0.5;

    if (this.mouthOpen < 0.03) return;

    ctx.save();

    const faceShadow = ctx.createRadialGradient(x, y + openH * 0.4, halfW * 0.3, x, y + openH * 0.4, halfW * 1.3);
    faceShadow.addColorStop(0, "rgba(40, 15, 15, 0.25)");
    faceShadow.addColorStop(1, "rgba(0, 0, 0, 0)");
    ctx.fillStyle = faceShadow;
    ctx.beginPath();
    ctx.ellipse(x, y + openH * 0.3, halfW * 1.1, openH * 0.8 + 8, 0, 0, Math.PI * 2);
    ctx.fill();

    ctx.beginPath();
    ctx.ellipse(x, y + openH * 0.35, halfW * 0.95, Math.max(2, openH * 0.65), 0, 0, Math.PI * 2);
    const cavityGrad = ctx.createRadialGradient(x, y + openH * 0.3, 1, x, y + openH * 0.35, halfW);
    cavityGrad.addColorStop(0, "#1a0508");
    cavityGrad.addColorStop(0.65, "#3b0c14");
    cavityGrad.addColorStop(1, "#5a1822");
    ctx.fillStyle = cavityGrad;
    ctx.fill();

    if (this.mouthOpen > 0.22) {
      const tongueLift = (1 - this.mouthRoundness) * (this.mouthOpen * 6);
      const tongueY = y + openH * 0.45 + tongueLift * 0.3;
      ctx.beginPath();
      ctx.ellipse(x, tongueY, halfW * 0.62, Math.max(3, openH * 0.35), 0, 0, Math.PI);
      const tongueGrad = ctx.createRadialGradient(x, tongueY - 2, 2, x, tongueY, halfW * 0.6);
      tongueGrad.addColorStop(0, "#d94860");
      tongueGrad.addColorStop(0.7, "#be123c");
      tongueGrad.addColorStop(1, "#881337");
      ctx.fillStyle = tongueGrad;
      ctx.fill();
    }

    if (this.mouthOpen > 0.12) {
      const teethH = Math.min(6, openH * 0.38);
      const teethW = halfW * 0.78;
      ctx.beginPath();
      ctx.moveTo(x - teethW, y - 1);
      ctx.quadraticCurveTo(x, y - teethH * 0.3, x + teethW, y - 1);
      ctx.lineTo(x + teethW * 0.85, y + teethH);
      ctx.quadraticCurveTo(x, y + teethH + 0.8, x - teethW * 0.85, y + teethH);
      ctx.closePath();
      ctx.fillStyle = "rgba(245, 243, 240, 0.96)";
      ctx.fill();
    }

    const upperLift = openH * 0.25;
    ctx.beginPath();
    ctx.moveTo(x - halfW - 2, y);
    ctx.bezierCurveTo(x - halfW * 0.45, y - upperLift - 3.5, x - halfW * 0.15, y - upperLift - 3.5, x, y - upperLift - 1.5);
    ctx.bezierCurveTo(x + halfW * 0.15, y - upperLift - 3.5, x + halfW * 0.45, y - upperLift - 3.5, x + halfW + 2, y);
    ctx.quadraticCurveTo(x, y - upperLift * 0.3, x - halfW - 2, y);
    ctx.closePath();
    ctx.fillStyle = isMale ? "rgba(145, 80, 70, 0.94)" : "rgba(175, 75, 85, 0.96)";
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
    this._drawRealisticMouth(ctx, cx, cy + 45, 36, false);
  }

  destroy(): void {
    this.stopAnimation();
    if (this.rafId !== null) cancelAnimationFrame(this.rafId);
    this.canvas.remove();
  }
}
