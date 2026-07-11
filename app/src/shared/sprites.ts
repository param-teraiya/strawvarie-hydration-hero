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
  readonly reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  constructor(private canvas: HTMLCanvasElement) {
    this.ctx = canvas.getContext("2d")!;
  }

  get loaded() {
    return this.manifest !== null && this.atlas !== null;
  }

  get id() {
    return this.manifest?.id ?? "";
  }

  async load(dir: string): Promise<void> {
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

  /** Play an animation state. Resolves onComplete when a non-looping state ends. */
  play(state: string, opts: { loop?: boolean; onComplete?: () => void } = {}): void {
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

  stop(): void {
    cancelAnimationFrame(this.raf);
  }
}
