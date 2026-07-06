import tkinter as tk
import webbrowser
from typing import Callable, Optional

import customtkinter as ctk

from hydration_hero.animation import AnimationLibrary, AnimationPlayer
from hydration_hero.brand import BRAND_NAME, COLORS, REMINDER_LINE, WEBSITE, create_logo_image
from hydration_hero.ui import font, ghost_button, nested_frame_color, primary_button, secondary_button


class ReminderPopup:
    def __init__(
        self,
        master: ctk.CTk,
        animations: AnimationLibrary,
        default_drink_ml: int,
        on_drank: Callable[[], None],
        on_snooze: Callable[[], None],
        on_dismiss: Callable[[], None],
    ) -> None:
        self.master = master
        self.animations = animations
        self.default_drink_ml = default_drink_ml
        self.on_drank = on_drank
        self.on_snooze = on_snooze
        self.on_dismiss = on_dismiss
        self.window: Optional[ctk.CTkToplevel] = None
        self.actions: Optional[ctk.CTkFrame] = None
        self.player: Optional[AnimationPlayer] = None
        self._closed = False

    @property
    def is_open(self) -> bool:
        return self.window is not None and not self._closed

    def show(self) -> None:
        if self.is_open:
            return

        self._closed = False
        width, height = 380, 560
        screen_w = self.master.winfo_screenwidth()
        screen_h = self.master.winfo_screenheight()
        x = screen_w - width - 28
        y = screen_h - height - 80

        self.window = ctk.CTkToplevel(self.master)
        self.window.overrideredirect(True)
        self.window.geometry(f"{width}x{height}+{x}+{y}")
        self.window.configure(fg_color=COLORS["reminder_bg"])
        self.window.attributes("-topmost", True)

        shell = ctk.CTkFrame(
            self.window,
            width=width,
            height=height,
            corner_radius=20,
            fg_color=COLORS["card"],
            border_width=1,
            border_color=COLORS["card_border"],
        )
        shell.pack(fill="both", expand=True)
        shell.pack_propagate(False)

        accent = ctk.CTkFrame(shell, height=4, corner_radius=0, fg_color=COLORS["brand"])
        accent.pack(fill="x")

        header = ctk.CTkFrame(shell, fg_color=nested_frame_color(COLORS["card"]))
        header.pack(fill="x", padx=20, pady=(16, 0))

        title_block = ctk.CTkFrame(header, fg_color=nested_frame_color(COLORS["card"]))
        title_block.pack(side="left")

        self._logo_image = create_logo_image(width=160)
        ctk.CTkLabel(title_block, text="", image=self._logo_image).pack(anchor="w")

        ctk.CTkLabel(
            title_block,
            text=f"{BRAND_NAME} · Hydration Hero",
            font=font("small"),
            text_color=COLORS["muted"],
        ).pack(anchor="w", pady=(4, 0))

        ctk.CTkButton(
            header,
            text="✕",
            width=32,
            height=32,
            corner_radius=16,
            fg_color=COLORS["button_secondary"],
            hover_color=COLORS["button_secondary_hover"],
            text_color=COLORS["muted"],
            font=font("body"),
            command=self._handle_dismiss,
        ).pack(side="right")

        ctk.CTkLabel(
            shell,
            text=REMINDER_LINE,
            font=font("section"),
            text_color=COLORS["text"],
            wraplength=320,
            justify="center",
        ).pack(pady=(12, 2))

        ctk.CTkLabel(
            shell,
            text="Your hero is here to help you stay on track.",
            font=font("caption"),
            text_color=COLORS["muted"],
        ).pack(pady=(0, 6))

        canvas = tk.Canvas(
            shell,
            width=300,
            height=250,
            bg=COLORS["reminder_canvas"],
            highlightthickness=0,
            bd=0,
        )
        canvas.pack(pady=(0, 4))

        self.player = AnimationPlayer(canvas, self.animations, center=(150, 125))
        self.player.play("walk_in", 40, on_complete=self._loop_stand)

        ghost_button(
            shell,
            text=f"Shop {BRAND_NAME} tumblers →",
            height=30,
            command=lambda: webbrowser.open(WEBSITE),
        ).pack(pady=(0, 4))

        self.actions = ctk.CTkFrame(shell, fg_color=nested_frame_color(COLORS["card"]))
        self.actions.pack(fill="x", padx=20, pady=(0, 20))

        primary_button(
            self.actions,
            text=f"I drank!  +{self.default_drink_ml} ml",
            height=46,
            command=self._handle_drank,
        ).pack(fill="x", pady=(0, 10))

        row = ctk.CTkFrame(self.actions, fg_color=nested_frame_color(COLORS["card"]))
        row.pack(fill="x")

        secondary_button(
            row,
            text="Snooze",
            height=38,
            command=self._handle_snooze,
        ).pack(side="left", expand=True, fill="x", padx=(0, 6))

        secondary_button(
            row,
            text="Dismiss",
            height=38,
            command=self._handle_dismiss,
        ).pack(side="left", expand=True, fill="x", padx=(6, 0))

    def _loop_stand(self) -> None:
        if self.player and not self._closed:
            self.player.play("stand", 120, loop=True)

    def _handle_drank(self) -> None:
        if self._closed:
            return
        self._close_with_animation(self.on_drank, play_drink=True)

    def _handle_snooze(self) -> None:
        if self._closed:
            return
        self._close_with_animation(self.on_snooze)

    def _handle_dismiss(self) -> None:
        if self._closed:
            return
        self._close_with_animation(self.on_dismiss)

    def _close_with_animation(self, callback: Callable[[], None], *, play_drink: bool = False) -> None:
        self._closed = True
        self._hide_actions()

        if self.player:
            self.player.stop()

        def finish() -> None:
            self._destroy()
            callback()

        if not self.player:
            finish()
            return

        if play_drink:
            self.player.play(
                "drink",
                45,
                on_complete=lambda: self.player.play("walk_out", 40, on_complete=finish)
                if self.player
                else finish(),
            )
        else:
            self.player.play("walk_out", 40, on_complete=finish)

    def _hide_actions(self) -> None:
        if self.actions is not None:
            self.actions.pack_forget()

    def _destroy(self) -> None:
        if self.window is not None:
            self.window.destroy()
            self.window = None
        self.actions = None
        self.player = None
