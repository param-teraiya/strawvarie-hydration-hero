import os
import platform
import sys
import tkinter as tk
from typing import Tuple, Union

import customtkinter as ctk

WidgetContainer = Union[ctk.CTkFrame, ctk.CTkScrollableFrame]


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
    """CTkScrollableFrame often renders blank in PyInstaller .app bundles on macOS."""
    return platform.system() == "Darwin"


def nested_frame_color(surface: str) -> str:
    """On macOS, transparent CTkFrame often renders incorrectly."""
    if platform.system() == "Darwin":
        return surface
    return "transparent"


def create_main_container(parent: ctk.CTk, bg_color: str) -> Tuple[WidgetContainer, ctk.CTkFrame]:
    """Return (outer shell, inner content frame). Inner frame is where widgets should pack."""
    if use_mac_scroll_workaround():
        # CTkScrollableFrame (and CTk inside tk Canvas) often renders blank in .app bundles.
        frame = ctk.CTkFrame(parent, fg_color=bg_color)
        frame.pack(fill="both", expand=True, padx=16, pady=16)
        return frame, frame

    scroll = ctk.CTkScrollableFrame(parent, fg_color=bg_color)
    scroll.pack(fill="both", expand=True, padx=16, pady=16)
    fix_scrollable_frame(scroll, bg_color)
    return scroll, scroll


def mac_window_geometry() -> str:
    if use_mac_scroll_workaround():
        return "440x860"
    return "440x720"


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
