//! Storage for the user's custom character (their "make your own" buddy).
//!
//! We keep it dead simple: one JSON file in the app config dir holding a name
//! and the processed PNG as a data URL. The heavy lifting (turning a photo into
//! a clean character image) happens in the frontend; Rust just persists the
//! result.

use serde::{Deserialize, Serialize};
use std::fs;
use std::path::PathBuf;
use tauri::{AppHandle, Manager};

#[derive(Serialize, Deserialize, Clone)]
pub struct CustomCharacter {
    pub name: String,
    /// PNG as a `data:image/png;base64,...` URL.
    pub image: String,
}

fn path(app: &AppHandle) -> Option<PathBuf> {
    Some(app.path().app_config_dir().ok()?.join("custom_character.json"))
}

pub fn load(app: &AppHandle) -> Option<CustomCharacter> {
    let text = fs::read_to_string(path(app)?).ok()?;
    serde_json::from_str(&text).ok()
}

pub fn save(app: &AppHandle, character: &CustomCharacter) -> Result<(), String> {
    let p = path(app).ok_or("no config dir")?;
    if let Some(parent) = p.parent() {
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    let json = serde_json::to_string(character).map_err(|e| e.to_string())?;
    let tmp = p.with_extension("json.tmp");
    fs::write(&tmp, json).map_err(|e| e.to_string())?;
    fs::rename(&tmp, &p).map_err(|e| e.to_string())?;
    Ok(())
}

pub fn delete(app: &AppHandle) {
    if let Some(p) = path(app) {
        let _ = fs::remove_file(p);
    }
}
