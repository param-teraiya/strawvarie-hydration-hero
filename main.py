#!/usr/bin/env python3
"""Strawvarie Hydration Hero — desktop water reminder with animated companion."""

import os
import sys

os.environ.setdefault("TK_SILENCE_DEPRECATION", "1")

if getattr(sys, "frozen", False):
    os.environ.setdefault("PYTHONUTF8", "1")

from hydration_hero.startup import check_runtime, print_startup_hint

check_runtime()

from hydration_hero.app import main

if __name__ == "__main__":
    if not getattr(sys, "frozen", False):
        print_startup_hint()
    try:
        main()
    except Exception:
        import traceback

        if getattr(sys, "frozen", False):
            try:
                import tkinter as tk
                from tkinter import messagebox

                root = tk.Tk()
                root.withdraw()
                messagebox.showerror(
                    "Strawvarie Hydration Hero",
                    "The app crashed on startup.\n\n"
                    + traceback.format_exc(limit=8),
                )
                root.destroy()
            except Exception:
                traceback.print_exc()
        else:
            print("\nThe app crashed on startup:\n")
            traceback.print_exc()
            print("\nRun: python check_setup.py")
        raise SystemExit(1)
