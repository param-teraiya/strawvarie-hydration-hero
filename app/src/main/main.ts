// The main window: first-run onboarding, settings, and about. There is no
// dashboard — this app is reminders only, so this window is small and quiet.
import { getCurrentWindow } from "@tauri-apps/api/window";
import { getVersion } from "@tauri-apps/api/app";
import { openUrl } from "@tauri-apps/plugin-opener";
import { open } from "@tauri-apps/plugin-dialog";
import "../shared/theme.css";
import "./main.css";
import { Sprite } from "../shared/sprites";
import { VideoBuddy } from "../overlay/videoBuddy";
import { applyTheme } from "../shared/theme";
import { CHARACTERS, characterDir } from "../shared/characters";
import { processCharacterImageFromDataUrl } from "../shared/imageProcess";
import {
  getCustomCharacter,
  getSettings,
  listen,
  readImageAsDataUrl,
  readVideoAsDataUrl,
  remindNow,
  saveCustomCharacter,
  saveSettings,
  type Settings,
} from "../shared/ipc";

const SHOP_URL = "https://strawvarie.in";
const RELEASES_URL =
  "https://github.com/param-teraiya/strawvarie-hydration-hero/releases/latest";
const GEMINI_URL = "https://gemini.google.com/app";
const INTERVAL_PRESETS = [30, 60, 120];
const LOGIN_HELP =
  "When this is on, Hydration Hero starts automatically every time you turn on your " +
  "computer and waits quietly in the menu bar at the top of the screen. You won't need " +
  "to open it yourself. Turn it off if you'd rather open the app manually.";
// The Strawvarie tumbler, described so the AI draws the real product: a lilac
// Stanley-Quencher-style cup with a side handle and a straw.
const TUMBLER =
  "a lilac / soft-lavender matte stainless-steel Strawvarie tumbler with a large " +
  "curved side handle and a straw poking out of the lid (Stanley-Quencher style)";

// Pose 1: the standing character, tumbler held by the handle at one side.
const GEMINI_PROMPT_STAND =
  "Turn the person in this photo into a cute full-body pixel-art character, " +
  "16-bit retro game style, standing and facing forward, full body from head to feet, " +
  "holding " +
  TUMBLER +
  " by the handle in one hand, down at one side, " +
  "centered with a little space above the head, " +
  "on a solid flat bright green background (hex #00FF00), no shadows, no text.";

// Image-to-video prompt: the animated buddy. Fed to a tool like Gemini/Veo,
// Runway, or Kling along with the character image. The solid green background is
// what lets the app key it out and float the character in the reminder card.
const CLIP_PROMPT =
  "Animate this image as a lively, dimensional pixel-art character with soft " +
  "directional lighting, subtle shading and a sense of weight so it feels 3D and alive. " +
  "It is holding " +
  TUMBLER +
  ". Follow this exact order: (1) it walks in from the side holding the tumbler by the " +
  "handle; (2) it reaches the centre and stands still facing forward for about a second; " +
  "(3) it raises the tumbler toward the viewer in a friendly 'cheers' toast; (4) it takes " +
  "a sip through the straw; (5) it lowers the tumbler; (6) it turns and walks back out of " +
  "frame. IMPORTANT: keep the tumbler in the SAME hand the entire time — never switch hands " +
  "or pass it between hands, and keep the tumbler's shape and colour identical throughout. " +
  "Add a soft contact shadow directly under the feet so it looks grounded. The ONLY " +
  "background is a solid flat bright green (hex #00FF00) filling the entire frame — no " +
  "floor, no scenery, no text (the app removes the green).";

// Pose 2 (still-image fallback): the SAME character mid-sip. Run it right after
// pose 1 in the same chat so Gemini keeps the character consistent.
const GEMINI_PROMPT_SIP =
  "Now make a second image of the exact same character, keeping everything " +
  "identical — same body, same colours, same size, same position and framing, and the " +
  "tumbler in the SAME hand — but raising the tumbler to take a sip through the straw. " +
  "Only the arm and tumbler move. Same solid flat bright green background (hex #00FF00), " +
  "no shadows, no text.";

const DROP_SVG = `<svg class="drop" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2C12 2 4 11 4 16a8 8 0 0 0 16 0C20 11 12 2 12 2Z" fill="var(--accent)"/></svg>`;

let settings: Settings;
let view: "onboarding" | "settings" | "about" | "create" = "settings";
let createReturn: "onboarding" | "settings" = "settings";
let step = 0;
let pickers: Sprite[] = [];
let createVideoBuddy: VideoBuddy | null = null;

// 1×1 transparent PNG — poster fallback if we can't key a frame from the clip.
const TRANSPARENT_PX =
  "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M8AAAMBAQDJ/pLvAAAAAElFTkSuQmCC";

function openCreate() {
  createReturn = view === "onboarding" ? "onboarding" : "settings";
  view = "create";
  render();
}

const app = document.getElementById("app")!;

/** Show a readable error instead of a blank screen if startup fails. */
function showFatal(message: string) {
  app.innerHTML = `<div style="padding:26px;font-family:sans-serif;line-height:1.5">
    <h2 style="margin:0 0 8px;font-size:17px;color:#28282b">Hydration Hero couldn't start</h2>
    <p style="margin:0 0 12px;color:#86867e;font-size:13px">Please send this to support:</p>
    <pre style="white-space:pre-wrap;word-break:break-word;font-size:12px;color:#b25b53;background:#f6f6f4;padding:12px;border-radius:8px">${String(message).replace(/[<>&]/g, "")}</pre>
  </div>`;
}
window.addEventListener("error", (e) => showFatal(e.message || String(e.error)));
window.addEventListener("unhandledrejection", (e) => showFatal(`Unhandled: ${String(e.reason)}`));

async function boot() {
  try {
    setupTooltips();
    settings = await getSettings();
    applyTheme(settings.theme);
    view = settings.onboarding_complete ? "settings" : "onboarding";
    render();
    listen<string>("navigate", (e) => {
      view = e.payload === "about" ? "about" : "settings";
      render();
    });
  } catch (e) {
    showFatal(String(e));
  }
}

/** Update one or more settings and persist immediately (live-apply). */
async function update(partial: Partial<Settings>) {
  settings = { ...settings, ...partial };
  applyTheme(settings.theme);
  await saveSettings(settings);
}

function stopPickers() {
  pickers.forEach((s) => s.stop());
  pickers = [];
  createVideoBuddy?.stop();
  createVideoBuddy = null;
}

function render() {
  stopPickers();
  app.innerHTML = "";
  if (view === "onboarding") renderOnboarding();
  else if (view === "about") renderAbout();
  else if (view === "create") renderCreate();
  else renderSettings();
}

// --- reusable character picker ---------------------------------------------
function selectCard(grid: HTMLElement, card: HTMLElement, id: string, onPick: (id: string) => void) {
  grid.querySelectorAll(".char-card").forEach((n) => n.classList.remove("selected"));
  card.classList.add("selected");
  onPick(id);
}

function buildPicker(onPick: (id: string) => void, onCreate: () => void): HTMLElement {
  const grid = document.createElement("div");
  grid.className = "char-grid";

  const addSpriteCard = (id: string, name: string, load: (s: Sprite) => Promise<void>) => {
    const card = document.createElement("button");
    card.className = "char-card" + (id === settings.character_id ? " selected" : "");
    card.innerHTML = `<canvas class="sprite"></canvas><div class="char-name">${escapeHtml(name)}</div>`;
    const sprite = new Sprite(card.querySelector("canvas")!);
    pickers.push(sprite);
    load(sprite).then(() => sprite.play("idle", { loop: true }));
    card.addEventListener("click", () => selectCard(grid, card, id, onPick));
    return card;
  };

  // Built-in buddies.
  CHARACTERS.forEach((c) => {
    grid.appendChild(addSpriteCard(c.id, c.name, (s) => s.load(characterDir(c.id))));
  });

  // "Make your own" card.
  const add = document.createElement("button");
  add.className = "char-card char-add";
  add.innerHTML = `<div class="char-add-plus">＋</div><div class="char-name">Make your own</div>`;
  add.addEventListener("click", onCreate);
  grid.appendChild(add);

  // Custom buddy (loaded async, inserted first if present).
  getCustomCharacter().then((c) => {
    if (!c) return;
    const card = addSpriteCard("custom", c.name, (s) => s.loadProcedural(c.image));
    grid.insertBefore(card, grid.firstChild);
  });

  return grid;
}

function hourOptions(selected: number): string {
  let out = "";
  for (let h = 0; h < 24; h++) {
    out += `<option value="${h}" ${h === selected ? "selected" : ""}>${String(h).padStart(2, "0")}:00</option>`;
  }
  return out;
}

// --- settings --------------------------------------------------------------
function renderSettings() {
  // Changes are staged in `draft` and only persisted on "Save & Apply".
  const draft: Settings = { ...settings };

  const wrap = document.createElement("div");
  wrap.className = "content";
  wrap.innerHTML = `
    <div class="brand">${DROP_SVG}
      <div><h1>Hydration Hero</h1><p class="sub">by <strong>Strawvarie</strong></p></div>
    </div>

    <div class="section">
      <p class="section-title">Your buddy</p>
      <div id="picker-slot"></div>
    </div>

    <div class="section">
      <p class="section-title">Reminders</p>
      <div class="card">
        <div class="row stack">
          <div><div class="label">Remind me every</div><div class="desc">Pick a preset or type your own</div></div>
          <div class="interval-options" id="interval-presets">
            ${INTERVAL_PRESETS.map((m) => `<button data-m="${m}" class="${m === draft.interval_minutes ? "active" : ""}">${m}m</button>`).join("")}
            <label class="custom-slot" for="interval-input">
              <input type="number" id="interval-input" min="1" max="480" value="${draft.interval_minutes}" aria-label="Custom minutes between reminders" />
              <span>m</span>
            </label>
          </div>
        </div>
        <div class="row">
          <div><div class="label">Active hours</div><div class="desc">Only remind me between these times</div></div>
          <div class="control field-row">
            <select id="start-h">${hourOptions(draft.active_start_hour)}</select>
            <span style="color:var(--muted)">to</span>
            <select id="end-h">${hourOptions(draft.active_end_hour)}</select>
          </div>
        </div>
        <div class="row">
          <div><div class="label">Snooze length</div><div class="desc">Delay when you tap snooze</div></div>
          <div class="control">
            <select id="snooze">
              ${[5, 10, 15, 20, 30].map((m) => `<option value="${m}" ${m === draft.snooze_minutes ? "selected" : ""}>${m} min</option>`).join("")}
            </select>
          </div>
        </div>
      </div>
    </div>

    <div class="section">
      <p class="section-title">Appearance</p>
      <div class="card">
        <div class="row">
          <div><div class="label">Show buddy in</div><div class="desc">Which screen corner</div></div>
          <div class="control">
            <select id="corner">
              <option value="bottom-right" ${sel("corner", "bottom-right")}>Bottom right</option>
              <option value="bottom-left" ${sel("corner", "bottom-left")}>Bottom left</option>
              <option value="top-right" ${sel("corner", "top-right")}>Top right</option>
              <option value="top-left" ${sel("corner", "top-left")}>Top left</option>
            </select>
          </div>
        </div>
        <div class="row">
          <div><div class="label">Theme</div><div class="desc">Bubble &amp; window colours</div></div>
          <div class="control">
            <select id="theme">
              <option value="system" ${sel("theme", "system")}>System</option>
              <option value="light" ${sel("theme", "light")}>Light</option>
              <option value="dark" ${sel("theme", "dark")}>Dark</option>
            </select>
          </div>
        </div>
      </div>
    </div>

    <div class="section">
      <p class="section-title">General</p>
      <div class="card">
        <div class="row">
          <div><div class="label">Chime on reminder</div><div class="desc">A soft sound when your buddy arrives</div></div>
          ${switchHtml("sound", draft.sound_enabled)}
        </div>
        <div class="row">
          <div>
            <div class="label">Open at login ${infoIcon(LOGIN_HELP)}</div>
            <div class="desc">Hydration Hero opens by itself when you turn on your computer, so you never forget to run it.</div>
          </div>
          ${switchHtml("login", draft.launch_at_login)}
        </div>
      </div>
    </div>`;

  const footer = document.createElement("div");
  footer.className = "footer";
  footer.innerHTML = `
    <button class="btn-primary full" id="save" disabled>Save &amp; apply</button>
    <button class="btn-ghost full" id="to-about">About &amp; privacy</button>`;

  app.appendChild(wrap);
  app.appendChild(footer);

  const saveBtn = footer.querySelector<HTMLButtonElement>("#save")!;
  // Enable Save only when something actually changed.
  const markDirty = () => {
    saveBtn.disabled = JSON.stringify(draft) === JSON.stringify(settings);
  };

  wrap.querySelector("#picker-slot")!.appendChild(
    buildPicker((id) => {
      draft.character_id = id;
      markDirty();
    }, openCreate),
  );

  const intervalInput = wrap.querySelector<HTMLInputElement>("#interval-input")!;
  const syncPresets = (val: number) => {
    wrap
      .querySelectorAll<HTMLButtonElement>("#interval-presets button")
      .forEach((n) => n.classList.toggle("active", Number(n.dataset.m) === val));
  };
  const setInterval = (val: number) => {
    draft.interval_minutes = val;
    syncPresets(val);
    markDirty();
  };
  wrap.querySelectorAll<HTMLButtonElement>("#interval-presets button").forEach((b) => {
    b.addEventListener("click", () => {
      const val = Number(b.dataset.m);
      intervalInput.value = String(val);
      setInterval(val);
    });
  });
  intervalInput.addEventListener("change", () => {
    let val = Math.round(Number(intervalInput.value));
    if (!Number.isFinite(val) || val < 1) val = 1;
    if (val > 480) val = 480;
    intervalInput.value = String(val);
    setInterval(val);
  });

  bindSelect(wrap, "#start-h", (v) => {
    draft.active_start_hour = Number(v);
    markDirty();
  });
  bindSelect(wrap, "#end-h", (v) => {
    draft.active_end_hour = Number(v);
    markDirty();
  });
  bindSelect(wrap, "#snooze", (v) => {
    draft.snooze_minutes = Number(v);
    markDirty();
  });
  bindSelect(wrap, "#corner", (v) => {
    draft.corner = v;
    markDirty();
  });
  bindSelect(wrap, "#theme", (v) => {
    draft.theme = v as Settings["theme"];
    applyTheme(draft.theme); // live preview
    markDirty();
  });
  bindSwitch(wrap, "sound", (v) => {
    draft.sound_enabled = v;
    markDirty();
  });
  bindSwitch(wrap, "login", (v) => {
    draft.launch_at_login = v;
    markDirty();
  });

  saveBtn.addEventListener("click", async () => {
    saveBtn.disabled = true;
    await saveSettings(draft); // persist + reschedule next for the new interval
    settings = { ...draft };
    await remindNow(); // immediate reminder as confirmation; next fires after the interval
    saveBtn.textContent = "Saved ✓  here's your reminder";
    setTimeout(() => {
      saveBtn.textContent = "Save & apply";
      markDirty();
    }, 2000);
  });

  footer.querySelector("#to-about")!.addEventListener("click", () => {
    view = "about";
    render();
  });
}

// --- about -----------------------------------------------------------------
async function renderAbout() {
  const wrap = document.createElement("div");
  wrap.className = "content about";
  wrap.innerHTML = `
    <div class="brand" style="justify-content:center">${DROP_SVG}
      <div style="text-align:left"><h1>Hydration Hero</h1><p class="sub">by <strong>Strawvarie</strong></p></div>
    </div>
    <p class="privacy">Everything stays on your device. No accounts, no tracking, no data
      leaves your computer. The app only reaches the internet if you tap “Check for updates”.</p>
    <div class="links">
      <button class="btn-secondary" id="updates">Check for updates</button>
      <button class="btn-secondary" id="shop">Shop Strawvarie ↗</button>
      <button class="back-btn" id="back">‹ Back</button>
    </div>
    <p class="version">Version <span id="ver">…</span></p>`;
  app.appendChild(wrap);

  getVersion().then((v) => {
    const el = wrap.querySelector("#ver");
    if (el) el.textContent = v;
  });
  wrap.querySelector("#updates")!.addEventListener("click", () => openUrl(RELEASES_URL));
  wrap.querySelector("#shop")!.addEventListener("click", () => openUrl(SHOP_URL));
  wrap.querySelector("#back")!.addEventListener("click", () => {
    view = "settings";
    render();
  });
}

// --- make your own ---------------------------------------------------------
/** Grab a mid-clip frame and key out its green background for a still poster. */
function extractPoster(videoDataUrl: string): Promise<string | null> {
  return new Promise((resolve) => {
    const v = document.createElement("video");
    v.muted = true;
    v.playsInline = true;
    v.preload = "auto";
    const grab = async () => {
      try {
        const c = document.createElement("canvas");
        c.width = v.videoWidth;
        c.height = v.videoHeight;
        c.getContext("2d")!.drawImage(v, 0, 0);
        resolve(await processCharacterImageFromDataUrl(c.toDataURL("image/png")));
      } catch {
        resolve(null);
      }
    };
    v.addEventListener(
      "loadeddata",
      () => {
        const t = v.duration && isFinite(v.duration) ? v.duration * 0.45 : 0;
        v.addEventListener("seeked", grab, { once: true });
        try {
          v.currentTime = t;
        } catch {
          void grab();
        }
      },
      { once: true },
    );
    v.addEventListener("error", () => resolve(null), { once: true });
    v.src = videoDataUrl;
    v.load();
  });
}

function renderCreate() {
  // Primary path: an animated green-screen clip (walk in → sip → walk out).
  // Fallback (collapsed): one or two still images.
  let videoUrl: string | null = null;
  let poster: string | null = null;
  let standImg: string | null = null;
  let sipImg: string | null = null;

  const wrap = document.createElement("div");
  wrap.className = "content create";
  wrap.innerHTML = `
    <div class="create-head">
      <button class="back-btn" id="c-back">‹ Back</button>
      <h2>Make your own buddy</h2>
    </div>
    <p class="create-intro">Make a short animation of your character and it'll walk in, sip, and stroll off in every reminder.</p>
    <ol class="steps">
      <li><strong>Make your character.</strong> In Google Gemini, upload a full-body photo and send this:
        <div class="prompt-box">
          <span>${escapeHtml(GEMINI_PROMPT_STAND)}</span>
          <button class="btn-secondary copy" data-prompt="stand">Copy</button>
        </div>
      </li>
      <li><strong>Animate it.</strong> In an image-to-video tool (Gemini Veo, Runway, Kling…), upload that image and send this:
        <div class="prompt-box">
          <span>${escapeHtml(CLIP_PROMPT)}</span>
          <button class="btn-secondary copy" data-prompt="clip">Copy</button>
        </div>
        <span class="hint">The bright-green background is what lets the app cut your character out — keep it solid green.</span>
      </li>
      <li><strong>Download the video</strong>, then bring it here:
        <button class="btn-primary" id="c-choose-video">Choose video…</button>
        <span class="c-status" id="c-status-video"></span>
      </li>
    </ol>
    <div class="import-row">
      <button class="btn-secondary" id="c-gemini">Open Gemini ↗</button>
    </div>
    <div class="preview-wrap" id="c-preview" hidden>
      <canvas class="sprite" id="c-canvas"></canvas>
      <div class="preview-form">
        <input type="text" id="c-name" placeholder="Name your buddy" maxlength="18"/>
        <div class="preview-actions">
          <button class="btn-primary" id="c-save">Use this buddy</button>
        </div>
      </div>
    </div>
    <details class="still-fallback">
      <summary>No video? Use a still image instead</summary>
      <ol class="steps">
        <li><strong>Standing pose.</strong> Use the character image from step 1 above.
          <button class="btn-secondary" id="c-choose-stand">Choose standing image…</button>
          <span class="c-status" id="c-status-stand"></span>
        </li>
        <li><strong>Sipping pose</strong> <span class="opt">(optional)</span>. Same character raising the tumbler:
          <div class="prompt-box">
            <span>${escapeHtml(GEMINI_PROMPT_SIP)}</span>
            <button class="btn-secondary copy" data-prompt="sip">Copy</button>
          </div>
          <button class="btn-secondary" id="c-choose-sip">Choose sipping image…</button>
          <span class="c-status" id="c-status-sip"></span>
        </li>
      </ol>
      <div class="preview-wrap" id="c-preview-still" hidden>
        <canvas class="sprite" id="c-canvas-still"></canvas>
        <div class="preview-form">
          <input type="text" id="c-name-still" placeholder="Name your buddy" maxlength="18"/>
          <div class="preview-actions">
            <button class="btn-secondary" id="c-drink" hidden>Preview sip</button>
            <button class="btn-primary" id="c-save-still">Use this buddy</button>
          </div>
        </div>
      </div>
    </details>`;
  app.appendChild(wrap);

  const status = (id: string) => wrap.querySelector<HTMLSpanElement>(`#${id}`)!;

  // --- video path ---
  const videoPreview = wrap.querySelector<HTMLDivElement>("#c-preview")!;
  const videoCanvas = wrap.querySelector<HTMLCanvasElement>("#c-canvas")!;
  videoCanvas.width = 220;
  videoCanvas.height = 220;
  const previewBuddy = new VideoBuddy(videoCanvas);
  createVideoBuddy = previewBuddy;
  const loopPreview = () => previewBuddy.play(loopPreview);

  wrap.querySelector("#c-choose-video")!.addEventListener("click", async () => {
    let path: string | string[] | null = null;
    try {
      path = await open({
        multiple: false,
        directory: false,
        filters: [{ name: "Video", extensions: ["mp4", "mov", "m4v", "webm"] }],
      });
    } catch {
      status("c-status-video").textContent = "Couldn't open the file picker.";
      return;
    }
    if (!path || Array.isArray(path)) return;
    status("c-status-video").textContent = "Processing…";
    try {
      videoUrl = await readVideoAsDataUrl(path);
      await previewBuddy.load(videoUrl);
      loopPreview();
      videoPreview.hidden = false;
      status("c-status-video").textContent = "Added ✓";
      poster = await extractPoster(videoUrl); // for the still fallback / reduced-motion
    } catch {
      videoUrl = null;
      status("c-status-video").textContent = "That video didn't work. Try an MP4.";
    }
  });

  wrap.querySelector("#c-save")!.addEventListener("click", async () => {
    if (!videoUrl) return;
    const name =
      wrap.querySelector<HTMLInputElement>("#c-name")!.value.trim().slice(0, 18) || "My buddy";
    await saveCustomCharacter(name, poster ?? TRANSPARENT_PX, null, videoUrl);
    settings = await getSettings();
    view = createReturn;
    render();
  });

  // --- still fallback path ---
  const stillPreview = wrap.querySelector<HTMLDivElement>("#c-preview-still")!;
  const drinkBtn = wrap.querySelector<HTMLButtonElement>("#c-drink")!;
  const previewSprite = new Sprite(wrap.querySelector<HTMLCanvasElement>("#c-canvas-still")!);
  pickers.push(previewSprite);

  const refreshStill = async () => {
    if (!standImg) return;
    await previewSprite.loadProcedural(standImg, sipImg);
    previewSprite.play("idle", { loop: true });
    stillPreview.hidden = false;
    drinkBtn.hidden = sipImg === null;
  };
  const pickInto = async (which: "stand" | "sip") => {
    let path: string | string[] | null = null;
    try {
      path = await open({
        multiple: false,
        directory: false,
        filters: [{ name: "Images", extensions: ["png", "jpg", "jpeg", "webp", "gif", "bmp"] }],
      });
    } catch {
      status(`c-status-${which}`).textContent = "Couldn't open the file picker.";
      return;
    }
    if (!path || Array.isArray(path)) return;
    status(`c-status-${which}`).textContent = "Processing…";
    try {
      const processed = await processCharacterImageFromDataUrl(await readImageAsDataUrl(path));
      if (which === "stand") standImg = processed;
      else sipImg = processed;
      status(`c-status-${which}`).textContent = "Added ✓";
      await refreshStill();
    } catch {
      status(`c-status-${which}`).textContent = "That image didn't work. Try a PNG or JPG.";
    }
  };
  wrap.querySelector("#c-choose-stand")!.addEventListener("click", () => pickInto("stand"));
  wrap.querySelector("#c-choose-sip")!.addEventListener("click", () => pickInto("sip"));
  drinkBtn.addEventListener("click", () =>
    previewSprite.play("drink", { onComplete: () => previewSprite.play("idle", { loop: true }) }),
  );
  wrap.querySelector("#c-save-still")!.addEventListener("click", async () => {
    if (!standImg) return;
    const name =
      wrap.querySelector<HTMLInputElement>("#c-name-still")!.value.trim().slice(0, 18) || "My buddy";
    await saveCustomCharacter(name, standImg, sipImg, null);
    settings = await getSettings();
    view = createReturn;
    render();
  });

  // --- shared ---
  wrap.querySelector("#c-back")!.addEventListener("click", () => {
    view = createReturn;
    render();
  });
  wrap.querySelector("#c-gemini")!.addEventListener("click", () => openUrl(GEMINI_URL));
  wrap.querySelectorAll<HTMLButtonElement>(".copy").forEach((b) =>
    b.addEventListener("click", async () => {
      const which = b.dataset.prompt;
      await copyText(
        which === "sip" ? GEMINI_PROMPT_SIP : which === "clip" ? CLIP_PROMPT : GEMINI_PROMPT_STAND,
      );
      const old = b.textContent;
      b.textContent = "Copied!";
      setTimeout(() => (b.textContent = old), 1500);
    }),
  );
}

// --- onboarding ------------------------------------------------------------
function renderOnboarding() {
  const onb = document.createElement("div");
  onb.className = "onb";
  const dots = `<div class="dots">${[0, 1, 2, 3].map((i) => `<span class="${i === step ? "on" : ""}"></span>`).join("")}</div>`;

  if (step === 0) {
    onb.innerHTML = `
      <div class="stage">
        <canvas class="sprite" id="hello"></canvas>
        <h2>hi, i'm your hydration hero</h2>
        <p>i'll live in your menu bar and gently remind you to sip from your Strawvarie tumbler through the day.</p>
      </div>
      <div class="nav"><button class="btn-primary" id="next">Let's go</button></div>
      ${dots}`;
    app.appendChild(onb);
    const sp = new Sprite(onb.querySelector("#hello")!);
    pickers.push(sp);
    sp.load(characterDir(settings.character_id)).then(() => sp.play("idle", { loop: true }));
    onb.querySelector("#next")!.addEventListener("click", () => go(1));
  } else if (step === 1) {
    onb.innerHTML = `
      <div class="stage">
        <h2>pick your buddy</h2>
        <p>you can change this any time in settings.</p>
        <div id="pick" style="width:100%"></div>
      </div>
      <div class="nav">
        <button class="btn-secondary" id="back">Back</button>
        <button class="btn-primary" id="next">Continue</button>
      </div>${dots}`;
    app.appendChild(onb);
    onb
      .querySelector("#pick")!
      .appendChild(buildPicker((id) => update({ character_id: id }), openCreate));
    onb.querySelector("#back")!.addEventListener("click", () => go(0));
    onb.querySelector("#next")!.addEventListener("click", () => go(2));
  } else if (step === 2) {
    onb.innerHTML = `
      <div class="stage">
        <h2>set your rhythm</h2>
        <p>how often should your buddy check in, and when?</p>
        <div class="presets" id="iv">
          ${INTERVAL_PRESETS.map((m) => `<button data-m="${m}" class="${m === settings.interval_minutes ? "active" : ""}">${m}m</button>`).join("")}
        </div>
        <div class="field-row">
          <select id="start-h">${hourOptions(settings.active_start_hour)}</select>
          <span style="color:var(--muted)">to</span>
          <select id="end-h">${hourOptions(settings.active_end_hour)}</select>
        </div>
      </div>
      <div class="nav">
        <button class="btn-secondary" id="back">Back</button>
        <button class="btn-primary" id="next">Continue</button>
      </div>${dots}`;
    app.appendChild(onb);
    onb.querySelectorAll<HTMLButtonElement>("#iv button").forEach((b) => {
      b.addEventListener("click", () => {
        onb.querySelectorAll("#iv button").forEach((n) => n.classList.remove("active"));
        b.classList.add("active");
        update({ interval_minutes: Number(b.dataset.m) });
      });
    });
    bindSelect(onb, "#start-h", (v) => update({ active_start_hour: Number(v) }));
    bindSelect(onb, "#end-h", (v) => update({ active_end_hour: Number(v) }));
    onb.querySelector("#back")!.addEventListener("click", () => go(1));
    onb.querySelector("#next")!.addEventListener("click", () => go(3));
  } else {
    onb.innerHTML = `
      <div class="stage">
        <canvas class="sprite" id="done"></canvas>
        <h2>that's it!</h2>
        <p>i live in your menu bar now — look for the little droplet up top. tap it any time to pause or change things.</p>
        <div class="row" style="width:100%;max-width:340px;background:var(--card);border:1px solid var(--border);border-radius:12px">
          <div style="text-align:left"><div class="label">Open at login ${infoIcon(LOGIN_HELP)}</div><div class="desc">Opens by itself when you start your computer</div></div>
          ${switchHtml("login", settings.launch_at_login)}
        </div>
      </div>
      <div class="nav">
        <button class="btn-secondary" id="preview">See a preview</button>
        <button class="btn-primary" id="finish">Finish</button>
      </div>${dots}`;
    app.appendChild(onb);
    const sp = new Sprite(onb.querySelector("#done")!);
    pickers.push(sp);
    sp.load(characterDir(settings.character_id)).then(() => sp.play("idle", { loop: true }));
    bindSwitch(onb, "login", (v) => update({ launch_at_login: v }));
    onb.querySelector("#preview")!.addEventListener("click", () => remindNow());
    onb.querySelector("#finish")!.addEventListener("click", async () => {
      await update({ onboarding_complete: true });
      await getCurrentWindow().hide();
      view = "settings";
      step = 0;
    });
  }
}

function go(next: number) {
  step = next;
  render();
}

// --- small DOM helpers -----------------------------------------------------
function sel(key: keyof Settings, value: string): string {
  return settings[key] === value ? "selected" : "";
}
function infoIcon(text: string): string {
  // Uses a custom tooltip (see setupTooltips) — the native `title` tooltip
  // does not render inside Tauri's WKWebView.
  return `<span class="info-icon" data-tip="${escapeHtml(text)}" role="img" aria-label="More information" tabindex="0">i</span>`;
}

/** A single custom tooltip driven by hover/focus of any [data-tip] element. */
function setupTooltips() {
  const tip = document.createElement("div");
  tip.className = "tooltip";
  tip.setAttribute("role", "tooltip");
  document.body.appendChild(tip);

  const show = (el: HTMLElement) => {
    const text = el.getAttribute("data-tip");
    if (!text) return;
    tip.textContent = text;
    tip.classList.add("show");
    const r = el.getBoundingClientRect();
    const tw = tip.offsetWidth;
    const th = tip.offsetHeight;
    let left = r.left + r.width / 2 - tw / 2;
    left = Math.max(8, Math.min(left, window.innerWidth - tw - 8));
    let top = r.top - th - 8;
    if (top < 8) top = r.bottom + 8; // flip below if there's no room above
    tip.style.left = `${left}px`;
    tip.style.top = `${top}px`;
  };
  const hide = () => tip.classList.remove("show");

  const target = (e: Event) =>
    (e.target as HTMLElement | null)?.closest?.(".info-icon") as HTMLElement | null;
  document.addEventListener("mouseover", (e) => {
    const el = target(e);
    if (el) show(el);
  });
  document.addEventListener("mouseout", (e) => {
    if (target(e)) hide();
  });
  document.addEventListener("focusin", (e) => {
    const el = target(e);
    if (el) show(el);
  });
  document.addEventListener("focusout", (e) => {
    if (target(e)) hide();
  });
}
function switchHtml(id: string, on: boolean): string {
  return `<label class="switch control"><input type="checkbox" id="sw-${id}" ${on ? "checked" : ""}/><span class="track"></span><span class="thumb"></span></label>`;
}
function bindSelect(scope: HTMLElement, selector: string, cb: (v: string) => void) {
  const el = scope.querySelector<HTMLSelectElement>(selector);
  el?.addEventListener("change", () => cb(el.value));
}
function bindSwitch(scope: HTMLElement, id: string, cb: (v: boolean) => void) {
  const el = scope.querySelector<HTMLInputElement>(`#sw-${id}`);
  el?.addEventListener("change", () => cb(el.checked));
}
function escapeHtml(s: string): string {
  return s.replace(
    /[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!,
  );
}
async function copyText(text: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(text);
    return;
  } catch {
    /* fall through to the legacy path */
  }
  const ta = document.createElement("textarea");
  ta.value = text;
  ta.style.position = "fixed";
  ta.style.opacity = "0";
  document.body.appendChild(ta);
  ta.select();
  try {
    document.execCommand("copy");
  } catch {
    /* ignore */
  }
  ta.remove();
}

boot();
