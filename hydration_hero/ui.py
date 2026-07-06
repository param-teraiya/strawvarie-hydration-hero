import platform

import customtkinter as ctk


def init_customtkinter() -> None:
    """Configure CustomTkinter before any windows are created."""
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")
    if platform.system() == "Darwin":
        ctk.set_widget_scaling(1.0)
        ctk.set_window_scaling(1.0)


def nested_frame_color(surface: str) -> str:
    """On macOS, transparent CTkFrame often renders as solid black."""
    if platform.system() == "Darwin":
        return surface
    return "transparent"


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
