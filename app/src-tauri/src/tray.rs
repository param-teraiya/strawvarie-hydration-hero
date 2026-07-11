//! The menu-bar / system-tray icon and its menu. This is the app's main home:
//! there is no dock icon, the tray is where the user lives day to day.

use crate::{now_unix, scheduler, windows, AppState};
use tauri::{
    menu::{Menu, MenuItem, PredefinedMenuItem, Submenu},
    tray::TrayIconBuilder,
    AppHandle, Emitter, Manager,
};

/// Build the tray icon + menu and stash the status line so we can update it.
pub fn build(app: &AppHandle) -> tauri::Result<()> {
    let status = MenuItem::with_id(app, "status", "Hydration Hero", false, None::<&str>)?;
    let remind = MenuItem::with_id(app, "remind", "Remind me now", true, None::<&str>)?;

    let pause_1h = MenuItem::with_id(app, "pause_1h", "Pause for 1 hour", true, None::<&str>)?;
    let pause_3h = MenuItem::with_id(app, "pause_3h", "Pause for 3 hours", true, None::<&str>)?;
    let pause_tom =
        MenuItem::with_id(app, "pause_tomorrow", "Pause until tomorrow", true, None::<&str>)?;
    let resume = MenuItem::with_id(app, "resume", "Resume reminders", true, None::<&str>)?;
    let pause_menu = Submenu::with_items(
        app,
        "Pause",
        true,
        &[&pause_1h, &pause_3h, &pause_tom, &resume],
    )?;

    let settings = MenuItem::with_id(app, "settings", "Settings…", true, None::<&str>)?;
    let about = MenuItem::with_id(app, "about", "About", true, None::<&str>)?;
    let quit = MenuItem::with_id(app, "quit", "Quit Hydration Hero", true, None::<&str>)?;

    let menu = Menu::with_items(
        app,
        &[
            &status,
            &PredefinedMenuItem::separator(app)?,
            &remind,
            &pause_menu,
            &PredefinedMenuItem::separator(app)?,
            &settings,
            &about,
            &PredefinedMenuItem::separator(app)?,
            &quit,
        ],
    )?;

    let icon = tauri::image::Image::from_bytes(include_bytes!("../icons/tray.png"))?;

    TrayIconBuilder::with_id("tray")
        .icon(icon)
        .icon_as_template(false)
        .tooltip("Hydration Hero")
        .menu(&menu)
        .show_menu_on_left_click(true)
        .on_menu_event(handle_menu_event)
        .build(app)?;

    // Remember the status item so the scheduler can keep it current.
    *app.state::<AppState>().tray_status.lock().unwrap() = Some(status);
    update_status(app);
    Ok(())
}

fn handle_menu_event(app: &AppHandle, event: tauri::menu::MenuEvent) {
    match event.id().as_ref() {
        "remind" => windows::trigger_reminder(app),
        "pause_1h" => crate::apply_pause(app, "1h"),
        "pause_3h" => crate::apply_pause(app, "3h"),
        "pause_tomorrow" => crate::apply_pause(app, "until_tomorrow"),
        "resume" => crate::apply_pause(app, "off"),
        "settings" => open_main(app, "settings"),
        "about" => open_main(app, "about"),
        "quit" => app.exit(0),
        _ => {}
    }
}

fn open_main(app: &AppHandle, view: &str) {
    if let Some(win) = app.get_webview_window("main") {
        let _ = win.show();
        let _ = win.unminimize();
        let _ = win.set_focus();
        let _ = app.emit_to("main", "navigate", view.to_string());
    }
}

/// Refresh the disabled status line at the top of the tray menu.
pub fn update_status(app: &AppHandle) {
    let state = app.state::<AppState>();
    let guard = state.tray_status.lock().unwrap();
    let Some(item) = guard.as_ref() else {
        return;
    };

    let now = now_unix();
    let (paused_until, start, end, next) = {
        let s = state.settings.lock().unwrap();
        let rt = state.runtime.lock().unwrap();
        (s.paused_until, s.active_start_hour, s.active_end_hour, rt.next_reminder_at)
    };

    let text = if paused_until.map(|p| now < p).unwrap_or(false) {
        "Paused".to_string()
    } else if !scheduler::within_active(chrono_hour(), start, end) {
        "Quiet hours".to_string()
    } else if let Some(n) = next {
        let mins = ((n - now) as f64 / 60.0).ceil() as i64;
        if mins <= 0 {
            "Time to sip!".to_string()
        } else {
            format!("Next sip in ~{mins} min")
        }
    } else {
        "Hydration Hero".to_string()
    };

    let _ = item.set_text(text);
}

fn chrono_hour() -> u32 {
    use chrono::Timelike;
    chrono::Local::now().hour()
}
