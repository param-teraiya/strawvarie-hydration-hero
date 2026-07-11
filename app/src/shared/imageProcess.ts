// Turn a customer's imported character image into a clean, transparent,
// centered sprite — entirely in the browser engine (no server, fully offline).
//
// Steps: draw the image to a canvas, remove the (solid) background by sampling
// the corners, crop to the character, and rescale to a standard height. Returns
// a PNG data URL ready to store and animate.

function fileToImage(file: File): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      URL.revokeObjectURL(url);
      resolve(img);
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("That file could not be read as an image."));
    };
    img.src = url;
  });
}

/** Zero-out pixels close to the background colour (sampled from the corners). */
function removeBackground(img: ImageData): void {
  const { data, width, height } = img;
  const corners = [
    [0, 0],
    [width - 1, 0],
    [0, height - 1],
    [width - 1, height - 1],
  ].map(([x, y]) => {
    const i = (y * width + x) * 4;
    return [data[i], data[i + 1], data[i + 2]];
  });
  const bg = [0, 1, 2].map((k) =>
    Math.round(corners.reduce((sum, c) => sum + c[k], 0) / corners.length),
  );

  const HARD = 66; // fully transparent below this colour distance
  const SOFT = 34; // feathered edge above it, to avoid a hard halo
  for (let i = 0; i < data.length; i += 4) {
    const dr = data[i] - bg[0];
    const dg = data[i + 1] - bg[1];
    const db = data[i + 2] - bg[2];
    const dist = Math.sqrt(dr * dr + dg * dg + db * db);
    if (dist < HARD) {
      data[i + 3] = 0;
    } else if (dist < HARD + SOFT) {
      data[i + 3] = Math.round(data[i + 3] * ((dist - HARD) / SOFT));
    }
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
  const img = await fileToImage(file);

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
  removeBackground(data);
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
