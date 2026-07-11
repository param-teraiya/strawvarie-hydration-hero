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

    let mp = monitor.position();
    let ms = monitor.size();
    let scale = monitor.scale_factor();
    let margin = (MARGIN_LOGICAL * scale) as i32;

    let win_size = match win.outer_size() {
        Ok(s) => s,
        Err(_) => return,
    };
    let ww = win_size.width as i32;
    let wh = win_size.height as i32;

    let (mx, my) = (mp.x, mp.y);
    let (mw, mh) = (ms.width as i32, ms.height as i32);

    let (x, y) = match corner {
        "bottom-left" => (mx + margin, my + mh - wh - margin),
        "top-left" => (mx + margin, my + margin),
        "top-right" => (mx + mw - ww - margin, my + margin),
        _ => (mx + mw - ww - margin, my + mh - wh - margin), // bottom-right
    };

    let _ = win.set_position(PhysicalPosition { x, y });
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
