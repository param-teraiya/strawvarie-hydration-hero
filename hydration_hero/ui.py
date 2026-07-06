import os
import platform
import sys
import tkinter as tk
from typing import Tuple, Union

import customtkinter as ctk

from hydration_hero.brand import CARD_RADIUS, COLORS, CONTENT_WIDTH, FONTS

WidgetContainer = Union[ctk.CTkFrame, ctk.CTkScrollableFrame]


def font(name: str) -> ctk.CTkFont:
    family, size, *rest = FONTS[name]
    weight = rest[0] if rest else "normal"
    return ctk.CTkFont(size=size, weight=weight)


def init_customtkinter() -> None:
    """Configure CustomTkinter before any windows are created."""
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")
    if platform.system() == "Darwin":
        ctk.set_widget_scaling(1.0)
        ctk.set_window_scaling(1.0)
        try:
            ctk.deactivate_automatic_dpi_awareness()
        except Exception:
            pass


def use_mac_scroll_workaround() -> bool:
    """Use tk Canvas scrolling instead of CTkScrollableFrame on macOS."""
    return platform.system() == "Darwin"


def nested_frame_color(surface: str) -> str:
    """On macOS, transparent CTkFrame often renders incorrectly."""
    if platform.system() == "Darwin":
        return surface
    return "transparent"


class MacScrollContainer:
    """Reliable scroll area for macOS (.app bundles and python.org Tk 8.6)."""

    def __init__(self, parent: ctk.CTk, bg_color: str) -> None:
        self._parent = parent
        self._bg_color = bg_color
        self.outer = ctk.CTkFrame(parent, fg_color=bg_color)
        self.outer.pack(fill="both", expand=True, padx=16, pady=16)

        self.canvas = tk.Canvas(
            self.outer,
            bg=bg_color,
            highlightthickness=0,
            bd=0,
        )
        self.scrollbar = ctk.CTkScrollbar(
            self.outer,
            orientation="vertical",
            command=self.canvas.yview,
        )
        self.inner = ctk.CTkFrame(self.canvas, fg_color=bg_color)

        self._window_id = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.inner.bind("<Configure>", self._sync_scroll_region)
        self.canvas.bind("<Configure>", self._sync_inner_width)
        self.canvas.bind("<Enter>", self._bind_wheel)
        self.canvas.bind("<Leave>", self._unbind_wheel)
        parent.after(150, self._sync_scroll_region)

    def _sync_scroll_region(self, _event=None) -> None:
        self.canvas.update_idletasks()
        bbox = self.canvas.bbox("all")
        if bbox:
            self.canvas.configure(scrollregion=bbox)

    def _sync_inner_width(self, event: tk.Event) -> None:
        self.canvas.itemconfigure(self._window_id, width=event.width)

    def _on_wheel(self, event: tk.Event) -> None:
        if event.delta:
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        elif event.num == 4:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self.canvas.yview_scroll(1, "units")

    def _bind_wheel(self, _event=None) -> None:
        self.canvas.bind_all("<MouseWheel>", self._on_wheel, add="+")
        self.canvas.bind_all("<Button-4>", self._on_wheel, add="+")
        self.canvas.bind_all("<Button-5>", self._on_wheel, add="+")

    def _unbind_wheel(self, _event=None) -> None:
        self.canvas.unbind_all("<MouseWheel>")
        self.canvas.unbind_all("<Button-4>")
        self.canvas.unbind_all("<Button-5>")


def create_main_container(parent: ctk.CTk, bg_color: str) -> Tuple[WidgetContainer, ctk.CTkFrame]:
    """Return (outer shell, inner content frame). Pack widgets into the inner frame."""
    if use_mac_scroll_workaround():
        scroll = MacScrollContainer(parent, bg_color)
        parent._mac_scroll = scroll  # type: ignore[attr-defined]
        return scroll.outer, scroll.inner

    scroll = ctk.CTkScrollableFrame(parent, fg_color=bg_color)
    scroll.pack(fill="both", expand=True, padx=16, pady=16)
    fix_scrollable_frame(scroll, bg_color)
    return scroll, scroll


def apply_mac_window_size(window: ctk.CTk) -> None:
    """Size and center the main dashboard window."""
    width = CONTENT_WIDTH
    if not use_mac_scroll_workaround():
        center_window(window, width, 720)
        window.minsize(400, 560)
        return

    window.update_idletasks()
    screen_h = window.winfo_screenheight()
    height = min(920, max(700, screen_h - 80))
    center_window(window, width, height)
    window.minsize(400, 560)


def center_window(window: ctk.CTk, width: int, height: int) -> None:
    window.update_idletasks()
    screen_w = window.winfo_screenwidth()
    screen_h = window.winfo_screenheight()
    x = max(0, (screen_w - width) // 2)
    y = max(0, (screen_h - height) // 2 - 24)
    window.geometry(f"{width}x{height}+{x}+{y}")


def section_header(parent: ctk.CTkFrame, title: str, subtitle: str = "") -> None:
    block = ctk.CTkFrame(parent, fg_color=nested_frame_color(COLORS["bg"]))
    block.pack(fill="x", pady=(0, 10))
    ctk.CTkLabel(
        block,
        text=title,
        font=font("section"),
        text_color=COLORS["text"],
        anchor="w",
    ).pack(fill="x")
    if subtitle:
        ctk.CTkLabel(
            block,
            text=subtitle,
            font=font("caption"),
            text_color=COLORS["muted"],
            anchor="w",
            wraplength=CONTENT_WIDTH - 64,
            justify="left",
        ).pack(fill="x", pady=(2, 0))


def create_card(parent: ctk.CTkFrame) -> Tuple[ctk.CTkFrame, ctk.CTkFrame]:
    card = ctk.CTkFrame(
        parent,
        corner_radius=CARD_RADIUS,
        fg_color=COLORS["card"],
        border_width=1,
        border_color=COLORS["card_border"],
    )
    card.pack(fill="x", pady=(0, 14))
    inner = ctk.CTkFrame(card, fg_color=nested_frame_color(COLORS["card"]))
    inner.pack(fill="x", padx=20, pady=18)
    return card, inner


def divider(parent: ctk.CTkFrame, *, pady: int = 8) -> None:
    ctk.CTkFrame(parent, height=1, fg_color=COLORS["divider"]).pack(fill="x", pady=pady)


def accent_strip(parent: ctk.CTkFrame, height: int = 4) -> None:
    strip = ctk.CTkFrame(parent, height=height, corner_radius=2, fg_color=COLORS["brand"])
    strip.pack(fill="x", pady=(0, 12))


def primary_button(parent, **kwargs) -> ctk.CTkButton:
    defaults = {
        "height": 42,
        "corner_radius": 12,
        "fg_color": COLORS["accent"],
        "hover_color": COLORS["accent_hover"],
        "text_color": "#FFFFFF",
        "font": font("body_bold"),
    }
    defaults.update(kwargs)
    return ctk.CTkButton(parent, **defaults)


def secondary_button(parent, **kwargs) -> ctk.CTkButton:
    defaults = {
        "height": 40,
        "corner_radius": 12,
        "fg_color": COLORS["button_secondary"],
        "hover_color": COLORS["button_secondary_hover"],
        "text_color": COLORS["text"],
        "font": font("body"),
    }
    defaults.update(kwargs)
    return ctk.CTkButton(parent, **defaults)


def ghost_button(parent, **kwargs) -> ctk.CTkButton:
    defaults = {
        "height": 36,
        "corner_radius": 10,
        "fg_color": COLORS["button_secondary"],
        "hover_color": COLORS["button_secondary_hover"],
        "text_color": COLORS["link"],
        "font": font("caption"),
    }
    defaults.update(kwargs)
    return ctk.CTkButton(parent, **defaults)


def refresh_main_scroll(window: ctk.CTk) -> None:
    """Recalculate scroll area after all widgets are packed."""
    scroll = getattr(window, "_mac_scroll", None)
    if scroll is not None:
        scroll._sync_scroll_region()


def fix_scrollable_frame(frame: ctk.CTkScrollableFrame, bg_color: str) -> None:
    """Fix black canvas background inside CTkScrollableFrame on macOS."""
    if platform.system() != "Darwin":
        return
    try:
        frame.configure(
            fg_color=bg_color,
            scrollbar_fg_color=bg_color,
            scrollbar_button_color=bg_color,
            scrollbar_button_hover_color=bg_color,
        )
    except Exception:
        pass
    try:
        frame._parent_canvas.configure(background=bg_color, highlightthickness=0)
    except Exception:
        pass
    try:
        frame._parent_frame.configure(fg_color=bg_color)
    except Exception:
        pass


def verify_frozen_assets() -> None:
    """Show a visible error if bundled assets are missing from the .app."""
    if not getattr(sys, "frozen", False):
        return

    import glob

    from hydration_hero.paths import get_default_frame_dir, get_logo_path

    missing = []
    logo_path = get_logo_path()
    if not os.path.isfile(logo_path):
        missing.append(logo_path)

    frame_dir = get_default_frame_dir()
    frame_count = len(glob.glob(os.path.join(frame_dir, "frame_*.png")))
    if frame_count < 40:
        missing.append(f"{frame_dir} ({frame_count} frame_*.png, need 40+)")

    if not missing:
        return

    from tkinter import messagebox

    root = tk.Tk()
    root.withdraw()
    messagebox.showerror(
        "Strawvarie Hydration Hero",
        "Bundled assets are missing from this build:\n\n"
        + "\n".join(missing)
        + "\n\nRebuild with ./build_mac.sh after git pull.",
    )
    root.destroy()
    raise SystemExit(1)
