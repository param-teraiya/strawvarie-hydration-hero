//! App settings: a small JSON file with atomic, corruption-tolerant persistence.
//!
//! Param: you will basically never need to touch this file. It loads/saves a
//! plain JSON blob. If the file is ever corrupt it backs it up and starts fresh
//! instead of crashing.

use serde::{Deserialize, Serialize};
use std::fs;
use std::path::PathBuf;
use tauri::{AppHandle, Manager};

/// Bump this if the shape of Settings changes in a breaking way.
const SCHEMA_VERSION: u32 = 1;

#[derive(Serialize, Deserialize, Clone, Debug)]
#[serde(default)]
pub struct Settings {
    pub schema_version: u32,
    pub onboarding_complete: bool,
    pub character_id: String,
    pub interval_minutes: u32,
    pub active_start_hour: u32,
    pub active_end_hour: u32,
    pub snooze_minutes: u32,
    /// "bottom-right" | "bottom-left" | "top-right" | "top-left"
    pub corner: String,
    pub sound_enabled: bool,
    pub launch_at_login: bool,
    /// "system" | "light" | "dark"
    pub theme: String,
    /// Unix seconds; while now < paused_until, no reminders fire. Persisted so
    /// a pause survives a restart.
    pub paused_until: Option<i64>,
}

impl Default for Settings {
    fn default() -> Self {
        Settings {
            schema_version: SCHEMA_VERSION,
            onboarding_complete: false,
            character_id: "berry".into(),
            interval_minutes: 45,
            active_start_hour: 9,
            active_end_hour: 22,
            snooze_minutes: 15,
            corner: "bottom-right".into(),
            sound_enabled: false,
            launch_at_login: true,
            theme: "system".into(),
            paused_until: None,
        }
    }
}

impl Settings {
    /// Keep values inside sane bounds so a bad edit can't wedge the scheduler.
    pub fn sanitize(&mut self) {
        self.interval_minutes = self.interval_minutes.clamp(15, 240);
        self.snooze_minutes = self.snooze_minutes.clamp(1, 120);
        self.active_start_hour = self.active_start_hour.min(23);
        self.active_end_hour = self.active_end_hour.min(24);
        let valid_corner = matches!(
            self.corner.as_str(),
            "bottom-right" | "bottom-left" | "top-right" | "top-left"
        );
        if !valid_corner {
            self.corner = "bottom-right".into();
        }
        if !matches!(self.theme.as_str(), "system" | "light" | "dark") {
            self.theme = "system".into();
        }
        let valid_char = matches!(
            self.character_id.as_str(),
            "berry" | "drip" | "sprout" | "custom"
        );
        if !valid_char {
            self.character_id = "berry".into();
        }
        self.schema_version = SCHEMA_VERSION;
    }
}

fn settings_path(app: &AppHandle) -> Option<PathBuf> {
    let dir = app.path().app_config_dir().ok()?;
    Some(dir.join("settings.json"))
}

/// Load settings. Missing file -> defaults. Corrupt file -> back it up and
/// use defaults (never crash on startup).
pub fn load(app: &AppHandle) -> Settings {
    let Some(path) = settings_path(app) else {
        return Settings::default();
    };
    let Ok(text) = fs::read_to_string(&path) else {
        return Settings::default();
    };
    match serde_json::from_str::<Settings>(&text) {
        Ok(mut s) => {
            s.sanitize();
            s
        }
        Err(_) => {
            let _ = fs::rename(&path, path.with_extension("json.bak"));
            Settings::default()
        }
    }
}

/// Persist settings atomically (write temp, then rename).
pub fn save(app: &AppHandle, settings: &Settings) -> Result<(), String> {
    let path = settings_path(app).ok_or("no config dir")?;
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    let json = serde_json::to_string_pretty(settings).map_err(|e| e.to_string())?;
    let tmp = path.with_extension("json.tmp");
    fs::write(&tmp, json).map_err(|e| e.to_string())?;
    fs::rename(&tmp, &path).map_err(|e| e.to_string())?;
    Ok(())
}
