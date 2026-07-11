#!/usr/bin/env python3
"""Procedurally generate placeholder pixel-art characters + app icons.

These are clean, intentional placeholders. Real characters get commissioned
later (see docs/character-brief.md) — the atlas/manifest format they slot into
is defined here and never changes.

Run:  ../../venv/bin/python generate_assets.py   (needs Pillow)
Outputs:
  public/characters/<id>/atlas.png + manifest.json   (3 characters)
  src-tauri/icons/*                                    (app + tray icons)
"""
import json
import os
import subprocess
import sys

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.dirname(HERE)
CHAR_DIR = os.path.join(APP, "public", "characters")
ICON_DIR = os.path.join(APP, "src-tauri", "icons")

# --- sprite geometry ---------------------------------------------------------
GW, GH = 40, 48          # logical pixel grid per frame
SCALE = 4                # each logical pixel -> 4x4 block (crisp NEAREST upscale)
FW, FH = GW * SCALE, GH * SCALE   # 160 x 192 atlas frame
STATES = ["idle", "walk", "drink"]
FRAMES = 2               # every state has 2 frames

INK = (43, 43, 48, 255)
WHITE = (255, 255, 255, 255)
CUP = (185, 194, 199, 255)
CUP_DARK = (138, 150, 156, 255)
CHEEK = (255, 158, 158, 200)

PALETTE = {
    "drip":   dict(body=(89, 166, 201, 255),  dark=(62, 134, 168, 255),  shine=(205, 234, 243, 255)),
    "berry":  dict(body=(226, 74, 74, 255),   dark=(184, 54, 54, 255),   shine=(244, 208, 107, 255)),
    "sprout": dict(body=(99, 176, 116, 255),  dark=(71, 145, 90, 255),   shine=(150, 214, 168, 255)),
}

META = {
    "drip":   dict(name="Drip",   blurb="A cheerful little water droplet."),
    "berry":  dict(name="Berry",  blurb="The Strawvarie mascot, always thirsty for more."),
    "sprout": dict(name="Sprout", blurb="A leafy sprout that grows when you hydrate."),
}


def new_frame():
    return Image.new("RGBA", (GW, GH), (0, 0, 0, 0))


def face(d, cx, cy, eyes_closed, kind):
    """Eyes + smile centered near (cx, cy)."""
    if eyes_closed:
        d.line([(cx - 6, cy), (cx - 3, cy + 1)], fill=INK, width=1)
        d.line([(cx + 3, cy + 1), (cx + 6, cy)], fill=INK, width=1)
    else:
        for ex in (cx - 5, cx + 5):
            d.ellipse([ex - 2, cy - 2, ex + 2, cy + 2], fill=WHITE)
            d.ellipse([ex - 1, cy - 1, ex + 1, cy + 1], fill=INK)
    # rosy cheeks
    d.ellipse([cx - 9, cy + 2, cx - 6, cy + 4], fill=CHEEK)
    d.ellipse([cx + 6, cy + 2, cx + 9, cy + 4], fill=CHEEK)
    # smile
    d.arc([cx - 3, cy + 2, cx + 3, cy + 7], start=10, end=170, fill=INK, width=1)


def feet(d, cx, foot_y, spread):
    d.ellipse([cx - 8 - spread, foot_y, cx - 2 - spread, foot_y + 3], fill=INK)
    d.ellipse([cx + 2 + spread, foot_y, cx + 8 + spread, foot_y + 3], fill=INK)


def cup(d, cx, cy):
    d.rounded_rectangle([cx - 4, cy - 6, cx + 4, cy + 3], radius=2, fill=CUP, outline=CUP_DARK)
    d.rectangle([cx - 4, cy - 6, cx + 4, cy - 5], fill=CUP_DARK)  # lid rim


def draw_drip(d, cx, cy, pal):
    d.ellipse([cx - 12, cy - 4, cx + 12, cy + 18], fill=pal["body"], outline=pal["dark"])
    d.polygon([(cx, cy - 22), (cx - 9, cy + 2), (cx + 9, cy + 2)], fill=pal["body"])
    d.polygon([(cx, cy - 22), (cx - 9, cy + 2), (cx + 9, cy + 2)], outline=pal["dark"])
    d.ellipse([cx - 7, cy - 8, cx - 2, cy - 2], fill=pal["shine"])  # shine


def draw_berry(d, cx, cy, pal):
    # leafy crown
    for lx in (-7, 0, 7):
        d.polygon([(cx + lx, cy - 20), (cx + lx - 4, cy - 12), (cx + lx + 4, cy - 12)],
                  fill=(91, 168, 106, 255))
    # body: rounded top + pointed bottom
    d.ellipse([cx - 12, cy - 14, cx + 12, cy + 8], fill=pal["body"], outline=pal["dark"])
    d.polygon([(cx - 11, cy + 2), (cx + 11, cy + 2), (cx, cy + 20)], fill=pal["body"])
    d.polygon([(cx - 11, cy + 2), (cx + 11, cy + 2), (cx, cy + 20)], outline=pal["dark"])
    # seeds
    for sx, sy in [(-6, 6), (6, 6), (0, 11), (-4, 14), (4, 14), (-8, 0), (8, 0)]:
        d.ellipse([cx + sx - 1, cy + sy - 1, cx + sx + 1, cy + sy + 1], fill=pal["shine"])


def draw_sprout(d, cx, cy, pal):
    # two leaves up top
    d.ellipse([cx - 10, cy - 20, cx - 1, cy - 10], fill=pal["shine"], outline=pal["dark"])
    d.ellipse([cx + 1, cy - 20, cx + 10, cy - 10], fill=(124, 203, 140, 255), outline=pal["dark"])
    d.line([(cx, cy - 12), (cx, cy - 4)], fill=pal["dark"], width=1)
    # round body
    d.ellipse([cx - 12, cy - 6, cx + 12, cy + 18], fill=pal["body"], outline=pal["dark"])
    d.ellipse([cx - 7, cy, cx - 2, cy + 6], fill=pal["shine"])


DRAW = {"drip": draw_drip, "berry": draw_berry, "sprout": draw_sprout}


def render_frame(kind, state, frame):
    img = new_frame()
    d = ImageDraw.Draw(img)
    pal = PALETTE[kind]
    bob = -1 if frame == 1 else 0                 # gentle vertical bob
    cx, cy = 20, 22 + bob
    foot_y = 40 + bob

    DRAW[kind](d, cx, cy, pal)

    if state == "walk":
        feet(d, cx, foot_y, spread=(2 if frame == 1 else 0))
    else:
        feet(d, cx, foot_y, spread=0)

    if state == "drink":
        cup(d, cx + (3 if frame == 1 else 5), cy + 5)
        face(d, cx, cy, eyes_closed=(frame == 1), kind=kind)
    else:
        face(d, cx, cy, eyes_closed=False, kind=kind)

    return img.resize((FW, FH), Image.NEAREST)


def build_character(kind):
    atlas = Image.new("RGBA", (FW * FRAMES, FH * len(STATES)), (0, 0, 0, 0))
    for row, state in enumerate(STATES):
        for col in range(FRAMES):
            atlas.paste(render_frame(kind, state, col), (col * FW, row * FH))
    out = os.path.join(CHAR_DIR, kind)
    os.makedirs(out, exist_ok=True)
    atlas.save(os.path.join(out, "atlas.png"))
    manifest = {
        "schema": 1,
        "id": kind,
        "name": META[kind]["name"],
        "blurb": META[kind]["blurb"],
        "frameWidth": FW,
        "frameHeight": FH,
        "anchorX": FW // 2,
        "anchorY": 176,
        "states": {
            "idle":  {"row": 0, "frames": FRAMES, "fps": 2, "loop": True},
            "walk":  {"row": 1, "frames": FRAMES, "fps": 8, "loop": True},
            "drink": {"row": 2, "frames": FRAMES, "fps": 3, "loop": False},
        },
        "poster": {"state": "idle", "index": 0},
    }
    with open(os.path.join(out, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"  character: {kind} -> {out}")


# --- icons -------------------------------------------------------------------
def droplet_shape(d, cx, cy, r, color, outline=None):
    d.ellipse([cx - r, cy - r * 0.7, cx + r, cy + r * 1.1], fill=color, outline=outline, width=6)
    d.polygon([(cx, cy - r * 1.9), (cx - r * 0.85, cy - r * 0.1), (cx + r * 0.85, cy - r * 0.1)],
              fill=color)


def build_icons():
    os.makedirs(ICON_DIR, exist_ok=True)
    S = 1024
    master = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(master)
    # rounded seafoam background with a soft vertical gradient
    bg = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    bd = ImageDraw.Draw(bg)
    for y in range(S):
        t = y / S
        col = (int(143 - t * 40), int(203 - t * 40), int(175 - t * 38), 255)
        bd.line([(0, y), (S, y)], fill=col)
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, S, S], radius=int(S * 0.22), fill=255)
    master.paste(bg, (0, 0), mask)
    # white droplet
    droplet_shape(d, S // 2, int(S * 0.56), int(S * 0.24), WHITE)
    # tiny shine
    d.ellipse([int(S * 0.42), int(S * 0.44), int(S * 0.49), int(S * 0.53)], fill=(255, 255, 255, 90))

    master.save(os.path.join(ICON_DIR, "icon.png"))
    for size, name in [(32, "32x32.png"), (128, "128x128.png"), (256, "128x128@2x.png")]:
        master.resize((size, size), Image.LANCZOS).save(os.path.join(ICON_DIR, name))
    # windows .ico
    master.resize((256, 256), Image.LANCZOS).save(
        os.path.join(ICON_DIR, "icon.ico"),
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    # macOS .icns via iconutil
    iconset = os.path.join(ICON_DIR, "icon.iconset")
    os.makedirs(iconset, exist_ok=True)
    for base in (16, 32, 128, 256, 512):
        master.resize((base, base), Image.LANCZOS).save(os.path.join(iconset, f"icon_{base}x{base}.png"))
        master.resize((base * 2, base * 2), Image.LANCZOS).save(
            os.path.join(iconset, f"icon_{base}x{base}@2x.png"))
    if sys.platform == "darwin":
        subprocess.run(["iconutil", "-c", "icns", iconset, "-o",
                        os.path.join(ICON_DIR, "icon.icns")], check=True)

    # tray icon: seafoam droplet with a dark edge — legible on light + dark bars
    tray = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    td = ImageDraw.Draw(tray)
    droplet_shape(td, 32, 36, 16, (95, 160, 140, 255), outline=(40, 60, 52, 255))
    tray.save(os.path.join(ICON_DIR, "tray.png"))
    tray.resize((32, 32), Image.LANCZOS).save(os.path.join(ICON_DIR, "tray-32.png"))
    print(f"  icons -> {ICON_DIR}")


def main():
    os.makedirs(CHAR_DIR, exist_ok=True)
    print("Generating characters...")
    for kind in PALETTE:
        build_character(kind)
    print("Generating icons...")
    build_icons()
    print("Done.")


if __name__ == "__main__":
    main()
