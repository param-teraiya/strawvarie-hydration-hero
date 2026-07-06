"""Build a single transparent RGBA image for the floating desktop reminder."""

from typing import List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from hydration_hero.brand import COLORS, REMINDER_LINE

OVERLAY_W = 540
OVERLAY_H = 270
FEET_Y = 255
FEET_X = 88
SPRITE_SCALE = 1.12


def _hex_rgb(hex_color: str) -> Tuple[int, int, int]:
    value = hex_color.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def _load_font(size: int, *, bold: bool = False) -> ImageFont.ImageFont:
    if bold:
        candidates = (
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/Library/Fonts/Arial Bold.ttf",
        )
    else:
        candidates = (
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/Library/Fonts/Arial.ttf",
        )
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    max_width: int,
) -> str:
    words = text.split()
    if not words:
        return text

    lines: List[str] = []
    current = words[0]
    for word in words[1:]:
        trial = f"{current} {word}"
        bbox = draw.textbbox((0, 0), trial, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = trial
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return "\n".join(lines)


def _make_cloud_button(
    text: str,
    *,
    width: int,
    height: int,
    fill: Tuple[int, int, int],
    text_fill: Tuple[int, int, int],
    font_size: int = 14,
    bold: bool = True,
    border: Optional[Tuple[int, int, int]] = None,
) -> Image.Image:
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, width - 1, height - 1), radius=height // 2, fill=fill + (255,))
    if border is not None:
        draw.rounded_rectangle(
            (1, 1, width - 2, height - 2),
            radius=height // 2,
            outline=border + (255,),
            width=2,
        )
    font = _load_font(font_size, bold=bold)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    draw.text(
        ((width - text_w) // 2, (height - text_h) // 2 - 1),
        text,
        fill=text_fill + (255,),
        font=font,
    )
    return image


def _make_speech_bubble(text: str, *, max_width: int = 250) -> Image.Image:
    font = _load_font(13, bold=True)
    padding_x = 16
    padding_y = 12
    tail_h = 10

    probe = Image.new("RGBA", (max_width, 200), (0, 0, 0, 0))
    draw = ImageDraw.Draw(probe)
    wrapped = _wrap_text(draw, text, font, max_width - padding_x * 2)
    bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=4)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    bubble_w = text_w + padding_x * 2
    bubble_h = text_h + padding_y * 2

    image = Image.new("RGBA", (bubble_w, bubble_h + tail_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    white = _hex_rgb(COLORS["card"])
    draw.rounded_rectangle((0, 0, bubble_w - 1, bubble_h - 1), radius=14, fill=white + (255,))
    tail_x = max(20, bubble_w // 3)
    draw.polygon(
        [(tail_x - 8, bubble_h - 1), (tail_x + 8, bubble_h - 1), (tail_x, bubble_h + tail_h)],
        fill=white + (255,),
    )
    text_color = _hex_rgb(COLORS["text"])
    draw.multiline_text(
        (padding_x, padding_y),
        wrapped,
        fill=text_color + (255,),
        font=font,
        spacing=4,
    )
    return image


def _in_rect(x: int, y: int, rect: Tuple[int, int, int, int]) -> bool:
    left, top, width, height = rect
    return left <= x < left + width and top <= y < top + height


class OverlayComposer:
    """Lay out speech bubble, cloud buttons, and hero sprite on a transparent canvas."""

    def __init__(self, drink_ml: int) -> None:
        self.drink_ml = drink_ml
        self.size = (OVERLAY_W, OVERLAY_H)
        self.bubble_pos = (44, 6)
        # Buttons sit to the right of the hero — all within the overlay bounds.
        self.drank_rect = (172, 128, 200, 46)
        self.snooze_rect = (384, 128, 118, 46)
        self.dismiss_rect = (286, 192, 108, 34)

        self._bubble = _make_speech_bubble(REMINDER_LINE, max_width=240)
        self._drank = _make_cloud_button(
            "YES, I DRANK",
            width=self.drank_rect[2],
            height=self.drank_rect[3],
            fill=_hex_rgb(COLORS["brand"]),
            text_fill=(255, 255, 255),
            font_size=14,
        )
        self._snooze = _make_cloud_button(
            "SNOOZE",
            width=self.snooze_rect[2],
            height=self.snooze_rect[3],
            fill=_hex_rgb(COLORS["card"]),
            text_fill=_hex_rgb(COLORS["text"]),
            font_size=13,
            border=_hex_rgb(COLORS["card_border"]),
        )
        self._dismiss = _make_cloud_button(
            "Dismiss",
            width=self.dismiss_rect[2],
            height=self.dismiss_rect[3],
            fill=_hex_rgb(COLORS["card"]),
            text_fill=_hex_rgb(COLORS["muted"]),
            font_size=11,
            bold=False,
            border=_hex_rgb(COLORS["card_border"]),
        )

    def hit_test(self, x: int, y: int) -> Optional[str]:
        if _in_rect(x, y, self.drank_rect):
            return "drank"
        if _in_rect(x, y, self.snooze_rect):
            return "snooze"
        if _in_rect(x, y, self.dismiss_rect):
            return "dismiss"
        if x < 200 and y > 40:
            return "drank"
        return None

    def render(
        self,
        sprite: Optional[Image.Image],
        foot_x: int,
        *,
        show_controls: bool = True,
    ) -> Image.Image:
        canvas = Image.new("RGBA", self.size, (0, 0, 0, 0))

        if sprite is not None:
            sprite = sprite.convert("RGBA")
            if SPRITE_SCALE != 1.0:
                width, height = sprite.size
                sprite = sprite.resize(
                    (max(1, int(width * SPRITE_SCALE)), max(1, int(height * SPRITE_SCALE))),
                    Image.NEAREST,
                )
            paste_x = foot_x - sprite.width // 2
            paste_y = FEET_Y - sprite.height
            canvas.paste(sprite, (paste_x, paste_y), sprite.split()[3])

        if show_controls:
            canvas.paste(self._bubble, self.bubble_pos, self._bubble)
            canvas.paste(self._drank, self.drank_rect[:2], self._drank)
            canvas.paste(self._snooze, self.snooze_rect[:2], self._snooze)
            canvas.paste(self._dismiss, self.dismiss_rect[:2], self._dismiss)

        return canvas
