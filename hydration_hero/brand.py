import os
import webbrowser
from pathlib import Path

from PIL import Image
import customtkinter as ctk

from hydration_hero.paths import get_guide_path, get_logo_path

WEBSITE = "https://strawvarie.in"
LOGO_URL = "https://strawvarie.in/cdn/shop/files/Strawverry_png2_micro.png?v=1709924729&width=260"
BRAND_NAME = "Strawvarie"
APP_NAME = "Hydration Hero"
FULL_TITLE = f"{BRAND_NAME} · {APP_NAME}"

TAGLINE = "Sustainable at Heart"
HERO_LINE = "Fill your tumbler. Stay refreshed."
REMINDER_LINE = "Time to sip from your Strawvarie!"
FOOTER_LINE = "We just sell tumblers! The good ones."

COLORS = {
    "bg": "#FFF8F6",
    "card": "#FFFFFF",
    "card_border": "#F0E4E8",
    "accent": "#C9567A",
    "accent_hover": "#B24568",
    "text": "#2F2433",
    "muted": "#8B7E8A",
    "progress_bg": "#F3E8EC",
    "progress_fill": "#E8A0B4",
    "success": "#5FA892",
    "seafoam": "#A8CBB7",
    "button_secondary": "#F3EEF0",
    "button_secondary_hover": "#E8DFE3",
    "reminder_bg": "#FFF8F6",
    "reminder_canvas": "#FFF8F6",
}


def create_logo_image(width: int = 210) -> ctk.CTkImage:
    try:
        image = Image.open(get_logo_path())
    except OSError:
        placeholder = Image.new("RGBA", (width, max(1, width // 4)), (201, 86, 122, 255))
        return ctk.CTkImage(
            light_image=placeholder,
            dark_image=placeholder,
            size=(width, max(1, width // 4)),
        )
    height = max(1, int(width * image.height / image.width))
    return ctk.CTkImage(light_image=image, dark_image=image, size=(width, height))


def create_tray_logo(size: int = 64) -> Image.Image:
    image = Image.open(get_logo_path()).convert("RGBA")
    width = size
    height = max(1, int(size * image.height / image.width))
    return image.resize((width, height), Image.LANCZOS)


def open_setup_guide() -> None:
    guide = Path(get_guide_path()).resolve()
    if guide.is_file():
        webbrowser.open(guide.as_uri())
