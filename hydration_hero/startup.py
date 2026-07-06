import os
import sys

# Must be set before Tk is imported (macOS shows a deprecation warning otherwise).
os.environ.setdefault("TK_SILENCE_DEPRECATION", "1")

PYTHON_ORG_URL = "https://www.python.org/downloads/macos/"


def _macos_python_is_system(exe: str) -> bool:
    if exe.startswith("/usr/bin/"):
        return True
    if "/Library/Developer/CommandLineTools/" in exe:
        return True
    return False


def _print_macos_python_fix() -> None:
    print("Fix on a new Mac:")
    print(f"  1. Install Python 3.12 from {PYTHON_ORG_URL}")
    print("  2. rm -rf venv")
    print("  3. python3.12 -m venv venv && source venv/bin/activate")
    print("  4. pip install -r requirements.txt")
    print("  5. python scripts/extract_default_frames.py")
    print("  6. python main.py   (or ./build_mac.sh to build the .app)")
    print()
    print(f"  Current Python: {sys.executable}")


def check_runtime() -> None:
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("ERROR: Python 3.8 or newer is required.")
        print(f"Current version: {sys.version.split()[0]}")
        sys.exit(1)

    if sys.platform != "darwin":
        return

    if _macos_python_is_system(sys.executable):
        print("ERROR: macOS system Python cannot run this app.")
        print("       It ships with old Tk 8.5 and usually crashes (segmentation fault).")
        print()
        _print_macos_python_fix()
        sys.exit(1)

    try:
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()
        patchlevel = str(root.tk.call("info", "patchlevel"))
        root.destroy()
    except Exception as exc:
        print("ERROR: Tkinter is not available.")
        print(exc)
        print()
        _print_macos_python_fix()
        sys.exit(1)

    if patchlevel.startswith("8.5."):
        print("ERROR: Old Tk 8.5 detected — CustomTkinter will crash (segmentation fault).")
        print(f"       Tk patchlevel: {patchlevel}")
        print()
        _print_macos_python_fix()
        sys.exit(1)


def print_startup_hint() -> None:
    print()
    print("Strawvarie Hydration Hero is running.")
    print("- Keep this Terminal window open (closing it quits the app).")
    print("- The dashboard should appear now on first launch.")
    print("- If you see nothing, run: python check_setup.py")
    print("- On Mac: you can also click the Python rocket icon in the Dock.")
    print()
