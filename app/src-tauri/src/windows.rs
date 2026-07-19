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
    //
    // On macOS the overlay's Space/level/full-screen behavior is configured once
    // at startup (see `configure_overlay_for_fullscreen`) and persists across
    // hide/show, so we deliberately do NOT call `set_always_on_top` here — that
    // would reset the window level back below other apps' full-screen spaces.
    #[cfg(not(target_os = "macos"))]
    {
        let _ = win.set_visible_on_all_workspaces(true);
        let _ = win.set_always_on_top(true);
    }
    let _ = win.show();
    // The overlay window fetches its own settings and starts the animation.
    let _ = app.emit("reminder-show", ());

    // Advance the schedule baseline; a real action (drank/snooze/dismiss) will
    // refine it. This guarantees the app never gets stuck if the overlay dies.
    let state = app.state::<AppState>();
    let interval = state.settings.lock().unwrap().interval_minutes as i64;
    state.runtime.lock().unwrap().next_reminder_at = Some(now_unix() + interval * 60);
}

/// One-time macOS setup so the overlay floats above other apps and shows even
/// when another app is in full-screen mode.
///
/// Two AppKit properties do the work: the collection behavior gains
/// `CanJoinAllSpaces` + `FullScreenAuxiliary` (the latter is what lets a window
/// appear inside another app's full-screen Space — Tauri's own
/// `set_visible_on_all_workspaces` only sets `CanJoinAllSpaces`), and the window
/// level is raised to the status level so it sits above ordinary windows.
///
/// Both are persistent `NSWindow` properties, so we set them once at startup and
/// never touch AppKit at reminder time. `NSWindow` is main-thread-only, so all
/// the work is hopped onto the main thread via `run_on_main_thread`.
#[cfg(target_os = "macos")]
pub fn configure_overlay_for_fullscreen(app: &AppHandle) {
    let Some(win) = app.get_webview_window("overlay") else {
        return;
    };
    let win_on_main = win.clone();
    let _ = win.run_on_main_thread(move || {
        let Ok(ptr) = win_on_main.ns_window() else {
            return;
        };
        if ptr.is_null() {
            return;
        }
        use objc2_app_kit::{NSWindow, NSWindowCollectionBehavior};
        // SAFETY: we are on the main thread (guaranteed by run_on_main_thread),
        // and `ptr` is a live NSWindow owned by this window for the app's life.
        let ns_window: &NSWindow = unsafe { &*(ptr as *const NSWindow) };
        let behavior = ns_window.collectionBehavior()
            | NSWindowCollectionBehavior::CanJoinAllSpaces
            | NSWindowCollectionBehavior::FullScreenAuxiliary
            | NSWindowCollectionBehavior::Stationary;
        ns_window.setCollectionBehavior(behavior);
        // NSStatusWindowLevel (25): above normal and floating windows and, paired
        // with FullScreenAuxiliary, visible over other apps' full-screen spaces.
        ns_window.setLevel(25);
    });
}

/// No-op on non-macOS platforms; Windows/Linux float the overlay via
/// `set_always_on_top` at reminder time instead.
#[cfg(not(target_os = "macos"))]
pub fn configure_overlay_for_fullscreen(_app: &AppHandle) {}

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
