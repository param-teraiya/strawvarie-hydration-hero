# -*- mode: python ; coding: utf-8 -*-
import glob

from PyInstaller.utils.hooks import collect_all

block_cipher = None

ctk_datas, ctk_binaries, ctk_hiddenimports = collect_all("customtkinter")

datas = list(ctk_datas)
datas.append(("hydration_hero/assets/strawvarie_logo.png", "hydration_hero/assets"))
datas.append(("hydration_hero/assets/guide.html", "hydration_hero/assets"))

for frame_path in sorted(glob.glob("heroes/male/frame_*.png")):
    datas.append((frame_path, "heroes/male"))

hiddenimports = list(ctk_hiddenimports) + [
    "PIL._tkinter_finder",
    "numpy",
    "cv2",
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
    upx=True,
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
    upx=True,
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
