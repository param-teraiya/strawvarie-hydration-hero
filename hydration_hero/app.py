import platform
import queue
import threading
import time
from typing import Optional

from PIL import Image

from hydration_hero.animation import AnimationLibrary
from hydration_hero.brand import APP_NAME, BRAND_NAME, FULL_TITLE, create_tray_logo
from hydration_hero.hero import HeroStatus, get_hero_state, process_hero_video
from hydration_hero.main_window import MainWindow
from hydration_hero.paths import ensure_user_hero_root
from hydration_hero.reminder import ReminderPopup
from hydration_hero.storage import SettingsStore
from hydration_hero.ui import init_customtkinter


class HydrationHeroApp:
    def __init__(self) -> None:
        init_customtkinter()
        ensure_user_hero_root()
        self.store = SettingsStore(on_change=self._on_settings_changed)
        self.animations = AnimationLibrary()
        self.event_queue = queue.Queue()
        self.running = True
        self.next_reminder_at = time.time() + self._interval_seconds()

        self.main_window = MainWindow(
            self.store,
            on_minimize_to_tray=self._hide_main_window,
            on_preview_reminder=self._show_reminder,
            on_create_hero=self._create_custom_hero,
        )
        self.reminder = ReminderPopup(
            self.main_window,
            self.animations,
            self.store.settings.default_drink_ml,
            on_drank=self._on_drank,
            on_snooze=self._on_snooze,
            on_dismiss=self._on_dismiss,
        )
        self.tray_icon = None
        self._tray_thread: Optional[threading.Thread] = None
        self._use_tray = platform.system() != "Darwin"
        self._hero_processing = False

        self.animations.load_async(
            on_ready=lambda: self.main_window.after(0, self._on_animations_ready),
        )
        if platform.system() == "Darwin":
            self.main_window.createcommand("::tk::mac::ReopenApplication", self._show_main_window)
        threading.Thread(target=self._timer_loop, daemon=True).start()
        self.main_window.after(100, self._poll_queue)
        self.main_window.after(200, self._refresh_hero_status)
        self.main_window.after(2000, self._poll_hero_status)

    def _poll_hero_status(self) -> None:
        self._refresh_hero_status()
        if self.running:
            self.main_window.after(2000, self._poll_hero_status)

    def _refresh_hero_status(self) -> None:
        if self._hero_processing:
            return
        state = get_hero_state()
        self.main_window.set_hero_state(state.status, state.message)

    def _create_custom_hero(self) -> None:
        state = get_hero_state()
        if state.status != HeroStatus.NEEDS_PROCESSING:
            self.main_window.refresh_hero_status(
                "Save your video as hero.mp4 in the hero folder first.",
                processing=False,
            )
            self.main_window.set_hero_state(state.status, state.message)
            return

        self._hero_processing = True
        self.main_window.set_hero_state(HeroStatus.PROCESSING, "Creating your hero…")

        def on_progress(message: str) -> None:
            self.main_window.after(0, lambda: self.main_window.refresh_hero_status(message, processing=True))

        def on_complete(_state) -> None:
            def finish() -> None:
                self._hero_processing = False
                self.animations.reload_async(on_ready=self._on_animations_ready)
                self._refresh_hero_status()
                self.main_window._flash_status("Custom hero ready! Try Preview reminder.")

            self.main_window.after(0, finish)

        def on_error(message: str) -> None:
            def finish() -> None:
                self._hero_processing = False
                state = get_hero_state()
                self.main_window.set_hero_state(state.status, message)

            self.main_window.after(0, finish)

        process_hero_video(on_progress=on_progress, on_complete=on_complete, on_error=on_error)

    def _interval_seconds(self) -> float:
        return self.store.settings.reminder_interval_mins * 60

    def _snooze_seconds(self) -> float:
        return self.store.settings.snooze_mins * 60

    def _schedule_next_reminder(self, delay_seconds: Optional[float] = None) -> None:
        delay = self._interval_seconds() if delay_seconds is None else delay_seconds
        self.next_reminder_at = time.time() + delay

    def _timer_loop(self) -> None:
        while self.running:
            if time.time() >= self.next_reminder_at:
                self.event_queue.put("SHOW_REMINDER")
                self.next_reminder_at = time.time() + 10**9
            time.sleep(1)

    def _poll_queue(self) -> None:
        try:
            while True:
                event = self.event_queue.get_nowait()
                if event == "SHOW_REMINDER":
                    self._show_reminder()
        except queue.Empty:
            pass
        if self.running:
            self.main_window.after(100, self._poll_queue)

    def _hide_main_window(self) -> None:
        if not self.store.settings.onboarding_complete:
            self.store.settings.onboarding_complete = True
            self.store.save()
        self.main_window.withdraw()

    def _show_main_window(self) -> None:
        self.main_window.deiconify()
        self.main_window.lift()
        self.main_window.focus_force()
        self.main_window.refresh()

    def _show_reminder(self) -> None:
        if self.reminder.is_open:
            return
        if not self.animations.ready:
            if self.animations._load_error:
                print(f"Animation load failed: {self.animations._load_error}")
            self._schedule_next_reminder(30)
            return
        self._hide_main_window()
        self.reminder.default_drink_ml = self.store.settings.default_drink_ml
        self.reminder.show()

    def _return_to_background(self) -> None:
        self._refresh_ui()
        self._hide_main_window()

    def _on_drank(self) -> None:
        self.store.add_water(self.store.settings.default_drink_ml)
        self._schedule_next_reminder()
        self._return_to_background()

    def _on_snooze(self) -> None:
        self._schedule_next_reminder(self._snooze_seconds())
        self._return_to_background()

    def _on_dismiss(self) -> None:
        self._schedule_next_reminder()
        self._return_to_background()

    def _on_settings_changed(self) -> None:
        self._schedule_next_reminder()
        self.main_window.after(0, self._refresh_ui)

    def _refresh_ui(self) -> None:
        self.main_window.refresh()

    def _log_from_tray(self) -> None:
        self.store.add_water(250)
        self._refresh_ui()

    def _on_animations_ready(self) -> None:
        self.main_window.set_ready(True)

    def _create_tray_image(self) -> Image.Image:
        logo = create_tray_logo(size=64)
        canvas = Image.new("RGBA", (64, 64), (255, 248, 246, 255))
        x = (64 - logo.width) // 2
        y = (64 - logo.height) // 2
        canvas.paste(logo, (x, y), logo)
        return canvas

    def _build_tray_menu(self):
        import pystray

        return pystray.Menu(
            pystray.MenuItem(
                f"Open {BRAND_NAME} {APP_NAME}",
                lambda: self.main_window.after(0, self._show_main_window),
            ),
            pystray.MenuItem(
                "Log +250 ml",
                lambda: self.main_window.after(0, self._log_from_tray),
            ),
            pystray.MenuItem(
                "Show reminder now",
                lambda: self.main_window.after(0, self._show_reminder),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", lambda: self.main_window.after(0, self.quit)),
        )

    def _start_tray(self) -> None:
        if not self._use_tray:
            return

        try:
            import pystray

            self.tray_icon = pystray.Icon(
                "strawvarie_hydration_hero",
                self._create_tray_image(),
                FULL_TITLE,
                menu=self._build_tray_menu(),
            )
            self._tray_thread = threading.Thread(target=self.tray_icon.run, daemon=True)
            self._tray_thread.start()
        except Exception:
            self._use_tray = False

    def run(self) -> None:
        if self._use_tray:
            self.main_window.after(300, self._start_tray)
        if not self.store.settings.onboarding_complete:
            self.main_window.after(0, self._show_main_window)
        else:
            self.main_window.after(0, self._hide_main_window)
        self.main_window.mainloop()

    def quit(self) -> None:
        self.running = False
        if self.tray_icon is not None:
            self.tray_icon.stop()
        self.main_window.quit()
        self.main_window.destroy()


def main() -> None:
    HydrationHeroApp().run()


if __name__ == "__main__":
    main()
