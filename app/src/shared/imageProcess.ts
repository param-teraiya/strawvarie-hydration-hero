// Turn a customer's imported character image into a clean, transparent,
// centered sprite — entirely in the browser engine (no server, fully offline).
//
// Steps: draw the image to a canvas, remove the (solid) background by sampling
// the corners, crop to the character, and rescale to a standard height. Returns
// a PNG data URL ready to store and animate.

function urlToImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error("That file could not be read as an image."));
    img.src = url;
  });
}

function fileToImage(file: File): Promise<HTMLImageElement> {
  const url = URL.createObjectURL(file);
  return urlToImage(url).finally(() => URL.revokeObjectURL(url));
}

/** True if the image already has its own transparent background (e.g. a PNG
 *  exported with alpha) — in which case we must NOT chroma-key it, or we'd
 *  erase the character's dark pixels. */
function alreadyTransparent(img: ImageData): boolean {
  const { data, width, height } = img;
  const corners = [
    [0, 0],
    [width - 1, 0],
    [0, height - 1],
    [width - 1, height - 1],
  ];
  let clear = 0;
  for (const [x, y] of corners) {
    if (data[(y * width + x) * 4 + 3] < 32) clear += 1;
  }
  return clear >= 3;
}

/** Remove the background by flood-filling inward from the edges. Only pixels
 *  that are the background colour AND connected to the border are cleared — so
 *  an interior face that happens to match the background (e.g. skin on a beige
 *  backdrop) survives, unlike a naive "remove every matching pixel" pass. */
function removeBackground(img: ImageData): void {
  const { data, width: w, height: h } = img;
  const corners = [
    [0, 0],
    [w - 1, 0],
    [0, h - 1],
    [w - 1, h - 1],
  ];
  const bg = [0, 1, 2].map((k) =>
    Math.round(corners.reduce((sum, [x, y]) => sum + data[(y * w + x) * 4 + k], 0) / 4),
  );

  const TOL = 110 * 110; // squared colour distance that still counts as background
  const near = (idx: number) => {
    const o = idx * 4;
    const dr = data[o] - bg[0];
    const dg = data[o + 1] - bg[1];
    const db = data[o + 2] - bg[2];
    return dr * dr + dg * dg + db * db < TOL;
  };

  const visited = new Uint8Array(w * h);
  const stack: number[] = [];
  const seed = (idx: number) => {
    if (!visited[idx] && near(idx)) {
      visited[idx] = 1;
      stack.push(idx);
    }
  };
  for (let x = 0; x < w; x++) {
    seed(x);
    seed((h - 1) * w + x);
  }
  for (let y = 0; y < h; y++) {
    seed(y * w);
    seed(y * w + w - 1);
  }
  while (stack.length) {
    const idx = stack.pop()!;
    data[idx * 4 + 3] = 0;
    const x = idx % w;
    const y = (idx - x) / w;
    if (x > 0) seed(idx - 1);
    if (x < w - 1) seed(idx + 1);
    if (y > 0) seed(idx - w);
    if (y < h - 1) seed(idx + w);
  }
}

/** Bounding box of pixels that are meaningfully opaque. */
function opaqueBounds(img: ImageData) {
  const { data, width, height } = img;
  let x0 = width,
    y0 = height,
    x1 = 0,
    y1 = 0,
    found = false;
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      if (data[(y * width + x) * 4 + 3] > 24) {
        found = true;
        if (x < x0) x0 = x;
        if (x > x1) x1 = x;
        if (y < y0) y0 = y;
        if (y > y1) y1 = y;
      }
    }
  }
  if (!found) return { x0: 0, y0: 0, x1: width - 1, y1: height - 1 };
  return { x0, y0, x1, y1 };
}

const TARGET_HEIGHT = 184;

export async function processCharacterImage(file: File): Promise<string> {
  return processImage(await fileToImage(file));
}

export async function processCharacterImageFromDataUrl(dataUrl: string): Promise<string> {
  return processImage(await urlToImage(dataUrl));
}

async function processImage(img: HTMLImageElement): Promise<string> {
  // Work at a modest resolution for speed.
  const maxSide = 512;
  const scale = Math.min(1, maxSide / Math.max(img.width, img.height));
  const w = Math.max(1, Math.round(img.width * scale));
  const h = Math.max(1, Math.round(img.height * scale));

  const work = document.createElement("canvas");
  work.width = w;
  work.height = h;
  const wctx = work.getContext("2d", { willReadFrequently: true })!;
  wctx.drawImage(img, 0, 0, w, h);

  const data = wctx.getImageData(0, 0, w, h);
  // Only chroma-key a solid background. If the image is already transparent,
  // keep its alpha as-is (removing it would eat dark parts of the character).
  if (!alreadyTransparent(data)) {
    removeBackground(data);
  }
  wctx.putImageData(data, 0, 0);

  const b = opaqueBounds(data);
  const cropW = b.x1 - b.x0 + 1;
  const cropH = b.y1 - b.y0 + 1;
  if (cropW < 4 || cropH < 4) {
    // Couldn't find a subject; return the background-removed image as-is.
    return work.toDataURL("image/png");
  }

  const s = TARGET_HEIGHT / cropH;
  const outW = Math.max(1, Math.round(cropW * s));
  const out = document.createElement("canvas");
  out.width = outW;
  out.height = TARGET_HEIGHT;
  const octx = out.getContext("2d")!;
  octx.imageSmoothingEnabled = true;
  octx.imageSmoothingQuality = "high";
  octx.drawImage(work, b.x0, b.y0, cropW, cropH, 0, 0, outW, TARGET_HEIGHT);
  return out.toDataURL("image/png");
}
