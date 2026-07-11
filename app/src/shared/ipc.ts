// Typed wrappers around the Rust commands. This is the whole surface between
// the TypeScript UI and the Rust core — every backend call goes through here.
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";

export interface Settings {
  schema_version: number;
  onboarding_complete: boolean;
  character_id: string;
  interval_minutes: number;
  active_start_hour: number;
  active_end_hour: number;
  snooze_minutes: number;
  corner: string;
  sound_enabled: boolean;
  launch_at_login: boolean;
  theme: "system" | "light" | "dark";
  paused_until: number | null;
}

export interface Status {
  now: number;
  next_at: number | null;
  paused_until: number | null;
}

export const getSettings = () => invoke<Settings>("get_settings");
export const saveSettings = (settings: Settings) => invoke("save_settings", { settings });
export const getStatus = () => invoke<Status>("get_status");
export const reminderAction = (action: "drank" | "snooze" | "dismiss") =>
  invoke("reminder_action", { action });
export const remindNow = () => invoke("remind_now");
export const setPause = (kind: "1h" | "3h" | "until_tomorrow" | "off") =>
  invoke("set_pause", { kind });

export { listen };
