// The main window: first-run onboarding, settings, and about. There is no
// dashboard — this app is reminders only, so this window is small and quiet.
import { getCurrentWindow } from "@tauri-apps/api/window";
import { getVersion } from "@tauri-apps/api/app";
import { openUrl } from "@tauri-apps/plugin-opener";
import { open } from "@tauri-apps/plugin-dialog";
import "../shared/theme.css";
import "./main.css";
import { Sprite } from "../shared/sprites";
import { applyTheme } from "../shared/theme";
import { CHARACTERS, characterDir } from "../shared/characters";
import { processCharacterImageFromDataUrl } from "../shared/imageProcess";
import {
  getCustomCharacter,
  getSettings,
  listen,
  readImageAsDataUrl,
  remindNow,
  saveCustomCharacter,
  saveSettings,
  type Settings,
} from "../shared/ipc";

const SHOP_URL = "https://strawvarie.in";
const RELEASES_URL = "https://github.com/strawvarie/hydration-hero/releases";
const GEMINI_URL = "https://gemini.google.com/app";
const INTERVAL_PRESETS = [30, 45, 60, 90];
const GEMINI_PROMPT =
  "Turn the person in this photo into a cute full-body pixel-art character, " +
  "16-bit retro game style, standing and facing forward, full body from head to feet, " +
  "holding a stainless-steel water tumbler in one hand, " +
  "on a solid flat bright green background (hex #00FF00), no shadows, no text.";

const DROP_SVG = `<svg class="drop" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2C12 2 4 11 4 16a8 8 0 0 0 16 0C20 11 12 2 12 2Z" fill="var(--accent)"/></svg>`;

let settings: Settings;
let view: "onboarding" | "settings" | "about" | "create" = "settings";
let createReturn: "onboarding" | "settings" = "settings";
let step = 0;
let pickers: Sprite[] = [];

function openCreate() {
  createReturn = view === "onboarding" ? "onboarding" : "settings";
  view = "create";
  render();
}

const app = document.getElementById("app")!;

async function boot() {
  settings = await getSettings();
  applyTheme(settings.theme);
  view = settings.onboarding_complete ? "settings" : "onboarding";
  render();
  listen<string>("navigate", (e) => {
    view = e.payload === "about" ? "about" : "settings";
    render();
  });
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
  const wrap = document.createElement("div");
  wrap.className = "content";
  wrap.innerHTML = `
    <div class="brand">${DROP_SVG}
      <div><h1>Hydration Hero</h1><p class="sub">by Strawvarie · stay refreshed</p></div>
    </div>

    <div class="section">
      <p class="section-title">Your buddy</p>
      <div id="picker-slot"></div>
    </div>

    <div class="section">
      <p class="section-title">Reminders</p>
      <div class="card">
        <div class="row">
          <div><div class="label">Remind me every</div><div class="desc">How often your buddy pops by</div></div>
          <div class="control presets" id="interval-presets">
            ${INTERVAL_PRESETS.map((m) => `<button data-m="${m}" class="${m === settings.interval_minutes ? "active" : ""}">${m}m</button>`).join("")}
          </div>
        </div>
        <div class="row">
          <div><div class="label">Active hours</div><div class="desc">Only remind me between these times</div></div>
          <div class="control field-row">
            <select id="start-h">${hourOptions(settings.active_start_hour)}</select>
            <span style="color:var(--muted)">to</span>
            <select id="end-h">${hourOptions(settings.active_end_hour)}</select>
          </div>
        </div>
        <div class="row">
          <div><div class="label">Snooze length</div><div class="desc">Delay when you tap snooze</div></div>
          <div class="control">
            <select id="snooze">
              ${[5, 10, 15, 20, 30].map((m) => `<option value="${m}" ${m === settings.snooze_minutes ? "selected" : ""}>${m} min</option>`).join("")}
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
          ${switchHtml("sound", settings.sound_enabled)}
        </div>
        <div class="row">
          <div><div class="label">Open at login</div><div class="desc">Start quietly when your computer does</div></div>
          ${switchHtml("login", settings.launch_at_login)}
        </div>
      </div>
    </div>`;

  const footer = document.createElement("div");
  footer.className = "footer";
  footer.innerHTML = `
    <button class="btn-primary full" id="preview">Preview a reminder</button>
    <button class="btn-ghost full" id="to-about">About &amp; privacy</button>`;

  app.appendChild(wrap);
  app.appendChild(footer);

  wrap
    .querySelector("#picker-slot")!
    .appendChild(buildPicker((id) => update({ character_id: id }), openCreate));

  wrap.querySelectorAll<HTMLButtonElement>("#interval-presets button").forEach((b) => {
    b.addEventListener("click", () => {
      wrap.querySelectorAll("#interval-presets button").forEach((n) => n.classList.remove("active"));
      b.classList.add("active");
      update({ interval_minutes: Number(b.dataset.m) });
    });
  });
  bindSelect(wrap, "#start-h", (v) => update({ active_start_hour: Number(v) }));
  bindSelect(wrap, "#end-h", (v) => update({ active_end_hour: Number(v) }));
  bindSelect(wrap, "#snooze", (v) => update({ snooze_minutes: Number(v) }));
  bindSelect(wrap, "#corner", (v) => update({ corner: v }));
  bindSelect(wrap, "#theme", (v) => update({ theme: v as Settings["theme"] }));
  bindSwitch(wrap, "sound", (v) => update({ sound_enabled: v }));
  bindSwitch(wrap, "login", (v) => update({ launch_at_login: v }));

  footer.querySelector("#preview")!.addEventListener("click", () => remindNow());
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
      <div style="text-align:left"><h1>Hydration Hero</h1><p class="sub">by Strawvarie</p></div>
    </div>
    <p class="privacy">Everything stays on your device. No accounts, no tracking, no data
      leaves your computer. The app only reaches the internet if you tap “Check for updates”.</p>
    <div class="links">
      <button class="btn-secondary" id="updates">Check for updates</button>
      <button class="btn-secondary" id="shop">Shop Strawvarie ↗</button>
      <button class="btn-ghost" id="back">Back to settings</button>
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
function renderCreate() {
  let processed: string | null = null;
  const wrap = document.createElement("div");
  wrap.className = "content create";
  wrap.innerHTML = `
    <div class="create-head">
      <button class="btn-ghost" id="c-back">‹ Back</button>
      <h2>Make your own buddy</h2>
    </div>
    <p class="create-intro">Turn a photo into your very own pixel buddy — about a minute.</p>
    <ol class="steps">
      <li>Open Google Gemini and upload a clear, full-body photo.</li>
      <li>Paste this prompt and send it:
        <div class="prompt-box">
          <span id="prompt-text">${escapeHtml(GEMINI_PROMPT)}</span>
          <button class="btn-secondary copy" id="c-copy">Copy</button>
        </div>
      </li>
      <li>Download the image Gemini makes for you.</li>
      <li>Bring it back here with “Choose image”.</li>
    </ol>
    <div class="import-row">
      <button class="btn-secondary" id="c-gemini">Open Gemini ↗</button>
      <button class="btn-primary" id="c-choose">Choose image…</button>
    </div>
    <p class="c-status" id="c-status"></p>
    <div class="preview-wrap" id="c-preview" hidden>
      <canvas class="sprite" id="c-canvas"></canvas>
      <div class="preview-form">
        <input type="text" id="c-name" placeholder="Name your buddy" maxlength="18"/>
        <div class="preview-actions">
          <button class="btn-secondary" id="c-retry">Try another</button>
          <button class="btn-primary" id="c-save">Use this buddy</button>
        </div>
      </div>
    </div>
    <p class="hint">Tip: a plain, solid-colour background works best — the app removes it for you.</p>`;
  app.appendChild(wrap);

  const status = wrap.querySelector<HTMLParagraphElement>("#c-status")!;
  const previewWrap = wrap.querySelector<HTMLDivElement>("#c-preview")!;
  const nameInput = wrap.querySelector<HTMLInputElement>("#c-name")!;
  const previewSprite = new Sprite(wrap.querySelector<HTMLCanvasElement>("#c-canvas")!);
  pickers.push(previewSprite);

  wrap.querySelector("#c-back")!.addEventListener("click", () => {
    view = createReturn;
    render();
  });
  wrap.querySelector("#c-gemini")!.addEventListener("click", () => openUrl(GEMINI_URL));
  wrap.querySelector("#c-copy")!.addEventListener("click", async (e) => {
    await copyText(GEMINI_PROMPT);
    const b = e.currentTarget as HTMLButtonElement;
    const old = b.textContent;
    b.textContent = "Copied!";
    setTimeout(() => (b.textContent = old), 1500);
  });

  wrap.querySelector("#c-choose")!.addEventListener("click", async () => {
    let path: string | string[] | null = null;
    try {
      path = await open({
        multiple: false,
        directory: false,
        filters: [{ name: "Images", extensions: ["png", "jpg", "jpeg", "webp", "gif", "bmp"] }],
      });
    } catch {
      status.textContent = "Couldn't open the file picker. Please try again.";
      return;
    }
    if (!path || Array.isArray(path)) return;

    status.textContent = "Processing your image…";
    previewWrap.hidden = true;
    try {
      const dataUrl = await readImageAsDataUrl(path);
      processed = await processCharacterImageFromDataUrl(dataUrl);
      await previewSprite.loadProcedural(processed);
      previewSprite.play("idle", { loop: true });
      status.textContent = "";
      previewWrap.hidden = false;
    } catch {
      status.textContent = "That image didn't work. Try a PNG or JPG.";
    }
  });

  wrap.querySelector("#c-retry")!.addEventListener("click", () => {
    processed = null;
    previewWrap.hidden = true;
    previewSprite.stop();
  });

  wrap.querySelector("#c-save")!.addEventListener("click", async () => {
    if (!processed) return;
    const name = nameInput.value.trim().slice(0, 18) || "My buddy";
    await saveCustomCharacter(name, processed);
    settings = await getSettings(); // Rust already set character_id = "custom"
    view = createReturn;
    render();
  });
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
        <div class="row" style="width:100%;max-width:320px;background:var(--card);border:1px solid var(--border);border-radius:12px">
          <div style="text-align:left"><div class="label">Open at login</div><div class="desc">Start quietly with your computer</div></div>
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
