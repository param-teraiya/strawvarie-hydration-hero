//! Hydration Hero — app entry point, shared state, and the commands the
//! TypeScript frontend calls.
//!
//! Param: the whole Rust surface is these six modules. The frontend talks to
//! the functions marked `#[tauri::command]` via `invoke(...)`. Everything else
//! is wiring you should rarely need to open.

mod custom;
mod scheduler;
mod settings;
mod tray;
mod windows;

pub use settings::Settings;

use std::sync::Mutex;
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use tauri::{AppHandle, Manager};
use tauri_plugin_autostart::{MacosLauncher, ManagerExt};

/// Runtime state that does not need to be persisted.
pub struct Runtime {
    /// Unix seconds at which the next reminder is due.
    pub next_reminder_at: Option<i64>,
}

/// Everything the app shares across threads and commands.
pub struct AppState {
    pub settings: Mutex<Settings>,
    pub runtime: Mutex<Runtime>,
    pub tray_status: Mutex<Option<tauri::menu::MenuItem<tauri::Wry>>>,
}

pub fn now_unix() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0)
}

// --- reminder scheduling shared with the tray ------------------------------

/// Apply a pause ("1h" | "3h" | "until_tomorrow" | "off").
pub fn apply_pause(app: &AppHandle, kind: &str) {
    let state = app.state::<AppState>();
    let now = now_unix();

    let until = match kind {
        "1h" => Some(now + 3600),
        "3h" => Some(now + 3 * 3600),
        "until_tomorrow" => {
            let start = state.settings.lock().unwrap().active_start_hour;
            Some(scheduler::next_time_at_hour(start))
        }
        _ => None, // "off" / resume
    };

    {
        let mut s = state.settings.lock().unwrap();
        s.paused_until = until;
        let _ = settings::save(&s);
    }

    if until.is_none() {
        // Resuming: schedule the next reminder one interval out.
        let interval = state.settings.lock().unwrap().interval_minutes as i64;
        state.runtime.lock().unwrap().next_reminder_at = Some(now + interval * 60);
    }

    tray::update_status(app);
}

fn apply_autostart(app: &AppHandle, enabled: bool) {
    let manager = app.autolaunch();
    let _ = if enabled {
        manager.enable()
    } else {
        manager.disable()
    };
}

// --- commands the frontend calls -------------------------------------------

#[tauri::command]
fn get_settings(state: tauri::State<AppState>) -> Settings {
    state.settings.lock().unwrap().clone()
}

#[tauri::command]
fn save_settings(
    app: AppHandle,
    state: tauri::State<AppState>,
    mut settings: Settings,
) -> Result<(), String> {
    settings.sanitize();
    {
        let mut s = state.settings.lock().unwrap();
        *s = settings.clone();
    }
    settings::save(&settings)?;
    apply_autostart(&app, settings.launch_at_login);

    // Reschedule from now with the (possibly new) interval.
    let now = now_unix();
    state.runtime.lock().unwrap().next_reminder_at = Some(now + settings.interval_minutes as i64 * 60);
    tray::update_status(&app);
    Ok(())
}

#[derive(serde::Serialize)]
struct Status {
    now: i64,
    next_at: Option<i64>,
    paused_until: Option<i64>,
}

#[tauri::command]
fn get_status(state: tauri::State<AppState>) -> Status {
    let rt = state.runtime.lock().unwrap();
    let s = state.settings.lock().unwrap();
    Status {
        now: now_unix(),
        next_at: rt.next_reminder_at,
        paused_until: s.paused_until,
    }
}

/// Called by the overlay when the user picks an action. The overlay plays its
/// own exit animation and hides its window; we just reschedule.
#[tauri::command]
fn reminder_action(app: AppHandle, state: tauri::State<AppState>, action: String) {
    let now = now_unix();
    let (interval, snooze) = {
        let s = state.settings.lock().unwrap();
        (s.interval_minutes as i64, s.snooze_minutes as i64)
    };
    let next = match action.as_str() {
        "snooze" => now + snooze * 60,
        _ => now + interval * 60, // "drank" | "dismiss"
    };
    state.runtime.lock().unwrap().next_reminder_at = Some(next);
    tray::update_status(&app);
}

#[tauri::command]
fn remind_now(app: AppHandle) {
    windows::trigger_reminder(&app);
}

#[tauri::command]
fn set_pause(app: AppHandle, kind: String) {
    apply_pause(&app, &kind);
}

#[tauri::command]
fn get_custom_character(app: AppHandle) -> Option<custom::CustomCharacter> {
    custom::load(&app)
}

#[tauri::command]
fn save_custom_character(
    app: AppHandle,
    state: tauri::State<AppState>,
    name: String,
    image: String,
) -> Result<(), String> {
    custom::save(&app, &custom::CustomCharacter { name, image })?;
    // Selecting the new buddy right away.
    let mut s = state.settings.lock().unwrap();
    s.character_id = "custom".into();
    settings::save(&s)
}

/// Read a user-picked image file and return it as a data URL the webview can
/// load. Paired with the native file dialog so file selection is reliable.
#[tauri::command]
fn read_image_as_data_url(path: String) -> Result<String, String> {
    use base64::Engine;
    let bytes = std::fs::read(&path).map_err(|e| e.to_string())?;
    let mime = match path.rsplit('.').next().map(|s| s.to_lowercase()).as_deref() {
        Some("jpg") | Some("jpeg") => "image/jpeg",
        Some("webp") => "image/webp",
        Some("gif") => "image/gif",
        Some("bmp") => "image/bmp",
        _ => "image/png",
    };
    let encoded = base64::engine::general_purpose::STANDARD.encode(bytes);
    Ok(format!("data:{mime};base64,{encoded}"))
}

#[tauri::command]
fn delete_custom_character(app: AppHandle, state: tauri::State<AppState>) -> Result<(), String> {
    custom::delete(&app);
    let mut s = state.settings.lock().unwrap();
    if s.character_id == "custom" {
        s.character_id = "berry".into();
        return settings::save(&s);
    }
    Ok(())
}

/// Bring the main window to the front. Used on re-launch / re-activation so the
/// app never feels "dead" when a user opens it while it's already in the tray.
/// On macOS we briefly become a regular (dock-visible) app so the window
/// actually comes to the foreground; closing the window drops us back to
/// menu-bar-only (see the window close handler).
fn reveal_main(app: &AppHandle) {
    #[cfg(target_os = "macos")]
    let _ = app.set_activation_policy(tauri::ActivationPolicy::Regular);
    if let Some(win) = app.get_webview_window("main") {
        let _ = win.show();
        let _ = win.unminimize();
        let _ = win.set_focus();
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    // Load settings before the app is built so the managed state is real from
    // the very first moment (no startup race with the webview).
    let loaded = settings::load();
    let onboarding_done = loaded.onboarding_complete;
    let launch_at_login = loaded.launch_at_login;
    let interval = loaded.interval_minutes as i64;

    let app = tauri::Builder::default()
        // Must be registered first: focuses the running app instead of
        // launching a second copy when the user opens it again.
        .plugin(tauri_plugin_single_instance::init(|app, _argv, _cwd| {
            reveal_main(app);
        }))
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_autostart::init(
            MacosLauncher::LaunchAgent,
            // Passed only when the OS launches us at login, so we can tell a
            // login-launch (stay quiet) from a manual open (show the window).
            Some(vec!["--autostart"]),
        ))
        // Register the real state up-front (before any window loads) so commands
        // like get_settings never race the setup hook — on Windows the webview
        // can invoke before setup() runs.
        .manage(AppState {
            settings: Mutex::new(loaded),
            runtime: Mutex::new(Runtime {
                next_reminder_at: Some(now_unix() + interval * 60),
            }),
            tray_status: Mutex::new(None),
        })
        .invoke_handler(tauri::generate_handler![
            get_settings,
            save_settings,
            get_status,
            reminder_action,
            remind_now,
            set_pause,
            get_custom_character,
            save_custom_character,
            delete_custom_character,
            read_image_as_data_url,
        ])
        .on_window_event(|window, event| {
            // Closing the main window hides it (the app lives in the tray) and
            // drops the dock icon so we're menu-bar-only again.
            if window.label() == "main" {
                if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                    api.prevent_close();
                    let _ = window.hide();
                    #[cfg(target_os = "macos")]
                    let _ = window
                        .app_handle()
                        .set_activation_policy(tauri::ActivationPolicy::Accessory);
                }
            }
        })
        .setup(move |app| {
            let handle = app.handle();
            apply_autostart(handle, launch_at_login);
            tray::build(handle)?;

            // Show the window on first run (onboarding) and on any manual
            // launch. Only stay silently in the tray (menu-bar-only) when the OS
            // launched us at login (marked by the --autostart flag).
            let launched_at_login = std::env::args().any(|a| a == "--autostart");
            if !onboarding_done || !launched_at_login {
                reveal_main(handle);
            } else {
                #[cfg(target_os = "macos")]
                let _ = handle.set_activation_policy(tauri::ActivationPolicy::Accessory);
            }

            // Background thread: the reminder clock.
            let sched_handle = handle.clone();
            std::thread::spawn(move || loop {
                std::thread::sleep(Duration::from_secs(scheduler::TICK_SECONDS));
                scheduler::tick(&sched_handle);
            });

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building Hydration Hero");

    app.run(|app_handle, _event| {
        // macOS: clicking the app again (Finder / dock) reopens the window.
        #[cfg(target_os = "macos")]
        if let tauri::RunEvent::Reopen { .. } = _event {
            reveal_main(app_handle);
        }
    });
}
