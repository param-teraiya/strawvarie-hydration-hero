//! The reminder brain. This is the one piece of real logic in the Rust layer.
//!
//! Param: this decides *when* a reminder fires. It runs on a background thread
//! that wakes every 15 seconds and asks a simple question: "is it time?"
//! Everything is driven by the wall clock (unix timestamps), so closing the
//! laptop lid and reopening it later Just Works — no missed-reminder backlog.

use crate::{now_unix, tray, windows, AppState};
use chrono::{Local, TimeZone, Timelike};
use tauri::{AppHandle, Manager};

/// How often the background thread checks the clock.
pub const TICK_SECONDS: u64 = 15;

/// Is `hour` inside the active window? Handles windows that wrap past midnight
/// (e.g. start=22, end=6). start==end means "always on".
pub fn within_active(hour: u32, start: u32, end: u32) -> bool {
    if start == end {
        true
    } else if start < end {
        hour >= start && hour < end
    } else {
        hour >= start || hour < end
    }
}

fn local_hour() -> u32 {
    Local::now().hour()
}

/// Next unix timestamp at which the local clock reads `hour:00`. Used for
/// "pause until tomorrow".
pub fn next_time_at_hour(hour: u32) -> i64 {
    let now = Local::now();
    let today = now.date_naive();
    let candidate = today.and_hms_opt(hour.min(23), 0, 0);
    if let Some(naive) = candidate {
        if let Some(dt) = Local.from_local_datetime(&naive).single() {
            let ts = dt.timestamp();
            if ts > now.timestamp() {
                return ts;
            }
        }
    }
    // otherwise the same hour tomorrow
    now.timestamp() + 24 * 3600
}

/// One scheduler tick. Called every TICK_SECONDS from a background thread.
pub fn tick(app: &AppHandle) {
    let state = app.state::<AppState>();
    let now = now_unix();

    // Expire a finished pause.
    let (paused, start, end) = {
        let mut s = state.settings.lock().unwrap();
        if let Some(p) = s.paused_until {
            if now >= p {
                s.paused_until = None;
                let _ = crate::settings::save(&s);
            }
        }
        let paused = s.paused_until.map(|p| now < p).unwrap_or(false);
        (paused, s.active_start_hour, s.active_end_hour)
    };

    tray::update_status(app);

    if paused || !within_active(local_hour(), start, end) {
        return;
    }

    // Don't stack reminders: if the overlay is already on screen, wait.
    let overlay_up = app
        .get_webview_window("overlay")
        .and_then(|w| w.is_visible().ok())
        .unwrap_or(false);
    if overlay_up {
        return;
    }

    let due = state
        .runtime
        .lock()
        .unwrap()
        .next_reminder_at
        .map(|n| now >= n)
        .unwrap_or(true);

    if due {
        windows::trigger_reminder(app);
    }
}
