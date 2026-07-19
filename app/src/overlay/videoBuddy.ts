// Plays a customer's green-screen animation clip in the overlay, keying out the
// green background in real time and keeping the character centred + feet-anchored
// so the walk/drink motion reads clearly at a small size — even though the source
// character walks across a wide frame.
//
// Everything runs on a <canvas>: draw the current video frame to a small work
// buffer, drop green pixels to transparent, find the character's bounding box,
// then blit that box (scaled, feet to the bottom) onto the visible canvas.

const WORK_W = 256; // work-buffer width; height derives from the video aspect

/**
 * Convert a `data:video/...;base64,...` URL into a same-origin blob URL. Drawing
 * a video loaded from a data: URL taints the canvas (getImageData throws), which
 * would kill the chroma key; a blob URL does not.
 */
function toBlobUrl(url: string): string {
  if (!url.startsWith("data:")) return url;
  const comma = url.indexOf(",");
  const mime = url.slice(5, url.indexOf(";")) || "video/mp4";
  const bin = atob(url.slice(comma + 1));
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return URL.createObjectURL(new Blob([bytes], { type: mime }));
}

export class VideoBuddy {
  private video: HTMLVideoElement;
  private work: HTMLCanvasElement;
  private wctx: CanvasRenderingContext2D;
  private ctx: CanvasRenderingContext2D;
  private raf = 0;
  private blobUrl: string | null = null;
  private onEnded: (() => void) | null = null;
  // Smoothed character box (in work-buffer pixels) to avoid per-frame jitter.
  private box = { x: 0, y: 0, w: WORK_W, h: WORK_W, ready: false };
  // Snapshot of the last frame where the character was centred and standing.
  // We freeze on this instead of the literal last frame, so a clip that ends by
  // walking off-screen still holds a standing pose (belt-and-suspenders for the
  // "ends standing" prompt guidance).
  private lastGood: HTMLCanvasElement;
  private lgctx: CanvasRenderingContext2D;
  private hasLastGood = false;
  // Entrance/pause/resume: play walk-in, auto-pause when the character arrives
  // and stands, then resume (sip + walk-out) when the user acts.
  private detectingArrival = false;
  private arrivalHist: { t: number; x: number }[] = [];
  private arriveFallback = 0;

  constructor(private canvas: HTMLCanvasElement) {
    this.ctx = canvas.getContext("2d")!;
    this.video = document.createElement("video");
    this.video.muted = true;
    this.video.playsInline = true;
    this.video.preload = "auto";
    // WKWebView will not load/play a <video> that isn't in the document, so keep
    // it attached but effectively invisible.
    this.video.style.cssText =
      "position:fixed;top:0;left:0;width:2px;height:2px;opacity:0;pointer-events:none;";
    document.body.appendChild(this.video);
    this.work = document.createElement("canvas");
    this.wctx = this.work.getContext("2d", { willReadFrequently: true })!;
    this.lastGood = document.createElement("canvas");
    this.lgctx = this.lastGood.getContext("2d")!;
  }

  /** Load a clip (data URL). Resolves once a frame can be drawn. */
  load(dataUrl: string): Promise<void> {
    return new Promise((resolve, reject) => {
      const v = this.video;
      let done = false;
      const onReady = () => {
        if (done) return;
        done = true;
        const vw = v.videoWidth || 16;
        const vh = v.videoHeight || 9;
        this.work.width = WORK_W;
        this.work.height = Math.max(1, Math.round((WORK_W * vh) / vw));
        this.box = { x: 0, y: 0, w: this.work.width, h: this.work.height, ready: false };
        this.hasLastGood = false;
        v.removeEventListener("loadeddata", onReady);
        resolve();
      };
      v.addEventListener("loadeddata", onReady);
      v.addEventListener("error", () => {
        if (!done) {
          done = true;
          reject(new Error("video load failed"));
        }
      });
      // Never hang the overlay: if metadata is slow, bail so the caller can fall
      // back to the still buddy.
      setTimeout(() => {
        if (!done) {
          done = true;
          reject(new Error("video load timed out"));
        }
      }, 5000);
      if (this.blobUrl) URL.revokeObjectURL(this.blobUrl);
      this.blobUrl = toBlobUrl(dataUrl);
      v.src = this.blobUrl;
      v.load();
    });
  }

  /**
   * Play once from the start, then FREEZE on the final frame (the character
   * standing) and hold it — the buddy waits on screen until dismissed. `onEnded`
   * fires after it freezes (the create-screen preview uses it to loop).
   */
  play(onEnded?: () => void): void {
    this.onEnded = onEnded ?? null;
    this.detectingArrival = false;
    cancelAnimationFrame(this.raf);
    const v = this.video;
    v.currentTime = 0;
    v.loop = false;
    v.onended = () => this.freezeEnd();
    void v.play().catch(() => {
      /* if autoplay is blocked we still draw the poster frame */
    });
    this.loop();
  }

  /**
   * Reminder entrance: play from the start and AUTO-PAUSE once the character has
   * walked in and is standing still (centre stops moving). It then waits until
   * `playRest()` resumes it. Use this instead of `play()` in the overlay.
   */
  playEntrance(): void {
    this.onEnded = null;
    cancelAnimationFrame(this.raf);
    clearTimeout(this.arriveFallback);
    const v = this.video;
    v.currentTime = 0;
    v.loop = false;
    v.onended = () => this.freezeEnd(); // if there's no walk-out beat, just hold
    this.detectingArrival = true;
    this.arrivalHist = [];
    void v.play().catch(() => {});
    // Safety: if we never detect an arrival (e.g. the character starts centred),
    // pause partway through so it doesn't play the whole thing.
    const capMs = Math.min((v.duration || 6) * 1000 * 0.6, 4500);
    this.arriveFallback = window.setTimeout(() => this.pauseAtStand(), capMs);
    this.loop();
  }

  /** Freeze the buddy at the arrived-standing point (called from render()). */
  private pauseAtStand(): void {
    if (!this.detectingArrival) return;
    this.detectingArrival = false;
    clearTimeout(this.arriveFallback);
    cancelAnimationFrame(this.raf);
    this.raf = 0;
    try {
      this.video.pause();
    } catch {
      /* ignore */
    }
  }

  /** Resume from the paused standing pose through to the end (sip → walk out). */
  playRest(onEnded?: () => void): void {
    this.onEnded = onEnded ?? null;
    this.detectingArrival = false;
    const v = this.video;
    v.onended = () => this.freezeEnd();
    void v.play().catch(() => {});
    this.loop();
  }

  private loop(): void {
    const tick = () => {
      this.render();
      this.raf = requestAnimationFrame(tick);
    };
    this.raf = requestAnimationFrame(tick);
  }

  /** Draw the final frame, preferring the last standing snapshot, then stop and
   *  fire the onEnded callback once (used by preview looping and resume-then-fade). */
  private freezeEnd(): void {
    this.render();
    if (this.hasLastGood) {
      this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
      this.ctx.drawImage(this.lastGood, 0, 0);
    }
    cancelAnimationFrame(this.raf);
    this.raf = 0;
    const cb = this.onEnded;
    this.onEnded = null;
    cb?.();
  }

  stop(): void {
    this.detectingArrival = false;
    clearTimeout(this.arriveFallback);
    cancelAnimationFrame(this.raf);
    this.raf = 0;
    this.onEnded = null;
    this.video.onended = null;
    try {
      this.video.pause();
    } catch {
      /* ignore */
    }
  }

  /** Draw one keyed, tracked frame to the visible canvas. */
  private render(): void {
    const v = this.video;
    if (v.readyState < 2) return; // no frame yet
    const ww = this.work.width;
    const wh = this.work.height;
    this.wctx.drawImage(v, 0, 0, ww, wh);

    let img: ImageData;
    try {
      img = this.wctx.getImageData(0, 0, ww, wh);
    } catch {
      return; // e.g. not-yet-decodable frame
    }
    const d = img.data;

    // Key out green + find the character's bounding box in one pass.
    let minX = ww;
    let minY = wh;
    let maxX = 0;
    let maxY = 0;
    for (let i = 0, p = 0; i < d.length; i += 4, p++) {
      const r = d[i];
      const g = d[i + 1];
      const b = d[i + 2];
      // Green screen: green clearly dominates red and blue.
      if (g > 90 && g > r * 1.3 && g > b * 1.3) {
        d[i + 3] = 0;
        continue;
      }
      // Spill suppression: pull lingering green on the edges toward grey.
      if (g > r && g > b) {
        const cap = Math.max(r, b);
        d[i + 1] = (g + cap) >> 1;
      }
      const x = p % ww;
      const y = (p / ww) | 0;
      if (x < minX) minX = x;
      if (x > maxX) maxX = x;
      if (y < minY) minY = y;
      if (y > maxY) maxY = y;
    }
    this.wctx.putImageData(img, 0, 0);

    // If we found a character, smooth its box; otherwise keep the last one.
    if (maxX >= minX && maxY >= minY) {
      const pad = 3;
      const nx = Math.max(0, minX - pad);
      const ny = Math.max(0, minY - pad);
      const nw = Math.min(ww, maxX + pad) - nx;
      const nh = Math.min(wh, maxY + pad) - ny;
      if (!this.box.ready) {
        this.box = { x: nx, y: ny, w: nw, h: nh, ready: true };
      } else {
        const s = 0.35; // easing toward the new box
        this.box.x += (nx - this.box.x) * s;
        this.box.y += (ny - this.box.y) * s;
        this.box.w += (nw - this.box.w) * s;
        this.box.h += (nh - this.box.h) * s;
      }
    }

    // Entrance auto-pause: once the character's horizontal centre stops moving
    // (finished walking in), freeze on the standing pose and wait for the user.
    if (this.detectingArrival && this.box.ready) {
      const now = performance.now();
      const cx = this.box.x + this.box.w / 2;
      this.arrivalHist.push({ t: now, x: cx });
      while (this.arrivalHist.length && now - this.arrivalHist[0].t > 350) {
        this.arrivalHist.shift();
      }
      const span = now - this.arrivalHist[0].t;
      if (span >= 300 && v.currentTime > 0.7) {
        let lo = Infinity;
        let hi = -Infinity;
        for (const s of this.arrivalHist) {
          if (s.x < lo) lo = s.x;
          if (s.x > hi) hi = s.x;
        }
        if (hi - lo < 5) this.pauseAtStand(); // centre steady → arrived
      }
    }

    // Blit the character box onto the visible canvas: fit by height, centred,
    // feet anchored near the bottom.
    const cw = this.canvas.width;
    const ch = this.canvas.height;
    this.ctx.clearRect(0, 0, cw, ch);
    const b = this.box;
    if (b.w < 1 || b.h < 1) return;
    const scale = Math.min((cw - 8) / b.w, (ch - 6) / b.h);
    const dw = b.w * scale;
    const dh = b.h * scale;
    const dx = (cw - dw) / 2;
    const dy = ch - dh - 2;
    this.ctx.drawImage(this.work, b.x, b.y, b.w, b.h, dx, dy, dw, dh);

    // Snapshot this frame if the character is well-centred and substantial (i.e.
    // standing, not entering/exiting) — this becomes the freeze pose on clip end.
    if (maxX >= minX) {
      const rawH = maxY - minY;
      const rawCx = (minX + maxX) / 2;
      const centred = Math.abs(rawCx - ww / 2) < ww * 0.22;
      if (rawH > wh * 0.5 && centred) {
        if (this.lastGood.width !== cw || this.lastGood.height !== ch) {
          this.lastGood.width = cw;
          this.lastGood.height = ch;
        }
        this.lgctx.clearRect(0, 0, cw, ch);
        this.lgctx.drawImage(this.canvas, 0, 0);
        this.hasLastGood = true;
      }
    }
  }
}
