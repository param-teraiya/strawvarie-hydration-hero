import os
import sys

# Must be set before Tk is imported (macOS shows a deprecation warning otherwise).
os.environ.setdefault("TK_SILENCE_DEPRECATION", "1")


def check_runtime() -> None:
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("ERROR: Python 3.8 or newer is required.")
        print(f"Current version: {sys.version.split()[0]}")
        sys.exit(1)

    if sys.platform != "darwin":
        return

    try:
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()
        patchlevel = str(root.tk.call("info", "patchlevel"))
        root.destroy()
    except Exception as exc:
        print("ERROR: Tkinter is not available.")
        print(exc)
        sys.exit(1)

    # Warn only — some Macs show the deprecation message but still work.
    if patchlevel.startswith("8.5."):
        print("WARNING: Old system Tk 8.5 detected. UI may not appear.")
        print("         Install Python from https://www.python.org/downloads/ if the app is blank.")
        print()


def print_startup_hint() -> None:
    print()
    print("Strawvarie Hydration Hero is running.")
    print("- Keep this Terminal window open (closing it quits the app).")
    print("- The dashboard should appear now on first launch.")
    print("- If you see nothing, run: python check_setup.py")
    print("- On Mac: you can also click the Python rocket icon in the Dock.")
    print()
