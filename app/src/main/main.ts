// The main window: first-run onboarding, settings, and about. There is no
// dashboard — this app is reminders only, so this window is small and quiet.
import { getCurrentWindow } from "@tauri-apps/api/window";
import { getVersion } from "@tauri-apps/api/app";
import { openUrl } from "@tauri-apps/plugin-opener";
import "../shared/theme.css";
import "./main.css";
import { Sprite } from "../shared/sprites";
import { applyTheme } from "../shared/theme";
import { CHARACTERS, characterDir } from "../shared/characters";
import { getSettings, listen, remindNow, saveSettings, type Settings } from "../shared/ipc";

const SHOP_URL = "https://strawvarie.in";
const RELEASES_URL = "https://github.com/strawvarie/hydration-hero/releases";
const INTERVAL_PRESETS = [30, 45, 60, 90];

const DROP_SVG = `<svg class="drop" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2C12 2 4 11 4 16a8 8 0 0 0 16 0C20 11 12 2 12 2Z" fill="var(--accent)"/></svg>`;

let settings: Settings;
let view: "onboarding" | "settings" | "about" = "settings";
let step = 0;
let pickers: Sprite[] = [];

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
  else renderSettings();
}

// --- reusable character picker ---------------------------------------------
function buildPicker(onPick: (id: string) => void): HTMLElement {
  const grid = document.createElement("div");
  grid.className = "char-grid";
  CHARACTERS.forEach((c) => {
    const card = document.createElement("button");
    card.className = "char-card" + (c.id === settings.character_id ? " selected" : "");
    card.innerHTML = `<canvas class="sprite"></canvas><div class="char-name">${c.name}</div>`;
    const sprite = new Sprite(card.querySelector("canvas")!);
    pickers.push(sprite);
    sprite.load(characterDir(c.id)).then(() => sprite.play("idle", { loop: true }));
    card.addEventListener("click", () => {
      grid.querySelectorAll(".char-card").forEach((n) => n.classList.remove("selected"));
      card.classList.add("selected");
      onPick(c.id);
    });
    grid.appendChild(card);
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

  wrap.querySelector("#picker-slot")!.appendChild(buildPicker((id) => update({ character_id: id })));

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
    onb.querySelector("#pick")!.appendChild(buildPicker((id) => update({ character_id: id })));
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

boot();
