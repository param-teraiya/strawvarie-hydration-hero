//! Hydration Hero — app entry point, shared state, and the commands the
//! TypeScript frontend calls.
//!
//! Param: the whole Rust surface is these six modules. The frontend talks to
//! the functions marked `#[tauri::command]` via `invoke(...)`. Everything else
//! is wiring you should rarely need to open.

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
        let _ = settings::save(app, &s);
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
    settings::save(&app, &settings)?;
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

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_autostart::init(
            MacosLauncher::LaunchAgent,
            None,
        ))
        .invoke_handler(tauri::generate_handler![
            get_settings,
            save_settings,
            get_status,
            reminder_action,
            remind_now,
            set_pause,
        ])
        .on_window_event(|window, event| {
            // Closing the main window hides it (the app lives in the tray).
            if window.label() == "main" {
                if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                    api.prevent_close();
                    let _ = window.hide();
                }
            }
        })
        .setup(|app| {
            // Menu-bar app: no dock icon on macOS.
            #[cfg(target_os = "macos")]
            app.set_activation_policy(tauri::ActivationPolicy::Accessory);

            let handle = app.handle();
            let loaded = settings::load(handle);
            apply_autostart(handle, loaded.launch_at_login);

            let onboarding_done = loaded.onboarding_complete;
            let interval = loaded.interval_minutes as i64;

            app.manage(AppState {
                settings: Mutex::new(loaded),
                runtime: Mutex::new(Runtime {
                    next_reminder_at: Some(now_unix() + interval * 60),
                }),
                tray_status: Mutex::new(None),
            });

            tray::build(handle)?;

            // First run: show onboarding. Otherwise stay quietly in the tray.
            if !onboarding_done {
                if let Some(win) = app.get_webview_window("main") {
                    let _ = win.show();
                    let _ = win.set_focus();
                }
            }

            // Background thread: the reminder clock.
            let sched_handle = handle.clone();
            std::thread::spawn(move || loop {
                std::thread::sleep(Duration::from_secs(scheduler::TICK_SECONDS));
                scheduler::tick(&sched_handle);
            });

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running Hydration Hero");
}
