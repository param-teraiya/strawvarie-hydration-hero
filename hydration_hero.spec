# -*- mode: python ; coding: utf-8 -*-
import glob
import os
import sys

from PyInstaller.utils.hooks import collect_all

block_cipher = None

ctk_datas, ctk_binaries, ctk_hiddenimports = collect_all("customtkinter")

datas = list(ctk_datas)


def _add_data(source: str, destination: str) -> bool:
    if os.path.isfile(source):
        datas.append((source, destination))
        return True
    return False


def _bundle_first_match(pairs):
    for source, destination in pairs:
        if _add_data(source, destination):
            return
    print("ERROR: Missing bundled asset. Expected one of:", file=sys.stderr)
    for source, _destination in pairs:
        print(f"  - {source}", file=sys.stderr)
    raise SystemExit(1)


_bundle_first_match(
    [
        ("assets/brand/strawvarie_logo.png", "assets/brand"),
        ("hydration_hero/assets/strawvarie_logo.png", "hydration_hero/assets"),
    ]
)
for extra_asset in ("assets/brand/strawvarie_logo_inverse.png", "assets/brand/strawvarie_logo.svg"):
    if os.path.isfile(extra_asset):
        datas.append((extra_asset, "assets/brand"))
_bundle_first_match(
    [
        ("assets/guide/guide.html", "assets/guide"),
        ("hydration_hero/assets/guide.html", "hydration_hero/assets"),
    ]
)

frame_paths = sorted(
    set(
        glob.glob("heroes/male/frames/frame_*.png")
        + glob.glob("heroes/male/frame_*.png")
    )
)
if not frame_paths:
    print(
        "ERROR: No hero frames found.\n"
        "       Run: python scripts/extract_default_frames.py\n"
        "       (requires heroes/male/default_hero.mp4 from git)",
        file=sys.stderr,
    )
    raise SystemExit(1)

for frame_path in frame_paths:
    destination = os.path.dirname(frame_path)
    datas.append((frame_path, destination))

hiddenimports = list(ctk_hiddenimports) + [
    "PIL._tkinter_finder",
    "numpy",
    "cv2",
    "customtkinter.windows.widgets",
    "customtkinter.windows.widgets.theme",
    "objc",
    "AppKit",
    "Foundation",
    "hydration_hero.overlay_composer",
    "hydration_hero.overlay_subprocess",
    "hydration_hero.overlay_worker",
]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=list(ctk_binaries),
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Strawvarie Hydration Hero",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Strawvarie Hydration Hero",
)

app = BUNDLE(
    coll,
    name="Strawvarie Hydration Hero.app",
    icon=None,
    bundle_identifier="in.strawvarie.hydrationhero",
    info_plist={
        "CFBundleName": "Strawvarie Hydration Hero",
        "CFBundleDisplayName": "Strawvarie Hydration Hero",
        "NSHighResolutionCapable": True,
    },
)
