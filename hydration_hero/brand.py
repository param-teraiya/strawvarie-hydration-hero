import webbrowser
from pathlib import Path
from typing import Union

from PIL import Image
import customtkinter as ctk

from hydration_hero.paths import get_guide_path, get_logo_path

WEBSITE = "https://strawvarie.in"
BRAND_NAME = "Strawvarie"
APP_NAME = "Hydration Hero"
FULL_TITLE = f"{BRAND_NAME} · {APP_NAME}"

TAGLINE = "Sustainable at Heart"
HERO_LINE = "Fill your tumbler. Stay refreshed."
REMINDER_LINE = "Time to sip from your Strawvarie tumbler"
FOOTER_LINE = "We just sell tumblers! The good ones."

# Matches strawvarie.in — clean, minimal, sustainable; charcoal CTAs, seafoam eco accent
COLORS = {
    "bg": "#F6F6F4",
    "card": "#FFFFFF",
    "card_border": "#EAEAE6",
    "accent": "#28282B",
    "accent_hover": "#3A3A3E",
    "accent_soft": "#EEF3F0",
    "brand": "#7AB69A",
    "brand_hover": "#689F84",
    "text": "#28282B",
    "muted": "#8A8A85",
    "progress_bg": "#ECEFEC",
    "progress_fill": "#7AB69A",
    "success": "#5FA892",
    "seafoam": "#A8CBB7",
    "button_secondary": "#F1F1EF",
    "button_secondary_hover": "#E6E6E2",
    "reminder_bg": "#F6F6F4",
    "reminder_canvas": "#FFFFFF",
    "divider": "#EDEDE9",
    "link": "#5FA892",
    "field_bg": "#F5F5F3",
    "stepper_bg": "#F1F1EF",
}

CARD_RADIUS = 18
CONTENT_WIDTH = 460
LOGO_WIDTH = 220

FONTS = {
    "title": ("", 18, "bold"),
    "section": ("", 15, "bold"),
    "body": ("", 13),
    "body_bold": ("", 13, "bold"),
    "caption": ("", 12),
    "small": ("", 11),
    "hero_amount": ("", 26, "bold"),
}


def create_logo_image(width: int = LOGO_WIDTH) -> ctk.CTkImage:
    try:
        image = Image.open(get_logo_path()).convert("RGBA")
    except OSError:
        placeholder = Image.new("RGBA", (width, max(1, width // 6)), (26, 26, 26, 255))
        return ctk.CTkImage(
            light_image=placeholder,
            dark_image=placeholder,
            size=(width, max(1, width // 6)),
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


def format_setting_display(value: Union[int, float], unit: str = "") -> str:
    if isinstance(value, float) and not value.is_integer():
        text = str(value).rstrip("0").rstrip(".")
    else:
        text = str(int(value))
    return f"{text}{unit}" if unit else text
