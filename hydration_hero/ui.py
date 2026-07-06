import os
import platform
import sys
import tkinter as tk
from typing import Optional, Tuple, Union

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
    """Use tk Canvas scrolling on macOS — CTkScrollableFrame trackpad support is unreliable."""
    return platform.system() == "Darwin"


def _wheel_step(event: tk.Event) -> int:
    if not event.delta:
        return 0
    if platform.system() == "Darwin":
        if abs(event.delta) >= 120:
            return int(-event.delta / 120)
        return int(-event.delta) or (-1 if event.delta > 0 else 1)
    return int(-event.delta / 120) or (-1 if event.delta > 0 else 1)


class MacScrollContainer:
    """Reliable scroll area for macOS — canvas + scrollbar on the main window."""

    def __init__(self, parent: ctk.CTk, bg_color: str) -> None:
        self._parent = parent
        self._bg_color = bg_color
        self.outer = ctk.CTkFrame(parent, fg_color=bg_color)
        self.outer.pack(fill="both", expand=True, padx=20, pady=(12, 16))

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
            fg_color=bg_color,
            button_color=COLORS["divider"],
            button_hover_color=COLORS["muted"],
        )
        self.inner = ctk.CTkFrame(self.canvas, fg_color=bg_color)

        self._window_id = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y", padx=(4, 0))

        self.inner.bind("<Configure>", self._sync_scroll_region)
        self.canvas.bind("<Configure>", self._sync_inner_width)
        parent.bind_all("<MouseWheel>", self._on_wheel_global, add="+")
        parent.bind_all("<Button-4>", self._on_wheel_global, add="+")
        parent.bind_all("<Button-5>", self._on_wheel_global, add="+")
        parent.after(150, self._sync_scroll_region)

    def _sync_scroll_region(self, _event=None) -> None:
        self.canvas.update_idletasks()
        bbox = self.canvas.bbox("all")
        if bbox:
            self.canvas.configure(scrollregion=(bbox[0], bbox[1], bbox[2], bbox[3] + 40))

    def _sync_inner_width(self, event: tk.Event) -> None:
        self.canvas.itemconfigure(self._window_id, width=event.width)

    def _is_over_dashboard(self, widget: Optional[tk.Widget]) -> bool:
        current = widget
        while current is not None:
            if current in (self.inner, self.outer, self.canvas):
                return True
            if current == self._parent:
                return True
            current = current.master if hasattr(current, "master") else None
        return False

    def _on_wheel_global(self, event: tk.Event) -> Optional[str]:
        try:
            widget = self._parent.winfo_containing(
                self._parent.winfo_pointerx(),
                self._parent.winfo_pointery(),
            )
        except tk.TclError:
            return None
        if not self._is_over_dashboard(widget):
            return None
        self._on_wheel(event)
        return "break"

    def _on_wheel(self, event: tk.Event) -> None:
        step = _wheel_step(event)
        if step:
            self.canvas.yview_scroll(step, "units")
        elif event.num == 4:
            self.canvas.yview_scroll(-3, "units")
        elif event.num == 5:
            self.canvas.yview_scroll(3, "units")


def _attach_scroll_handlers(root: ctk.CTk, scroll: ctk.CTkScrollableFrame) -> None:
    """Ensure trackpad / mouse-wheel scrolling works over all dashboard widgets."""
    canvas = scroll._parent_canvas

    def _scroll(event: tk.Event) -> str:
        step = _wheel_step(event)
        if step:
            canvas.yview_scroll(step, "units")
        elif event.num == 4:
            canvas.yview_scroll(-3, "units")
        elif event.num == 5:
            canvas.yview_scroll(3, "units")
        return "break"

    def _scroll_if_over_content(event: tk.Event) -> Optional[str]:
        try:
            widget = root.winfo_containing(root.winfo_pointerx(), root.winfo_pointery())
        except tk.TclError:
            return None
        if widget is None:
            return None
        current: Optional[tk.Widget] = widget
        while current is not None:
            if current == scroll:
                return _scroll(event)
            current = current.master if hasattr(current, "master") else None
        return None

    root.bind_all("<MouseWheel>", _scroll_if_over_content, add="+")
    root.bind_all("<Button-4>", _scroll_if_over_content, add="+")
    root.bind_all("<Button-5>", _scroll_if_over_content, add="+")
    canvas.bind("<MouseWheel>", _scroll, add="+")
    scroll.bind("<MouseWheel>", _scroll, add="+")


def create_main_container(parent: ctk.CTk, bg_color: str) -> Tuple[WidgetContainer, ctk.CTkFrame]:
    """Return (outer shell, inner content frame). Pack widgets into the inner frame."""
    if use_mac_scroll_workaround():
        scroll = MacScrollContainer(parent, bg_color)
        parent._mac_scroll = scroll  # type: ignore[attr-defined]
        return scroll.outer, scroll.inner

    scroll = ctk.CTkScrollableFrame(
        parent,
        fg_color=bg_color,
        scrollbar_fg_color=bg_color,
        scrollbar_button_color=COLORS["divider"],
        scrollbar_button_hover_color=COLORS["muted"],
    )
    scroll.pack(fill="both", expand=True, padx=20, pady=(12, 16))
    fix_scrollable_frame(scroll, bg_color)
    _attach_scroll_handlers(parent, scroll)
    parent._scroll_frame = scroll  # type: ignore[attr-defined]
    return scroll, scroll


def apply_mac_window_size(window: ctk.CTk) -> None:
    """Size and center the main dashboard window."""
    width = CONTENT_WIDTH
    window.update_idletasks()
    screen_h = window.winfo_screenheight()
    height = min(720, max(600, screen_h - 120))
    center_window(window, width, height)
    window.minsize(420, 580)


def nested_frame_color(surface: str) -> str:
    """On macOS, transparent CTkFrame often renders incorrectly."""
    if platform.system() == "Darwin":
        return surface
    return "transparent"


def center_window(window: ctk.CTk, width: int, height: int) -> None:
    window.update_idletasks()
    screen_w = window.winfo_screenwidth()
    screen_h = window.winfo_screenheight()
    x = max(0, (screen_w - width) // 2)
    y = max(0, (screen_h - height) // 2 - 24)
    window.geometry(f"{width}x{height}+{x}+{y}")


def section_header(parent: ctk.CTkFrame, title: str, subtitle: str = "") -> None:
    block = ctk.CTkFrame(parent, fg_color=nested_frame_color(COLORS["bg"]))
    block.pack(fill="x", pady=(8, 12))
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
            wraplength=CONTENT_WIDTH - 80,
            justify="left",
        ).pack(fill="x", pady=(4, 0))


def create_card(parent: ctk.CTkFrame, *, pady: Tuple[int, int] = (0, 16)) -> Tuple[ctk.CTkFrame, ctk.CTkFrame]:
    card = ctk.CTkFrame(
        parent,
        corner_radius=CARD_RADIUS,
        fg_color=COLORS["card"],
        border_width=1,
        border_color=COLORS["card_border"],
    )
    card.pack(fill="x", pady=pady)
    inner = ctk.CTkFrame(card, fg_color=nested_frame_color(COLORS["card"]))
    inner.pack(fill="x", padx=22, pady=20)
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
    mac_scroll = getattr(window, "_mac_scroll", None)
    if mac_scroll is not None:
        mac_scroll._sync_scroll_region()
        return

    scroll = getattr(window, "_scroll_frame", None)
    if scroll is None:
        return
    scroll.update_idletasks()
    canvas = scroll._parent_canvas
    bbox = canvas.bbox("all")
    if bbox:
        canvas.configure(scrollregion=(bbox[0], bbox[1], bbox[2], bbox[3] + 40))


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


def make_overlay_transparent(window) -> Optional[str]:
    """Make a frameless window's background transparent so only sprites show.

    Returns the color name to use for transparent widget backgrounds, or None
    if the current platform cannot render a per-pixel transparent overlay.
    """

    def _set_bg(color: str) -> None:
        # Bypass CustomTkinter's configure() override (it rejects raw ``bg``)
        # by talking to the underlying Tk widget directly.
        window.tk.call(window._w, "configure", "-background", color)

    system = platform.system()
    if system == "Darwin":
        try:
            window.wm_attributes("-transparent", True)
            _set_bg("systemTransparent")
            return "systemTransparent"
        except Exception:
            return None
    if system == "Windows":
        try:
            magic = "#010203"
            window.wm_attributes("-transparentcolor", magic)
            _set_bg(magic)
            return magic
        except Exception:
            return None
    return None


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
