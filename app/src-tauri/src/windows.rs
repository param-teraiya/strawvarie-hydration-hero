//! Overlay window helpers: position it in the right screen corner and show it.
//!
//! Param: the overlay is a small transparent window that appears in a corner.
//! We keep it deliberately compact so it never blocks much of your screen, and
//! we show it WITHOUT focusing it, so a reminder never interrupts your typing.

use crate::{now_unix, AppState};
use tauri::{AppHandle, Emitter, Manager, Monitor, PhysicalPosition};

const MARGIN_LOGICAL: f64 = 24.0;

/// Show the reminder overlay now (unless it is already visible). Also advances
/// the baseline schedule so the app keeps ticking even if the user ignores it.
pub fn trigger_reminder(app: &AppHandle) {
    let Some(win) = app.get_webview_window("overlay") else {
        return;
    };
    if win.is_visible().unwrap_or(false) {
        return;
    }

    let corner = {
        let state = app.state::<AppState>();
        let s = state.settings.lock().unwrap();
        s.corner.clone()
    };

    position_in_corner(app, &win, &corner);
    // Surface on the user's current Space and float above the active app,
    // without stealing keyboard focus (the window is non-activating).
    let _ = win.set_always_on_top(true);
    #[cfg(not(target_os = "macos"))]
    let _ = win.set_visible_on_all_workspaces(true);
    #[cfg(target_os = "macos")]
    apply_macos_overlay_behavior(&win);
    let _ = win.show();
    // The overlay window fetches its own settings and starts the animation.
    let _ = app.emit("reminder-show", ());

    // Advance the schedule baseline; a real action (drank/snooze/dismiss) will
    // refine it. This guarantees the app never gets stuck if the overlay dies.
    let state = app.state::<AppState>();
    let interval = state.settings.lock().unwrap().interval_minutes as i64;
    state.runtime.lock().unwrap().next_reminder_at = Some(now_unix() + interval * 60);
}

fn position_in_corner(app: &AppHandle, win: &tauri::WebviewWindow, corner: &str) {
    let cursor = app.cursor_position().ok();
    let Some(monitor) = pick_monitor(app, cursor) else {
        return;
    };

    // Use the work area (excludes the Dock and menu bar) so the buddy never
    // hides behind the Dock.
    let area = monitor.work_area();
    let scale = monitor.scale_factor();
    let margin = (MARGIN_LOGICAL * scale) as i32;

    let win_size = match win.outer_size() {
        Ok(s) => s,
        Err(_) => return,
    };
    let ww = win_size.width as i32;
    let wh = win_size.height as i32;

    let (mx, my) = (area.position.x, area.position.y);
    let (mw, mh) = (area.size.width as i32, area.size.height as i32);

    let (x, y) = match corner {
        "bottom-left" => (mx + margin, my + mh - wh - margin),
        "top-left" => (mx + margin, my + margin),
        "top-right" => (mx + mw - ww - margin, my + margin),
        _ => (mx + mw - ww - margin, my + mh - wh - margin), // bottom-right
    };

    let _ = win.set_position(PhysicalPosition { x, y });
}

/// macOS: let the overlay appear over full-screen apps and on every Space,
/// without becoming a full-screen-able window itself. Tauri doesn't expose the
/// `fullScreenAuxiliary` collection behaviour, so we set it on the NSWindow.
#[cfg(target_os = "macos")]
fn apply_macos_overlay_behavior(win: &tauri::WebviewWindow) {
    use objc::{msg_send, runtime::Object, sel, sel_impl};
    let Ok(ptr) = win.ns_window() else {
        return;
    };
    let ns_window = ptr as *mut Object;
    // CanJoinAllSpaces(1<<0) | Stationary(1<<4) | FullScreenAuxiliary(1<<8)
    let behavior: u64 = (1 << 0) | (1 << 4) | (1 << 8);
    unsafe {
        let _: () = msg_send![ns_window, setCollectionBehavior: behavior];
        // NSStatusWindowLevel (25) floats above full-screen app content.
        let _: () = msg_send![ns_window, setLevel: 25i64];
    }
}

/// The monitor under the cursor, or the primary monitor as a fallback.
fn pick_monitor(app: &AppHandle, cursor: Option<PhysicalPosition<f64>>) -> Option<Monitor> {
    let monitors = app.available_monitors().ok()?;
    if let Some(c) = cursor {
        let (cx, cy) = (c.x as i32, c.y as i32);
        for m in &monitors {
            let p = m.position();
            let s = m.size();
            if cx >= p.x
                && cx < p.x + s.width as i32
                && cy >= p.y
                && cy < p.y + s.height as i32
            {
                return Some(m.clone());
            }
        }
    }
    app.primary_monitor()
        .ok()
        .flatten()
        .or_else(|| monitors.into_iter().next())
}
