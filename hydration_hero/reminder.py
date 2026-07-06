import platform
import tkinter as tk
from typing import Callable, Optional, Tuple

import customtkinter as ctk
from PIL import Image, ImageDraw

from hydration_hero.animation import AnimationLibrary, ScenePlayer
from hydration_hero.brand import COLORS, REMINDER_LINE
from hydration_hero.overlay_composer import FEET_X, FEET_Y, OVERLAY_H, OVERLAY_W, OverlayComposer
from hydration_hero.platform_compat import macos_overlay_fallback_reason, supports_macos_native_overlay

WALK_IN_DELAY_MS = 40
WALK_IN_START_X = -130
WALK_OUT_END_X = OVERLAY_W + 110
CARD_WALK_IN_START_X = -60
from hydration_hero.ui import font, nested_frame_color, primary_button, secondary_button

POPUP_W = 380
POPUP_H = 430
SCENE_W = 340
SCENE_H = 200
CARD_FOOT_X = 118
CARD_FOOT_Y = SCENE_H - 6


def _hex_rgb(hex_color: str) -> Tuple[int, int, int]:
    value = hex_color.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def make_scene(width: int, height: int) -> Image.Image:
    """Soft seafoam gradient — gives the hero a place to stand."""
    top = _hex_rgb(COLORS["accent_soft"])
    bottom = _hex_rgb(COLORS["seafoam"])
    image = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(image)
    for y in range(height):
        t = y / max(height - 1, 1)
        color = (
            int(top[0] + (bottom[0] - top[0]) * t),
            int(top[1] + (bottom[1] - top[1]) * t),
            int(top[2] + (bottom[2] - top[2]) * t),
        )
        draw.line([(0, y), (width, y)], fill=color)
    draw.ellipse((width // 2 - 52, height - 22, width // 2 + 28, height - 6), fill=(120, 150, 130))
    return image


class ReminderPopup:
    def __init__(
        self,
        master: ctk.CTk,
        animations: AnimationLibrary,
        default_drink_ml: int,
        on_drank: Callable[[], None],
        on_snooze: Callable[[], None],
        on_dismiss: Callable[[], None],
        dispatch_to_main: Optional[Callable[[Callable[[], None]], None]] = None,
    ) -> None:
        self.master = master
        self.animations = animations
        self.default_drink_ml = default_drink_ml
        self.on_drank = on_drank
        self.on_snooze = on_snooze
        self.on_dismiss = on_dismiss
        self._dispatch_to_main = dispatch_to_main
        self.window: Optional[ctk.CTkToplevel] = None
        self.actions: Optional[ctk.CTkFrame] = None
        self.player: Optional[ScenePlayer] = None
        self._overlay = None
        self._composer: Optional[OverlayComposer] = None
        self._anim_after: Optional[str] = None
        self._anim_running = False
        self._anim_generation = 0
        self._closing = False
        self._closed = False

    @property
    def is_open(self) -> bool:
        return self._overlay is not None or (self.window is not None and not self._closed)

    def show(self) -> None:
        if self.is_open:
            return

        if platform.system() == "Darwin":
            if supports_macos_native_overlay():
                try:
                    self._show_macos_overlay()
                    return
                except ImportError as exc:
                    print(f"macOS overlay unavailable, using card fallback: {exc}")
            else:
                reason = macos_overlay_fallback_reason()
                if reason:
                    print(f"Using card reminder: {reason}")

        self._show_card()

    def _show_macos_overlay(self) -> None:
        from hydration_hero.overlay_subprocess import SubprocessOverlayWindow

        self._closed = False
        self._closing = False
        self._composer = OverlayComposer(self.default_drink_ml)
        screen_w = self.master.winfo_screenwidth()
        screen_h = self.master.winfo_screenheight()
        x = screen_w - OVERLAY_W - 32
        y = screen_h - OVERLAY_H - 48

        try:
            self._overlay = SubprocessOverlayWindow(
                self.master,
                OVERLAY_W,
                OVERLAY_H,
                x,
                y,
                on_click=self._handle_overlay_click,
                dispatch_to_main=self._dispatch_to_main,
            )
        except Exception as exc:
            print(f"macOS overlay unavailable, using card fallback: {exc}")
            self._overlay = None
            self._composer = None
            self._show_card()
            return

        self._start_overlay_entrance()

    def _start_overlay_entrance(self) -> None:
        if self._overlay is None or self._composer is None:
            return

        frames = self.animations.get("walk_in")
        if frames and frames[0] is not None:
            image = self._composer.render(frames[0], WALK_IN_START_X, show_controls=True)
            self._overlay.set_image(image)

        self._play_overlay_animation(
            "walk_in",
            WALK_IN_DELAY_MS,
            motion_x=(WALK_IN_START_X, FEET_X),
            on_complete=self._loop_overlay_stand,
        )

    def _handle_overlay_click(self, x: int, y: int) -> None:
        if self._closing or self._composer is None or self._overlay is None:
            return
        action = self._composer.hit_test(x, y)
        if action == "drank":
            self._handle_drank()
        elif action == "snooze":
            self._handle_snooze()
        elif action == "dismiss":
            self._handle_dismiss()

    def _play_overlay_animation(
        self,
        name: str,
        delay_ms: int,
        *,
        loop: bool = False,
        on_complete: Optional[Callable[[], None]] = None,
        motion_x: Optional[Tuple[int, int]] = None,
        show_controls: bool = True,
    ) -> None:
        if self._overlay is None or self._composer is None:
            return

        frames = self.animations.get(name)
        if not frames:
            if on_complete:
                on_complete()
            return

        self._stop_overlay_animation()
        self._anim_running = True
        generation = self._anim_generation
        frame_count = len(frames)

        def step(index: int) -> None:
            if not self._anim_running or generation != self._anim_generation:
                return
            if self._overlay is None:
                return

            if index < frame_count:
                frame = frames[index]
                foot_x = FEET_X
                if motion_x is not None and frame_count > 1:
                    start_x, end_x = motion_x
                    progress = index / (frame_count - 1)
                    foot_x = int(start_x + (end_x - start_x) * progress)
                image = self._composer.render(frame, foot_x, show_controls=show_controls)
                self._overlay.set_image(image)
                self._anim_after = self.master.after(delay_ms, lambda idx=index: step(idx + 1))
                return

            if loop:
                self._anim_after = self.master.after(delay_ms, lambda: step(0))
                return

            if on_complete:
                on_complete()

        step(0)

    def _loop_overlay_stand(self) -> None:
        if not self._closing and self._overlay is not None:
            self._play_overlay_animation("stand", 120, loop=True)

    def _stop_overlay_animation(self) -> None:
        self._anim_running = False
        self._anim_generation += 1
        if self._anim_after is not None:
            try:
                self.master.after_cancel(self._anim_after)
            except Exception:
                pass
            self._anim_after = None

    def _show_card(self) -> None:
        self._closed = False
        screen_w = self.master.winfo_screenwidth()
        screen_h = self.master.winfo_screenheight()
        x = screen_w - POPUP_W - 28
        y = screen_h - POPUP_H - 72

        self.window = ctk.CTkToplevel(self.master)
        self.window.overrideredirect(True)
        self.window.geometry(f"{POPUP_W}x{POPUP_H}+{x}+{y}")
        self.window.configure(fg_color=COLORS["reminder_bg"])
        self.window.attributes("-topmost", True)

        shell = ctk.CTkFrame(
            self.window,
            width=POPUP_W,
            height=POPUP_H,
            corner_radius=20,
            fg_color=COLORS["card"],
            border_width=1,
            border_color=COLORS["card_border"],
        )
        shell.pack(fill="both", expand=True)
        shell.pack_propagate(False)

        ctk.CTkFrame(shell, height=4, corner_radius=0, fg_color=COLORS["brand"]).pack(fill="x")

        ctk.CTkLabel(
            shell,
            text=REMINDER_LINE,
            font=font("body_bold"),
            text_color=COLORS["text"],
            wraplength=300,
            justify="center",
        ).pack(pady=(14, 10))

        scene_frame = ctk.CTkFrame(
            shell,
            width=SCENE_W,
            height=SCENE_H,
            corner_radius=14,
            fg_color=COLORS["accent_soft"],
        )
        scene_frame.pack(pady=(0, 12))
        scene_frame.pack_propagate(False)

        scene_canvas = tk.Canvas(
            scene_frame,
            width=SCENE_W,
            height=SCENE_H,
            bg=COLORS["accent_soft"],
            highlightthickness=0,
            bd=0,
        )
        scene_canvas.pack()

        self.player = ScenePlayer(
            scene_canvas,
            self.animations,
            make_scene(SCENE_W, SCENE_H),
            foot_y=CARD_FOOT_Y,
            foot_x=CARD_FOOT_X,
        )
        self.player.play(
            "walk_in",
            WALK_IN_DELAY_MS,
            motion_x=(CARD_WALK_IN_START_X, CARD_FOOT_X),
            on_complete=self._loop_stand,
        )

        self.actions = ctk.CTkFrame(shell, fg_color=nested_frame_color(COLORS["card"]))
        self.actions.pack(fill="x", padx=20, pady=(0, 18))

        row = ctk.CTkFrame(self.actions, fg_color=nested_frame_color(COLORS["card"]))
        row.pack(fill="x", pady=(0, 8))

        primary_button(
            row,
            text=f"I drank!  +{self.default_drink_ml} ml",
            height=42,
            command=self._handle_drank,
        ).pack(side="left", expand=True, fill="x", padx=(0, 6))

        secondary_button(
            row,
            text="Snooze",
            height=42,
            command=self._handle_snooze,
        ).pack(side="left", expand=True, fill="x", padx=(6, 0))

        secondary_button(
            self.actions,
            text="Dismiss",
            height=34,
            command=self._handle_dismiss,
        ).pack(fill="x")

    def _loop_stand(self) -> None:
        if self.player and not self._closed:
            self.player.play("stand", 120, loop=True)

    def _handle_drank(self) -> None:
        if self._closing:
            return
        self._close_with_animation(self.on_drank, play_drink=True)

    def _handle_snooze(self) -> None:
        if self._closing:
            return
        self._close_with_animation(self.on_snooze)

    def _handle_dismiss(self) -> None:
        if self._closing:
            return
        self._close_with_animation(self.on_dismiss)

    def _close_with_animation(self, callback: Callable[[], None], *, play_drink: bool = False) -> None:
        if self._closing:
            return
        self._closing = True
        self._hide_actions()
        self._stop_overlay_animation()

        if self.player:
            self.player.stop()

        def finish() -> None:
            self._destroy()
            callback()

        if self._overlay is not None:
            if play_drink:
                self._play_overlay_animation("drink", 45, show_controls=False, on_complete=finish)
            else:
                self._play_overlay_animation(
                    "walk_out",
                    WALK_IN_DELAY_MS,
                    motion_x=(FEET_X, WALK_OUT_END_X),
                    show_controls=False,
                    on_complete=finish,
                )
            return

        if not self.player:
            finish()
            return

        if play_drink:
            self.player.play("drink", 45, on_complete=finish)
        else:
            self.player.play(
                "walk_out",
                WALK_IN_DELAY_MS,
                motion_x=(CARD_FOOT_X, SCENE_W + 60),
                on_complete=finish,
            )

    def _hide_actions(self) -> None:
        if self.actions is not None:
            self.actions.pack_forget()

    def _destroy(self) -> None:
        if self._overlay is not None:
            self._overlay.close()
            self._overlay = None
        self._composer = None
        self._closing = False
        self._closed = True
        if self.window is not None:
            self.window.destroy()
            self.window = None
        self.actions = None
        self.player = None
