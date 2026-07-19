// A tiny sprite engine. It draws one animation state from a character's atlas
// onto a <canvas>, advancing frames on requestAnimationFrame. Horizontal
// movement (walking across the screen) is done by the caller via CSS transform
// — this engine only cycles frames.
//
// It respects prefers-reduced-motion: when set, it draws a single still pose
// instead of animating, and reports completion immediately.

interface CharState {
  row: number;
  frames: number;
  fps: number;
  loop: boolean;
}

export interface Manifest {
  schema: number;
  id: string;
  name: string;
  blurb: string;
  frameWidth: number;
  frameHeight: number;
  anchorX: number;
  anchorY: number;
  states: Record<string, CharState>;
  poster: { state: string; index: number };
}

function loadImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error(`failed to load ${url}`));
    img.src = url;
  });
}

export class Sprite {
  private ctx: CanvasRenderingContext2D;
  private atlas: HTMLImageElement | null = null;
  private manifest: Manifest | null = null;
  private raf = 0;
  private idx = 0;
  private acc = 0;
  private last = 0;
  // "atlas" = a built-in with a sprite sheet; "procedural" = a single imported
  // image animated with canvas transforms (the customer's own buddy).
  private mode: "atlas" | "procedural" = "atlas";
  private procImage: HTMLImageElement | null = null;
  // Optional second pose (tumbler raised) for a real drink animation.
  private procDrinkImage: HTMLImageElement | null = null;
  private procId = "";
  readonly reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  constructor(private canvas: HTMLCanvasElement) {
    this.ctx = canvas.getContext("2d")!;
  }

  get loaded() {
    return this.mode === "procedural" ? this.procImage !== null : this.manifest !== null;
  }

  get id() {
    return this.mode === "procedural" ? this.procId : (this.manifest?.id ?? "");
  }

  async load(dir: string): Promise<void> {
    this.mode = "atlas";
    const manifest: Manifest = await fetch(`${dir}/manifest.json`).then((r) => r.json());
    this.manifest = manifest;
    this.canvas.width = manifest.frameWidth;
    this.canvas.height = manifest.frameHeight;
    this.ctx.imageSmoothingEnabled = false;
    this.atlas = await loadImage(`${dir}/atlas.png`);
    this.drawFrame(manifest.poster.state, manifest.poster.index);
  }

  private drawFrame(state: string, index: number): void {
    if (!this.manifest || !this.atlas) return;
    const st = this.manifest.states[state];
    if (!st) return;
    const { frameWidth: fw, frameHeight: fh } = this.manifest;
    this.ctx.clearRect(0, 0, fw, fh);
    this.ctx.drawImage(this.atlas, index * fw, st.row * fh, fw, fh, 0, 0, fw, fh);
  }

  /**
   * Load an imported custom buddy. `dataUrl` is the standing pose; the optional
   * `drinkDataUrl` is a second "sipping" pose (tumbler raised) — when supplied,
   * the drink animation swaps to it instead of faking a lean-and-lift.
   */
  async loadProcedural(dataUrl: string, drinkDataUrl?: string | null): Promise<void> {
    this.mode = "procedural";
    this.procId = "custom";
    this.canvas.width = 160;
    this.canvas.height = 192;
    this.ctx.imageSmoothingEnabled = true;
    this.procImage = await loadImage(dataUrl);
    this.procDrinkImage = drinkDataUrl ? await loadImage(drinkDataUrl) : null;
    this.drawProc("idle", 0);
  }

  /** Play an animation state. Resolves onComplete when a non-looping state ends. */
  play(state: string, opts: { loop?: boolean; onComplete?: () => void } = {}): void {
    if (this.mode === "procedural") {
      this.playProc(state, opts);
      return;
    }
    cancelAnimationFrame(this.raf);
    if (!this.manifest) return;
    const st = this.manifest.states[state];
    if (!st) {
      opts.onComplete?.();
      return;
    }
    const loop = opts.loop ?? st.loop;

    if (this.reduceMotion) {
      // Show the final, most legible pose and finish at once.
      this.drawFrame(state, st.frames - 1);
      if (!loop) opts.onComplete?.();
      return;
    }

    this.idx = 0;
    this.acc = 0;
    this.last = performance.now();
    this.drawFrame(state, 0);
    const frameMs = 1000 / st.fps;

    const step = (t: number) => {
      const dt = t - this.last;
      this.last = t;
      this.acc += dt;
      if (this.acc >= frameMs) {
        this.acc = 0;
        this.idx += 1;
        if (this.idx >= st.frames) {
          if (loop) {
            this.idx = 0;
          } else {
            this.drawFrame(state, st.frames - 1);
            opts.onComplete?.();
            return;
          }
        }
        this.drawFrame(state, this.idx);
      }
      this.raf = requestAnimationFrame(step);
    };
    this.raf = requestAnimationFrame(step);
  }

  // --- procedural (custom buddy) animation --------------------------------
  private playProc(state: string, opts: { onComplete?: () => void }): void {
    cancelAnimationFrame(this.raf);
    const looping = state === "idle" || state === "walk";
    if (this.reduceMotion) {
      this.drawProc(state, 999);
      if (!looping) opts.onComplete?.();
      return;
    }
    const start = performance.now();
    const step = (t: number) => {
      const el = (t - start) / 1000;
      this.drawProc(state, el);
      if (!looping && el > 1.0) {
        opts.onComplete?.();
        return;
      }
      this.raf = requestAnimationFrame(step);
    };
    this.raf = requestAnimationFrame(step);
  }

  private drawProc(state: string, el: number): void {
    const img = this.procImage;
    if (!img) return;
    const ctx = this.ctx;
    const cw = this.canvas.width;
    const ch = this.canvas.height;
    ctx.clearRect(0, 0, cw, ch);

    // Both poses are drawn at the SAME scale and feet baseline so they line up
    // when we swap. When a second pose exists we reserve headroom for the raised
    // arm; the scale is always derived from the standing pose for consistency.
    const pad = 8;
    const hasTwo = this.procDrinkImage !== null;
    const heightBudget = hasTwo ? ch - pad - 22 : ch - pad;
    const scale = Math.min((cw - pad * 2) / img.width, heightBudget / img.height);

    // Real two-pose drink: cross-fade the standing pose into the raised-tumbler
    // pose (reads as lifting the cup), hold the sip, then fade back.
    if (state === "drink" && this.procDrinkImage) {
      const raised = this.procDrinkImage;
      let alphaB = 1;
      let bob = -4;
      if (!this.reduceMotion) {
        if (el < 0.18) {
          alphaB = ease(el / 0.18); // lift
          bob = -4 * alphaB;
        } else if (el > 0.8) {
          alphaB = ease(Math.max(0, (1 - el) / 0.2)); // lower
          bob = -4 * alphaB;
        } else {
          bob = -4 + Math.sin(el * 8) * 1.2; // sip
        }
      }
      if (alphaB < 1) this.paintProc(img, scale, bob * 0.5, 0, 1);
      this.paintProc(raised, scale, bob, 0, alphaB);
      return;
    }

    // idle / walk, and the single-image drink fallback (lean-and-lift, no swap).
    let bob = 0;
    let rot = 0;
    if (!this.reduceMotion) {
      if (state === "idle") {
        bob = Math.sin(el * 3) * 3;
      } else if (state === "walk") {
        bob = -Math.abs(Math.sin(el * 10)) * 4;
        rot = Math.sin(el * 10) * 0.05;
      } else if (state === "drink") {
        const p = ease(Math.min(1, el / 0.5));
        rot = -0.2 * p;
        bob = -4 * p;
      }
    } else if (state === "drink") {
      rot = -0.2;
      bob = -4;
    }
    this.paintProc(img, scale, bob, rot, 1);
  }

  /** Draw one procedural pose anchored at the feet (bottom-centre). */
  private paintProc(
    image: HTMLImageElement,
    scale: number,
    bob: number,
    rot: number,
    alpha: number,
  ): void {
    const ctx = this.ctx;
    const dw = image.width * scale;
    const dh = image.height * scale;
    ctx.save();
    ctx.globalAlpha = alpha;
    ctx.translate(this.canvas.width / 2, this.canvas.height - 2 + bob);
    ctx.rotate(rot);
    ctx.drawImage(image, -dw / 2, -dh, dw, dh);
    ctx.restore();
  }

  stop(): void {
    cancelAnimationFrame(this.raf);
  }
}

function ease(p: number): number {
  return p * p * (3 - 2 * p);
}
