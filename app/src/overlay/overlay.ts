// The reminder overlay: a frosted-glass card in a screen corner holding the
// pixel buddy, the message, Strawvarie branding, and the actions. Rust shows
// this (transparent, non-focusing) window and emits "reminder-show"; the window
// fetches its own settings and animates the card in.
import { getCurrentWindow } from "@tauri-apps/api/window";
import "../shared/theme.css";
import "./overlay.css";
import { Sprite } from "../shared/sprites";
import { VideoBuddy } from "./videoBuddy";
import { applyTheme } from "../shared/theme";
import { characterDir } from "../shared/characters";
import {
  getCustomCharacter,
  getCustomVideo,
  getSettings,
  listen,
  reminderAction,
  type Settings,
} from "../shared/ipc";

const DISMISS_AFTER_MS = 45_000;
const CARD_EXIT_MS = 260;
const WALK_MS = 800;
const OFFSCREEN = "translateX(-120px)"; // buddy parked off the card's left edge

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
let videoBuddy: VideoBuddy | null = null;
let usingVideo = false;
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
      if (sprite.id !== "custom")
        await sprite.loadProcedural(custom.image, custom.drink_image);
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

  applyTheme(settings.theme);
  headline.textContent = LINES[Math.floor(Math.random() * LINES.length)];
  snoozeBtn.textContent = `Snooze ${settings.snooze_minutes}m`;

  // A custom buddy with a green-screen clip plays as video (unless the user
  // prefers reduced motion, in which case we show its still poster).
  const custom =
    settings.character_id === "custom" ? await getCustomCharacter() : null;
  usingVideo = !!custom?.has_video && !sprite.reduceMotion;

  if (usingVideo) {
    const clip = await getCustomVideo();
    if (clip) {
      videoBuddy ??= new VideoBuddy(canvas);
      canvas.width = 220;
      canvas.height = 220;
      try {
        await videoBuddy.load(clip);
      } catch {
        usingVideo = false;
      }
    } else {
      usingVideo = false;
    }
  }
  if (!usingVideo) {
    sprite.stop();
    await ensureCharacter(settings.character_id);
  }
  card.classList.toggle("has-video", usingVideo);

  if (settings.sound_enabled) chime();

  // Reset: card hidden, buddy parked off the left edge (no transition yet).
  card.classList.remove("in", "out");
  canvas.classList.remove("walking");
  canvas.style.transform = OFFSCREEN;
  void card.offsetWidth; // force reflow so the transitions replay cleanly

  if (usingVideo) {
    // The clip walks the buddy in and sips; it plays once and freezes on the
    // final standing frame, staying on screen until the user acts (no
    // auto-dismiss timer on the video path — see below).
    requestAnimationFrame(() => {
      card.classList.add("in");
      canvas.classList.add("walking");
      canvas.style.transform = "translateX(0)";
    });
    videoBuddy!.play();
  } else if (sprite.reduceMotion) {
    canvas.style.transform = "translateX(0)";
    card.classList.add("in");
    sprite.play("idle", { loop: true });
  } else {
    // Card slides in while the buddy walks into place from the edge.
    sprite.play("walk", { loop: true });
    requestAnimationFrame(() => {
      card.classList.add("in");
      canvas.classList.add("walking");
      canvas.style.transform = "translateX(0)";
    });
    settleTimer = window.setTimeout(() => sprite.play("idle", { loop: true }), WALK_MS);
  }

  // Video buddies stay until the user acts. Sprite reminders keep the safety
  // auto-dismiss so a built-in buddy never gets stuck in a corner.
  if (!usingVideo) {
    dismissTimer = window.setTimeout(() => finish("dismiss"), DISMISS_AFTER_MS);
  }
}

function finish(action: "drank" | "snooze" | "dismiss") {
  if (busy) return;
  busy = true;
  clearTimeout(dismissTimer);
  clearTimeout(settleTimer);

  const fadeAndClose = () => {
    card.classList.remove("in");
    card.classList.add("out");
    window.setTimeout(() => close(action), CARD_EXIT_MS);
  };

  // The video buddy plays its own exit; if the user acts early we slide it off
  // and fade the card, otherwise the clip's end triggered this and we just fade.
  if (usingVideo) {
    canvas.classList.add("walking");
    canvas.style.transform = OFFSCREEN;
    videoBuddy?.stop();
    fadeAndClose();
    return;
  }

  const walkOut = () => {
    if (sprite.reduceMotion) {
      fadeAndClose();
      return;
    }
    // Stroll back out the edge the buddy came in from, then fade the card.
    sprite.play("walk", { loop: true });
    canvas.classList.add("walking");
    canvas.style.transform = OFFSCREEN;
    window.setTimeout(fadeAndClose, WALK_MS);
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
  videoBuddy?.stop();
  await getCurrentWindow().hide();
  card.classList.remove("in", "out");
  canvas.classList.remove("walking");
  canvas.style.transform = OFFSCREEN;
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
