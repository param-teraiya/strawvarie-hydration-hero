// The reminder overlay: a frosted-glass card in a screen corner holding the
// pixel buddy, the message, Strawvarie branding, and the actions. Rust shows
// this (transparent, non-focusing) window and emits "reminder-show"; the window
// fetches its own settings and animates the card in.
import { getCurrentWindow } from "@tauri-apps/api/window";
import "../shared/theme.css";
import "./overlay.css";
import { Sprite } from "../shared/sprites";
import { applyTheme } from "../shared/theme";
import { characterDir } from "../shared/characters";
import { getCustomCharacter, getSettings, listen, reminderAction, type Settings } from "../shared/ipc";

const DISMISS_AFTER_MS = 45_000;
const CARD_EXIT_MS = 260;
const SETTLE_MS = 700;

const LINES = [
  "time for a sip 💧",
  "hydration break!",
  "a little water?",
  "your tumbler misses you 💧",
];

const DROP = `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2C12 2 4 11 4 16a8 8 0 0 0 16 0C20 11 12 2 12 2Z" fill="var(--accent)"/></svg>`;

const root = document.getElementById("overlay-root")!;
root.innerHTML = `
  <div class="glass-card" id="card">
    <button class="x" id="x" aria-label="Dismiss reminder">✕</button>
    <div class="hero"><canvas class="sprite"></canvas></div>
    <div class="body">
      <div class="brand-row">${DROP}<span class="brand-name">Strawvarie</span></div>
      <div class="headline" id="headline">time for a sip 💧</div>
      <div class="actions">
        <button class="btn-primary" id="drank">I drank 💧</button>
        <button class="btn-secondary" id="snooze">Snooze</button>
      </div>
    </div>
  </div>`;

const card = root.querySelector<HTMLDivElement>("#card")!;
const canvas = root.querySelector<HTMLCanvasElement>("canvas.sprite")!;
const headline = root.querySelector<HTMLDivElement>("#headline")!;
const drankBtn = root.querySelector<HTMLButtonElement>("#drank")!;
const snoozeBtn = root.querySelector<HTMLButtonElement>("#snooze")!;
const xBtn = root.querySelector<HTMLButtonElement>("#x")!;

const sprite = new Sprite(canvas);
let busy = false;
let dismissTimer = 0;
let settleTimer = 0;
let audioCtx: AudioContext | null = null;

function chime() {
  try {
    audioCtx ??= new AudioContext();
    const now = audioCtx.currentTime;
    [660, 880].forEach((freq, i) => {
      const osc = audioCtx!.createOscillator();
      const gain = audioCtx!.createGain();
      osc.type = "sine";
      osc.frequency.value = freq;
      const t = now + i * 0.14;
      gain.gain.setValueAtTime(0, t);
      gain.gain.linearRampToValueAtTime(0.12, t + 0.03);
      gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.3);
      osc.connect(gain).connect(audioCtx!.destination);
      osc.start(t);
      osc.stop(t + 0.32);
    });
  } catch {
    /* audio is a nicety; ignore failures */
  }
}

async function ensureCharacter(id: string) {
  if (id === "custom") {
    const custom = await getCustomCharacter();
    if (custom) {
      if (sprite.id !== "custom") await sprite.loadProcedural(custom.image);
      return;
    }
    id = "berry"; // custom selected but missing — fall back gracefully
  }
  if (sprite.id !== id) {
    await sprite.load(characterDir(id));
  }
}

async function run(settings: Settings) {
  busy = false;
  clearTimeout(dismissTimer);
  clearTimeout(settleTimer);

  await ensureCharacter(settings.character_id);
  applyTheme(settings.theme);
  headline.textContent = LINES[Math.floor(Math.random() * LINES.length)];
  snoozeBtn.textContent = `Snooze ${settings.snooze_minutes}m`;

  if (settings.sound_enabled) chime();

  // Slide the glass card in.
  card.classList.remove("in", "out");
  void card.offsetWidth; // force reflow so the transition replays
  requestAnimationFrame(() => card.classList.add("in"));

  // Buddy walks into place, then idles.
  sprite.play("walk", { loop: true });
  settleTimer = window.setTimeout(() => sprite.play("idle", { loop: true }), SETTLE_MS);

  dismissTimer = window.setTimeout(() => finish("dismiss"), DISMISS_AFTER_MS);
}

function finish(action: "drank" | "snooze" | "dismiss") {
  if (busy) return;
  busy = true;
  clearTimeout(dismissTimer);
  clearTimeout(settleTimer);

  const exit = () => {
    card.classList.remove("in");
    card.classList.add("out");
    window.setTimeout(() => close(action), CARD_EXIT_MS);
  };

  if (action === "drank") {
    sprite.play("drink", { loop: false, onComplete: exit });
  } else {
    exit();
  }
}

async function close(action: "drank" | "snooze" | "dismiss") {
  await reminderAction(action);
  sprite.stop();
  await getCurrentWindow().hide();
  card.classList.remove("in", "out");
  busy = false;
}

drankBtn.addEventListener("click", () => finish("drank"));
snoozeBtn.addEventListener("click", () => finish("snooze"));
xBtn.addEventListener("click", () => finish("dismiss"));

// Rust shows the window then emits this; we fetch settings and run.
listen("reminder-show", async () => {
  try {
    const settings = await getSettings();
    await run(settings);
  } catch (e) {
    console.error("overlay run failed", e);
    await getCurrentWindow().hide();
  }
});
