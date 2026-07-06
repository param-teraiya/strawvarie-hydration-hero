import platform
import os
import subprocess
import webbrowser
from typing import Callable, Optional, Tuple, Union

import customtkinter as ctk

from hydration_hero.brand import (
    APP_NAME,
    COLORS,
    FOOTER_LINE,
    FULL_TITLE,
    HERO_LINE,
    TAGLINE,
    WEBSITE,
    create_logo_image,
    open_setup_guide,
)
from hydration_hero.hero import HeroStatus
from hydration_hero.paths import HERO_FOLDER_NAME, get_user_hero_root
from hydration_hero.storage import SettingsStore
from hydration_hero.ui import (
    apply_mac_window_size,
    create_main_container,
    nested_frame_color,
    refresh_main_scroll,
)


class MainWindow(ctk.CTk):
    COLORS = COLORS

    def __init__(
        self,
        store: SettingsStore,
        on_minimize_to_tray: Callable[[], None],
        on_preview_reminder: Optional[Callable[[], None]] = None,
        on_create_hero: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__()
        self.store = store
        self.on_minimize_to_tray = on_minimize_to_tray
        self._preview_callback = on_preview_reminder
        self._create_hero_callback = on_create_hero

        self.title(FULL_TITLE)
        self.configure(fg_color=self.COLORS["bg"])
        apply_mac_window_size(self)

        self._build_ui()
        refresh_main_scroll(self)
        self.refresh()
        self.protocol("WM_DELETE_WINDOW", self._handle_close)
        self.update_idletasks()
        self.after(300, lambda: refresh_main_scroll(self))

    def _build_ui(self) -> None:
        _shell, container = create_main_container(self, self.COLORS["bg"])

        brand_row = ctk.CTkFrame(container, fg_color=nested_frame_color(self.COLORS["bg"]))
        brand_row.pack(fill="x", pady=(0, 16))

        self._logo_image = create_logo_image(width=210)
        ctk.CTkLabel(
            brand_row,
            text="",
            image=self._logo_image,
        ).pack(anchor="w")

        ctk.CTkLabel(
            brand_row,
            text=APP_NAME,
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=self.COLORS["text"],
        ).pack(anchor="w", pady=(8, 0))

        ctk.CTkLabel(
            brand_row,
            text=TAGLINE,
            font=ctk.CTkFont(size=12),
            text_color=self.COLORS["seafoam"],
        ).pack(anchor="w", pady=(2, 0))

        ctk.CTkLabel(
            brand_row,
            text=HERO_LINE,
            font=ctk.CTkFont(size=13),
            text_color=self.COLORS["muted"],
        ).pack(anchor="w", pady=(6, 0))

        self.progress_card = ctk.CTkFrame(
            container,
            corner_radius=18,
            fg_color=self.COLORS["card"],
            border_width=1,
            border_color=self.COLORS["card_border"],
        )
        self.progress_card.pack(fill="x", pady=(0, 16))

        inner = ctk.CTkFrame(self.progress_card, fg_color=nested_frame_color(self.COLORS["card"]))
        inner.pack(fill="x", padx=20, pady=20)

        self.amount_label = ctk.CTkLabel(
            inner,
            text="0 / 2000 ml",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=self.COLORS["text"],
        )
        self.amount_label.pack(anchor="w")

        self.percent_label = ctk.CTkLabel(
            inner,
            text="0% of daily goal",
            font=ctk.CTkFont(size=13),
            text_color=self.COLORS["muted"],
        )
        self.percent_label.pack(anchor="w", pady=(4, 12))

        self.progress_bar = ctk.CTkProgressBar(
            inner,
            height=14,
            corner_radius=8,
            progress_color=self.COLORS["progress_fill"],
            fg_color=self.COLORS["progress_bg"],
        )
        self.progress_bar.pack(fill="x")
        self.progress_bar.set(0)

        self.status_label = ctk.CTkLabel(
            inner,
            text="",
            font=ctk.CTkFont(size=12),
            text_color=self.COLORS["success"],
        )
        self.status_label.pack(anchor="w", pady=(10, 0))

        hero_card = ctk.CTkFrame(
            container,
            corner_radius=18,
            fg_color=self.COLORS["card"],
            border_width=1,
            border_color=self.COLORS["card_border"],
        )
        hero_card.pack(fill="x", pady=(0, 16))

        hero_inner = ctk.CTkFrame(hero_card, fg_color=nested_frame_color(self.COLORS["card"]))
        hero_inner.pack(fill="x", padx=20, pady=20)

        ctk.CTkLabel(
            hero_inner,
            text="Your hydration hero",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=self.COLORS["text"],
        ).pack(anchor="w")

        ctk.CTkLabel(
            hero_inner,
            text="Follow the setup guide to create your pixel hero with Gemini, then drop hero.mp4 here.",
            font=ctk.CTkFont(size=12),
            text_color=self.COLORS["muted"],
            wraplength=360,
            justify="left",
        ).pack(anchor="w", pady=(6, 8))

        ctk.CTkButton(
            hero_inner,
            text="Open setup guide (step-by-step)",
            height=34,
            corner_radius=10,
            fg_color=self.COLORS["button_secondary"],
            hover_color=self.COLORS["button_secondary_hover"],
            text_color=self.COLORS["accent"],
            border_width=1,
            border_color=self.COLORS["card_border"],
            command=open_setup_guide,
        ).pack(fill="x", pady=(0, 10))

        self.hero_folder_label = ctk.CTkLabel(
            hero_inner,
            text=f"~/ {HERO_FOLDER_NAME} / hero.mp4",
            font=ctk.CTkFont(size=11),
            text_color=self.COLORS["text"],
            wraplength=360,
            justify="left",
        )
        self.hero_folder_label.pack(anchor="w", pady=(0, 10))

        hero_actions = ctk.CTkFrame(hero_inner, fg_color=nested_frame_color(self.COLORS["card"]))
        hero_actions.pack(fill="x")

        ctk.CTkButton(
            hero_actions,
            text="Open hero folder",
            height=36,
            corner_radius=10,
            fg_color=self.COLORS["button_secondary"],
            hover_color=self.COLORS["button_secondary_hover"],
            text_color=self.COLORS["text"],
            command=self._open_hero_folder,
        ).pack(side="left", expand=True, fill="x", padx=(0, 6))

        self.create_hero_btn = ctk.CTkButton(
            hero_actions,
            text="Create my hero",
            height=36,
            corner_radius=10,
            fg_color=self.COLORS["accent"],
            hover_color=self.COLORS["accent_hover"],
            state="disabled",
            command=self._request_create_hero,
        )
        self.create_hero_btn.pack(side="left", expand=True, fill="x", padx=(6, 0))

        self.hero_status_label = ctk.CTkLabel(
            hero_inner,
            text="",
            font=ctk.CTkFont(size=12),
            text_color=self.COLORS["seafoam"],
            wraplength=360,
            justify="left",
        )
        self.hero_status_label.pack(anchor="w", pady=(10, 0))

        ctk.CTkLabel(
            container,
            text="Quick log",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=self.COLORS["text"],
        ).pack(anchor="w", pady=(0, 8))

        quick_row = ctk.CTkFrame(container, fg_color=nested_frame_color(self.COLORS["bg"]))
        quick_row.pack(fill="x", pady=(0, 12))
        quick_row.grid_columnconfigure((0, 1, 2), weight=1)

        for col, amount in enumerate((250, 500, 750)):
            ctk.CTkButton(
                quick_row,
                text=f"+{amount} ml",
                height=44,
                corner_radius=12,
                fg_color=self.COLORS["button_secondary"],
                hover_color=self.COLORS["button_secondary_hover"],
                text_color=self.COLORS["text"],
                command=lambda ml=amount: self._log_water(ml),
            ).grid(row=0, column=col, sticky="ew", padx=(0 if col == 0 else 6, 0))

        custom_row = ctk.CTkFrame(container, fg_color=nested_frame_color(self.COLORS["bg"]))
        custom_row.pack(fill="x", pady=(0, 20))

        self.custom_entry = ctk.CTkEntry(
            custom_row,
            placeholder_text="Custom amount (ml)",
            height=42,
            corner_radius=12,
            fg_color=self.COLORS["card"],
            border_color=self.COLORS["card_border"],
            text_color=self.COLORS["text"],
        )
        self.custom_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        ctk.CTkButton(
            custom_row,
            text="Add",
            width=80,
            height=42,
            corner_radius=12,
            fg_color=self.COLORS["accent"],
            hover_color=self.COLORS["accent_hover"],
            command=self._log_custom,
        ).pack(side="right")

        if platform.system() == "Darwin":
            ctk.CTkLabel(
                container,
                text="Scroll down for Settings · Preview · Minimize to dock ↓",
                font=ctk.CTkFont(size=11),
                text_color=self.COLORS["muted"],
            ).pack(anchor="w", pady=(0, 10))

        settings_card = ctk.CTkFrame(
            container,
            corner_radius=18,
            fg_color=self.COLORS["card"],
            border_width=1,
            border_color=self.COLORS["card_border"],
        )
        settings_card.pack(fill="x", pady=(0, 16))

        settings_inner = ctk.CTkFrame(settings_card, fg_color=nested_frame_color(self.COLORS["card"]))
        settings_inner.pack(fill="x", padx=20, pady=20)

        ctk.CTkLabel(
            settings_inner,
            text="Settings",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=self.COLORS["text"],
        ).pack(anchor="w", pady=(0, 12))

        self._add_setting_row(settings_inner, "Daily goal (ml)", "daily_goal_ml", (1000, 5000, 250))
        self._add_setting_row(
            settings_inner,
            "Reminder every (min)",
            "reminder_interval_mins",
            (0.5, 120, 0.5),
        )
        self._add_setting_row(settings_inner, "Snooze (min)", "snooze_mins", (5, 60, 5))
        self._add_setting_row(settings_inner, "Default drink (ml)", "default_drink_ml", (100, 500, 50))

        footer = ctk.CTkFrame(container, fg_color=nested_frame_color(self.COLORS["bg"]))
        footer.pack(fill="x")

        ctk.CTkButton(
            footer,
            text="Preview reminder",
            height=40,
            corner_radius=12,
            fg_color=self.COLORS["accent"],
            hover_color=self.COLORS["accent_hover"],
            command=self._request_preview,
        ).pack(fill="x", pady=(0, 8))

        ctk.CTkButton(
            footer,
            text="Minimize to tray" if platform.system() != "Darwin" else "Minimize to dock",
            height=40,
            corner_radius=12,
            fg_color=self.COLORS["button_secondary"],
            hover_color=self.COLORS["button_secondary_hover"],
            text_color=self.COLORS["text"],
            command=self.on_minimize_to_tray,
        ).pack(fill="x", pady=(0, 12))

        ctk.CTkButton(
            footer,
            text="Shop tumblers at strawvarie.in →",
            height=36,
            corner_radius=12,
            fg_color=self.COLORS["button_secondary"],
            hover_color=self.COLORS["button_secondary_hover"],
            text_color=self.COLORS["accent"],
            command=lambda: webbrowser.open(WEBSITE),
        ).pack(fill="x", pady=(0, 4))

        ctk.CTkLabel(
            footer,
            text=FOOTER_LINE,
            font=ctk.CTkFont(size=11),
            text_color=self.COLORS["muted"],
        ).pack(anchor="w")

    def set_ready(self, ready: bool) -> None:
        if ready:
            self._flash_status("Hero is ready!")

    def _request_preview(self) -> None:
        if self._preview_callback:
            self._preview_callback()

    def _request_create_hero(self) -> None:
        if self._create_hero_callback:
            self._create_hero_callback()

    def _open_hero_folder(self) -> None:
        folder = get_user_hero_root()
        os.makedirs(folder, exist_ok=True)
        if platform.system() == "Darwin":
            subprocess.run(["open", folder], check=False)
        elif platform.system() == "Windows":
            os.startfile(folder)  # noqa: S606
        else:
            subprocess.run(["xdg-open", folder], check=False)

    def refresh_hero_status(self, message: str, *, processing: bool = False) -> None:
        self.hero_folder_label.configure(text=os.path.join(get_user_hero_root(), "hero.mp4"))
        self.hero_status_label.configure(
            text=message,
            text_color=self.COLORS["accent"] if processing else self.COLORS["seafoam"],
        )

    def set_hero_state(self, status: HeroStatus, message: str) -> None:
        processing = status == HeroStatus.PROCESSING
        can_create = status == HeroStatus.NEEDS_PROCESSING and not processing
        self.refresh_hero_status(message, processing=processing)
        self.create_hero_btn.configure(state="normal" if can_create else "disabled")

    @staticmethod
    def _format_setting_value(value: Union[int, float]) -> str:
        if isinstance(value, float) and not value.is_integer():
            return str(value).rstrip("0").rstrip(".")
        return str(int(value))

    def _add_setting_row(
        self,
        parent: ctk.CTkFrame,
        label: str,
        attr: str,
        bounds: Tuple[Union[int, float], Union[int, float], Union[int, float]],
    ) -> None:
        minimum, maximum, step = bounds
        row = ctk.CTkFrame(parent, fg_color=nested_frame_color(self.COLORS["card"]))
        row.pack(fill="x", pady=6)

        ctk.CTkLabel(
            row,
            text=label,
            font=ctk.CTkFont(size=13),
            text_color=self.COLORS["muted"],
        ).pack(side="left")

        current_value = getattr(self.store.settings, attr)
        value_label = ctk.CTkLabel(
            row,
            text=self._format_setting_value(current_value),
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=self.COLORS["text"],
            width=60,
        )
        value_label.pack(side="right")

        def change(delta: Union[int, float]) -> None:
            current = getattr(self.store.settings, attr)
            updated = round(current + delta, 2)
            updated = max(minimum, min(maximum, updated))
            self.store.update(**{attr: updated})
            value_label.configure(text=self._format_setting_value(updated))
            self.refresh()

        btn_frame = ctk.CTkFrame(row, fg_color=nested_frame_color(self.COLORS["card"]))
        btn_frame.pack(side="right", padx=(8, 0))

        ctk.CTkButton(
            btn_frame,
            text="−",
            width=30,
            height=28,
            corner_radius=8,
            fg_color=self.COLORS["button_secondary"],
            hover_color=self.COLORS["button_secondary_hover"],
            text_color=self.COLORS["text"],
            command=lambda: change(-step),
        ).pack(side="left", padx=(0, 4))

        ctk.CTkButton(
            btn_frame,
            text="+",
            width=30,
            height=28,
            corner_radius=8,
            fg_color=self.COLORS["button_secondary"],
            hover_color=self.COLORS["button_secondary_hover"],
            text_color=self.COLORS["text"],
            command=lambda: change(step),
        ).pack(side="left")

    def _log_water(self, amount_ml: int) -> None:
        self.store.add_water(amount_ml)
        self.refresh()
        self._flash_status(f"+{amount_ml} ml logged")

    def _log_custom(self) -> None:
        raw = self.custom_entry.get().strip()
        if not raw.isdigit():
            self._flash_status("Enter a valid number", success=False)
            return
        amount = int(raw)
        if amount <= 0:
            self._flash_status("Amount must be positive", success=False)
            return
        self.custom_entry.delete(0, "end")
        self._log_water(amount)

    def _flash_status(self, message: str, *, success: bool = True) -> None:
        color = self.COLORS["success"] if success else "#D46A6A"
        self.status_label.configure(text=message, text_color=color)
        self.after(2500, lambda: self.status_label.configure(text=""))

    def refresh(self) -> None:
        settings = self.store.settings
        settings.reset_if_new_day()
        progress = settings.progress
        self.amount_label.configure(text=f"{settings.today_ml} / {settings.daily_goal_ml} ml")
        self.percent_label.configure(text=f"{int(progress * 100)}% of daily goal")
        self.progress_bar.set(progress)

        remaining = max(settings.daily_goal_ml - settings.today_ml, 0)
        if progress >= 1.0:
            self.status_label.configure(text="Goal reached! Great job today.", text_color=self.COLORS["success"])
        elif remaining > 0:
            self.status_label.configure(text=f"{remaining} ml to go", text_color=self.COLORS["muted"])

    def _handle_close(self) -> None:
        self.on_minimize_to_tray()
