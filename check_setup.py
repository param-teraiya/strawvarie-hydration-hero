#!/usr/bin/env python3
"""Run this on the other Mac to see why Hydration Hero may not start."""

import glob
import importlib
import os
import platform
import sys

os.environ.setdefault("TK_SILENCE_DEPRECATION", "1")

ROOT = os.path.dirname(os.path.abspath(__file__))
PACKAGES = ("customtkinter", "PIL", "numpy", "pystray")


def ok(label: str) -> None:
    print(f"  OK   {label}")


def fail(label: str, detail: str = "") -> None:
    print(f"  FAIL {label}")
    if detail:
        print(f"       {detail}")


def warn(label: str, detail: str = "") -> None:
    print(f"  WARN {label}")
    if detail:
        print(f"       {detail}")


def main() -> None:
    print("=" * 60)
    print("Hydration Hero setup check")
    print("=" * 60)

    print("\n[System]")
    print(f"  Platform: {platform.platform()}")
    print(f"  Machine:  {platform.machine()}")

    print("\n[Python]")
    print(f"  Executable: {sys.executable}")
    print(f"  Version:    {sys.version.split()[0]}")
    in_venv = hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
    if in_venv:
        ok("Running inside a virtual environment")
    else:
        warn("Not in a virtual environment", "Run: source venv/bin/activate")

    if sys.executable.startswith("/usr/bin/"):
        warn("Using macOS system Python", "Install python.org Python and recreate venv")

    print("\n[Dependencies]")
    for name in PACKAGES:
        try:
            importlib.import_module(name)
            ok(name)
        except ImportError as exc:
            fail(name, str(exc))

    print("\n[Tk / GUI]")
    try:
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()
        patch = str(root.tk.call("info", "patchlevel"))
        root.update_idletasks()
        root.destroy()
        ok(f"Tk patchlevel {patch}")
        if patch.startswith("8.5."):
            warn("Old Tk 8.5 detected", "UI may be blank. Use python.org Python.")
    except Exception as exc:
        fail("Tkinter window test", str(exc))

    print("\n[Project files]")
    logo = os.path.join(ROOT, "hydration_hero", "assets", "strawvarie_logo.png")
    if os.path.exists(logo):
        ok("Strawvarie logo")
    else:
        fail("Strawvarie logo missing", logo)

    hero_dir = os.path.join(ROOT, "heroes", "male")
    default_video = os.path.join(hero_dir, "default_hero.mp4")
    frames = glob.glob(os.path.join(hero_dir, "frame_*.png"))
    if len(frames) >= 10:
        ok(f"Animation frames ({len(frames)} in heroes/male/)")
    elif frames:
        warn(f"Only {len(frames)} frame files found", "Expected ~239 frames")
    elif os.path.isfile(default_video):
        fail("Default hero frames not extracted", hero_dir)
        print("       Run: python scripts/extract_default_frames.py")
    else:
        fail("Missing default hero video", default_video)

    main_py = os.path.join(ROOT, "main.py")
    if os.path.exists(main_py):
        ok("main.py")
    else:
        fail("main.py missing")

    print("\n[Quick GUI smoke test]")
    try:
        import customtkinter as ctk

        app = ctk.CTk()
        app.title("Hydration Hero test")
        app.geometry("320x120")
        ctk.CTkLabel(app, text="If you can see this window, GUI works.").pack(pady=30)
        app.after(1500, app.destroy)
        app.mainloop()
        ok("CustomTkinter window opened")
    except Exception as exc:
        fail("CustomTkinter window test", str(exc))

    print("\n" + "=" * 60)
    print("Send this full output if the app still does not work.")
    print("=" * 60)


if __name__ == "__main__":
    main()
