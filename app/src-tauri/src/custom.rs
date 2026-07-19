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
    /// A still of the character (a keyed frame of the video, or an imported
    /// image). Used as the picker preview and the reduced-motion fallback.
    /// PNG as a `data:image/png;base64,...` URL.
    pub image: String,
    /// Optional "sipping" pose (tumbler raised to the mouth) for the still,
    /// two-pose buddies. Absent for video buddies and old single-image buddies.
    #[serde(default)]
    pub drink_image: Option<String>,
    /// True when a green-screen animation clip is stored alongside (see
    /// `video_path`). The overlay plays it with live background removal.
    #[serde(default)]
    pub has_video: bool,
}

fn path(app: &AppHandle) -> Option<PathBuf> {
    Some(app.path().app_config_dir().ok()?.join("custom_character.json"))
}

fn video_path(app: &AppHandle) -> Option<PathBuf> {
    Some(app.path().app_config_dir().ok()?.join("custom_character.mp4"))
}

/// Decode a `data:video/mp4;base64,...` URL and store the raw bytes as an .mp4
/// file (kept out of the JSON so the config stays small).
pub fn save_video(app: &AppHandle, data_url: &str) -> Result<(), String> {
    use base64::Engine;
    let b64 = data_url.split(",").nth(1).ok_or("malformed video data URL")?;
    let bytes = base64::engine::general_purpose::STANDARD
        .decode(b64)
        .map_err(|e| e.to_string())?;
    let p = video_path(app).ok_or("no config dir")?;
    if let Some(parent) = p.parent() {
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    let tmp = p.with_extension("mp4.tmp");
    fs::write(&tmp, bytes).map_err(|e| e.to_string())?;
    fs::rename(&tmp, &p).map_err(|e| e.to_string())?;
    Ok(())
}

/// Read the stored clip back as a `data:video/mp4;base64,...` URL for playback.
pub fn load_video(app: &AppHandle) -> Option<String> {
    use base64::Engine;
    let bytes = fs::read(video_path(app)?).ok()?;
    let encoded = base64::engine::general_purpose::STANDARD.encode(bytes);
    Some(format!("data:video/mp4;base64,{encoded}"))
}

pub fn delete_video(app: &AppHandle) {
    if let Some(p) = video_path(app) {
        let _ = fs::remove_file(p);
    }
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
    delete_video(app);
}
