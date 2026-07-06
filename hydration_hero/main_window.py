import os
import platform
import subprocess
import webbrowser
from typing import Callable, Dict, Optional, Tuple, Union

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
    format_setting_display,
    open_setup_guide,
)
from hydration_hero.hero import HeroStatus
from hydration_hero.paths import get_user_hero_root
from hydration_hero.storage import SettingsStore
from hydration_hero.ui import (
    accent_strip,
    apply_mac_window_size,
    create_card,
    create_main_container,
    divider,
    font,
    ghost_button,
    nested_frame_color,
    primary_button,
    refresh_main_scroll,
    secondary_button,
    section_header,
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
        self._setting_labels: Dict[str, ctk.CTkLabel] = {}

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

        self._build_header(container)
        if not self.store.settings.onboarding_complete:
            self._build_welcome_banner(container)
        self._build_progress_card(container)
        self._build_hero_card(container)
        self._build_quick_log(container)
        self._build_settings_card(container)
        self._build_footer(container)

    def _build_header(self, container: ctk.CTkFrame) -> None:
        brand_row = ctk.CTkFrame(container, fg_color=nested_frame_color(self.COLORS["bg"]))
        brand_row.pack(fill="x", pady=(0, 12))

        self._logo_image = create_logo_image()
        ctk.CTkLabel(brand_row, text="", image=self._logo_image).pack(anchor="w")

        ctk.CTkLabel(
            brand_row,
            text=APP_NAME,
            font=font("section"),
            text_color=self.COLORS["muted"],
        ).pack(anchor="w", pady=(8, 0))

        ctk.CTkLabel(
            brand_row,
            text=TAGLINE,
            font=font("caption"),
            text_color=self.COLORS["seafoam"],
        ).pack(anchor="w", pady=(2, 0))

        ctk.CTkLabel(
            brand_row,
            text=HERO_LINE,
            font=font("body"),
            text_color=self.COLORS["muted"],
        ).pack(anchor="w", pady=(4, 0))

    def _build_welcome_banner(self, container: ctk.CTkFrame) -> None:
        banner = ctk.CTkFrame(
            container,
            corner_radius=12,
            fg_color=self.COLORS["accent_soft"],
            border_width=1,
            border_color=self.COLORS["brand"],
        )
        banner.pack(fill="x", pady=(0, 14))
        ctk.CTkLabel(
            banner,
            text="Welcome! Log your first drink, set reminders below, then minimize to the dock.",
            font=font("caption"),
            text_color=self.COLORS["text"],
            wraplength=400,
            justify="left",
        ).pack(anchor="w", padx=16, pady=12)

    def _build_progress_card(self, container: ctk.CTkFrame) -> None:
        _card, inner = create_card(container)
        accent_strip(inner)
        ctk.CTkLabel(
            inner,
            text="Today's hydration",
            font=font("section"),
            text_color=self.COLORS["text"],
        ).pack(anchor="w")

        self.amount_label = ctk.CTkLabel(
            inner,
            text="0 / 2000 ml",
            font=font("hero_amount"),
            text_color=self.COLORS["text"],
        )
        self.amount_label.pack(anchor="w", pady=(8, 0))

        self.percent_label = ctk.CTkLabel(
            inner,
            text="0% of daily goal",
            font=font("caption"),
            text_color=self.COLORS["muted"],
        )
        self.percent_label.pack(anchor="w", pady=(2, 12))

        self.progress_bar = ctk.CTkProgressBar(
            inner,
            height=12,
            corner_radius=6,
            progress_color=self.COLORS["progress_fill"],
            fg_color=self.COLORS["progress_bg"],
        )
        self.progress_bar.pack(fill="x")
        self.progress_bar.set(0)

        self.status_label = ctk.CTkLabel(
            inner,
            text="",
            font=font("caption"),
            text_color=self.COLORS["success"],
        )
        self.status_label.pack(anchor="w", pady=(10, 0))

    def _build_hero_card(self, container: ctk.CTkFrame) -> None:
        section_header(
            container,
            "Your hydration hero",
            "Personalize with a Gemini pixel animation, or use the bundled default.",
        )
        _card, hero_inner = create_card(container)

        ghost_button(
            hero_inner,
            text="Open setup guide",
            command=open_setup_guide,
        ).pack(fill="x", pady=(0, 10))

        self.hero_folder_label = ctk.CTkLabel(
            hero_inner,
            text=os.path.join(get_user_hero_root(), "hero.mp4"),
            font=font("small"),
            text_color=self.COLORS["muted"],
            wraplength=400,
            justify="left",
        )
        self.hero_folder_label.pack(anchor="w", pady=(0, 12))

        hero_actions = ctk.CTkFrame(hero_inner, fg_color=nested_frame_color(self.COLORS["card"]))
        hero_actions.pack(fill="x")

        secondary_button(
            hero_actions,
            text="Open hero folder",
            height=38,
            command=self._open_hero_folder,
        ).pack(side="left", expand=True, fill="x", padx=(0, 6))

        self.create_hero_btn = primary_button(
            hero_actions,
            text="Create my hero",
            height=38,
            state="disabled",
            command=self._request_create_hero,
        )
        self.create_hero_btn.pack(side="left", expand=True, fill="x", padx=(6, 0))

        self.hero_status_label = ctk.CTkLabel(
            hero_inner,
            text="",
            font=font("caption"),
            text_color=self.COLORS["seafoam"],
            wraplength=400,
            justify="left",
        )
        self.hero_status_label.pack(anchor="w", pady=(12, 0))

    def _build_quick_log(self, container: ctk.CTkFrame) -> None:
        section_header(container, "Quick log", "Tap to add water to today's total.")

        quick_row = ctk.CTkFrame(container, fg_color=nested_frame_color(self.COLORS["bg"]))
        quick_row.pack(fill="x", pady=(0, 10))
        quick_row.grid_columnconfigure((0, 1, 2), weight=1)

        for col, amount in enumerate((250, 500, 750)):
            secondary_button(
                quick_row,
                text=f"+{amount} ml",
                height=46,
                font=font("body_bold"),
                command=lambda ml=amount: self._log_water(ml),
            ).grid(row=0, column=col, sticky="ew", padx=(0 if col == 0 else 6, 0))

        custom_row = ctk.CTkFrame(container, fg_color=nested_frame_color(self.COLORS["bg"]))
        custom_row.pack(fill="x", pady=(0, 6))

        self.custom_entry = ctk.CTkEntry(
            custom_row,
            placeholder_text="Custom amount (ml)",
            height=44,
            corner_radius=12,
            fg_color=self.COLORS["card"],
            border_color=self.COLORS["card_border"],
            text_color=self.COLORS["text"],
            font=font("body"),
        )
        self.custom_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.custom_entry.bind("<Return>", lambda _e: self._log_custom())

        primary_button(
            custom_row,
            text="Add",
            width=88,
            height=44,
            command=self._log_custom,
        ).pack(side="right")

    def _build_settings_card(self, container: ctk.CTkFrame) -> None:
        section_header(
            container,
            "Reminders & preferences",
            "Adjust goals and how often your hero nudges you.",
        )
        _card, settings_inner = create_card(container)

        settings = [
            ("Daily goal", "How much to drink each day", "daily_goal_ml", (1000, 5000, 250), " ml"),
            ("Reminder every", "Time between nudges", "reminder_interval_mins", (0.5, 120, 0.5), " min"),
            ("Snooze for", "Delay when you snooze", "snooze_mins", (5, 60, 5), " min"),
            ("Default drink", "Logged per sip", "default_drink_ml", (100, 500, 50), " ml"),
        ]
        for index, (label, subtitle, attr, bounds, unit) in enumerate(settings):
            if index > 0:
                divider(settings_inner, pady=10)
            self._add_setting_row(settings_inner, label, subtitle, attr, bounds, unit)

        summary_wrap = ctk.CTkFrame(settings_inner, fg_color=self.COLORS["accent_soft"], corner_radius=12)
        summary_wrap.pack(fill="x", pady=(18, 0))
        self.settings_summary = ctk.CTkLabel(
            summary_wrap,
            text="",
            font=font("small"),
            text_color=self.COLORS["text"],
            wraplength=380,
            justify="left",
        )
        self.settings_summary.pack(anchor="w", padx=14, pady=10)

    def _build_footer(self, container: ctk.CTkFrame) -> None:
        footer = ctk.CTkFrame(container, fg_color=nested_frame_color(self.COLORS["bg"]))
        footer.pack(fill="x", pady=(4, 8))

        primary_button(
            footer,
            text="Preview reminder",
            command=self._request_preview,
        ).pack(fill="x", pady=(0, 8))

        secondary_button(
            footer,
            text="Minimize to dock" if platform.system() == "Darwin" else "Minimize to tray",
            command=self.on_minimize_to_tray,
        ).pack(fill="x", pady=(0, 12))

        ghost_button(
            footer,
            text="Shop tumblers at strawvarie.in →",
            command=lambda: webbrowser.open(WEBSITE),
        ).pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(
            footer,
            text=FOOTER_LINE,
            font=font("small"),
            text_color=self.COLORS["muted"],
        ).pack(anchor="center")

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
            text_color=self.COLORS["brand"] if processing else self.COLORS["seafoam"],
        )

    def set_hero_state(self, status: HeroStatus, message: str) -> None:
        processing = status == HeroStatus.PROCESSING
        can_create = status == HeroStatus.NEEDS_PROCESSING and not processing
        self.refresh_hero_status(message, processing=processing)
        self.create_hero_btn.configure(state="normal" if can_create else "disabled")

    def _add_setting_row(
        self,
        parent: ctk.CTkFrame,
        label: str,
        subtitle: str,
        attr: str,
        bounds: Tuple[Union[int, float], Union[int, float], Union[int, float]],
        unit: str = "",
    ) -> None:
        minimum, maximum, step = bounds
        row = ctk.CTkFrame(parent, fg_color=nested_frame_color(self.COLORS["card"]))
        row.pack(fill="x", pady=2)

        text_col = ctk.CTkFrame(row, fg_color=nested_frame_color(self.COLORS["card"]))
        text_col.pack(side="left", anchor="w")
        ctk.CTkLabel(
            text_col,
            text=label,
            font=font("body_bold"),
            text_color=self.COLORS["text"],
            anchor="w",
        ).pack(anchor="w")
        ctk.CTkLabel(
            text_col,
            text=subtitle,
            font=font("small"),
            text_color=self.COLORS["muted"],
            anchor="w",
        ).pack(anchor="w")

        stepper = ctk.CTkFrame(
            row,
            fg_color=self.COLORS["stepper_bg"],
            corner_radius=999,
            height=40,
        )
        stepper.pack(side="right")
        stepper.pack_propagate(False)

        current_value = getattr(self.store.settings, attr)
        value_label = ctk.CTkLabel(
            stepper,
            text=format_setting_display(current_value, unit),
            font=font("body_bold"),
            text_color=self.COLORS["text"],
            width=78,
        )
        self._setting_labels[attr] = value_label

        def change(delta: Union[int, float]) -> None:
            current = getattr(self.store.settings, attr)
            updated = round(current + delta, 2)
            updated = max(minimum, min(maximum, updated))
            self.store.update(**{attr: updated})
            value_label.configure(text=format_setting_display(updated, unit))
            self.refresh()

        minus = ctk.CTkButton(
            stepper,
            text="−",
            width=34,
            height=34,
            corner_radius=999,
            fg_color=self.COLORS["card"],
            hover_color=self.COLORS["button_secondary_hover"],
            text_color=self.COLORS["text"],
            font=font("section"),
            command=lambda: change(-step),
        )
        minus.pack(side="left", padx=(3, 0), pady=3)
        value_label.pack(side="left")
        plus = ctk.CTkButton(
            stepper,
            text="+",
            width=34,
            height=34,
            corner_radius=999,
            fg_color=self.COLORS["accent"],
            hover_color=self.COLORS["accent_hover"],
            text_color="#FFFFFF",
            font=font("section"),
            command=lambda: change(step),
        )
        plus.pack(side="left", padx=(0, 3), pady=3)

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
            self.status_label.configure(
                text="Goal reached — great job today!",
                text_color=self.COLORS["success"],
            )
        elif remaining > 0:
            self.status_label.configure(
                text=f"{remaining} ml remaining",
                text_color=self.COLORS["muted"],
            )

        interval = format_setting_display(settings.reminder_interval_mins, " min")
        snooze = format_setting_display(settings.snooze_mins, " min")
        drink = format_setting_display(settings.default_drink_ml, " ml")
        self.settings_summary.configure(
            text=f"Reminders every {interval} · Snooze {snooze} · Logs +{drink} per sip",
        )

        for attr, unit in (
            ("daily_goal_ml", " ml"),
            ("reminder_interval_mins", " min"),
            ("snooze_mins", " min"),
            ("default_drink_ml", " ml"),
        ):
            label = self._setting_labels.get(attr)
            if label is not None:
                value = getattr(settings, attr)
                label.configure(text=format_setting_display(value, unit))

    def _handle_close(self) -> None:
        self.on_minimize_to_tray()
