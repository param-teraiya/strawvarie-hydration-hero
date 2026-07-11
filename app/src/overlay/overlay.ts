// The reminder overlay: the pixel buddy walks into a screen corner, shows a
// speech bubble with actions, and walks off. Rust shows this window and emits
// "reminder-show"; the window fetches its own settings and runs the sequence.
import { getCurrentWindow } from "@tauri-apps/api/window";
import "../shared/theme.css";
import "./overlay.css";
import { Sprite } from "../shared/sprites";
import { applyTheme } from "../shared/theme";
import { characterDir } from "../shared/characters";
import { getCustomCharacter, getSettings, listen, reminderAction, type Settings } from "../shared/ipc";

const DISMISS_AFTER_MS = 45_000;
const WALK_MS = 1000;

const LINES = [
  "time for a sip 💧",
  "hydration break!",
  "a little water?",
  "your tumbler misses you 💧",
];

const root = document.getElementById("overlay-root")!;
root.innerHTML = `
  <div class="character"><canvas class="sprite"></canvas></div>
  <div class="cloud">
    <div class="bubble">
      <span class="bubble-text">time for a sip 💧</span>
      <button class="dismiss-x" title="Dismiss" aria-label="Dismiss reminder">✕</button>
    </div>
    <div class="actions">
      <button class="btn-primary drank">I drank 💧</button>
      <button class="btn-secondary snooze">Snooze</button>
    </div>
  </div>`;

const characterEl = root.querySelector<HTMLDivElement>(".character")!;
const canvas = root.querySelector<HTMLCanvasElement>("canvas.sprite")!;
const cloud = root.querySelector<HTMLDivElement>(".cloud")!;
const bubbleText = root.querySelector<HTMLSpanElement>(".bubble-text")!;
const drankBtn = root.querySelector<HTMLButtonElement>(".drank")!;
const snoozeBtn = root.querySelector<HTMLButtonElement>(".snooze")!;
const dismissBtn = root.querySelector<HTMLButtonElement>(".dismiss-x")!;

const sprite = new Sprite(canvas);
let busy = false;
let dismissTimer = 0;
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
  await ensureCharacter(settings.character_id);
  applyTheme(settings.theme);
  bubbleText.textContent = LINES[Math.floor(Math.random() * LINES.length)];
  snoozeBtn.textContent = `Snooze ${settings.snooze_minutes}m`;
  cloud.classList.remove("show");

  if (settings.sound_enabled) chime();

  if (sprite.reduceMotion) {
    characterEl.classList.remove("walk-anim");
    characterEl.style.transform = "translateX(0)";
    sprite.play("idle", { loop: true });
    revealControls();
    return;
  }

  // Walk in from the left, then settle into idle and reveal the bubble.
  characterEl.classList.remove("walk-anim");
  characterEl.style.transform = "translateX(-200px)";
  sprite.play("walk", { loop: true });
  requestAnimationFrame(() => {
    characterEl.classList.add("walk-anim");
    characterEl.style.transform = "translateX(0)";
  });
  window.setTimeout(() => {
    sprite.play("idle", { loop: true });
    revealControls();
  }, WALK_MS);
}

function revealControls() {
  cloud.classList.add("show");
  dismissTimer = window.setTimeout(() => finish("dismiss"), DISMISS_AFTER_MS);
}

function finish(action: "drank" | "snooze" | "dismiss") {
  if (busy) return;
  busy = true;
  clearTimeout(dismissTimer);
  cloud.classList.remove("show");

  const walkOut = () => {
    if (sprite.reduceMotion) {
      close(action);
      return;
    }
    sprite.play("walk", { loop: true });
    characterEl.classList.add("walk-anim");
    characterEl.style.transform = "translateX(240px)";
    window.setTimeout(() => close(action), WALK_MS);
  };

  if (action === "drank") {
    sprite.play("drink", { loop: false, onComplete: walkOut });
  } else {
    walkOut();
  }
}

async function close(action: "drank" | "snooze" | "dismiss") {
  await reminderAction(action);
  sprite.stop();
  await getCurrentWindow().hide();
  // reset for next time
  characterEl.classList.remove("walk-anim");
  characterEl.style.transform = "translateX(-200px)";
  busy = false;
}

drankBtn.addEventListener("click", () => finish("drank"));
snoozeBtn.addEventListener("click", () => finish("snooze"));
dismissBtn.addEventListener("click", () => finish("dismiss"));

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
