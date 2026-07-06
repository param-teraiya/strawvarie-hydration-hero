# Strawvarie Hydration Hero

Desktop hydration reminder app for [Strawvarie](https://strawvarie.in) — animated pixel hero, custom character from a Gemini video, daily water tracking, and timed reminders.

## Features

- Animated reminder popup (walk in → drink → walk out)
- Default bundled male pixel hero (~239 frames)
- Custom hero: create animation in Gemini, drop `hero.mp4`, app processes frames automatically
- In-app setup guide (opens in browser)
- Daily water goal, quick log, reminder interval, and snooze settings
- Runs in the background (Mac: dock; Windows/Linux: system tray)

## Requirements

- **Python 3.8+** (for development / running from source)
- **macOS** for building the `.app` (PyInstaller build is platform-specific)
- Tkinter (included with most Python installs)

## Quick start (run from source)

**Do not use macOS system `python3`** — it has old Tk 8.5 and crashes with `segmentation fault`.

Install **Python 3.12** from [python.org/macOS](https://www.python.org/downloads/macos/) first, then:

```bash
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python scripts/extract_default_frames.py   # once after clone (~1 min)
python main.py
```

On macOS, the **floating desktop hero** runs in a separate AppKit process so Tk
does not crash. Install dependencies with `pip install -r requirements.txt`.
Set `HYDRATION_HERO_DISABLE_NATIVE_OVERLAY=1` to force the card reminder.

If the window does not appear on Mac:

```bash
python check_setup.py
```

## Build Mac app (for sharing)

**Requirements:** macOS only. **Apple Silicon (M1–M5) is supported** — a build on your Mac produces a native ARM `.app` for other Apple Silicon Macs.

### New MacBook (M5 / M4 / M3) — do this first

1. Install **Python 3.12** from [python.org/macOS](https://www.python.org/downloads/macos/) (universal2 installer)
2. Install Xcode command-line tools (if prompted, or run `xcode-select --install`)
3. Clone/pull the repo, then build:

```bash
git pull
chmod +x build_mac.sh
./build_mac.sh
```

If a previous attempt failed, reset the venv and retry:

```bash
rm -rf venv
./build_mac.sh
```

### Build troubleshooting

| Problem | Fix |
|---------|-----|
| **`segmentation fault`** or **`Old system Tk 8.5`** | Install Python 3.12 from [python.org](https://www.python.org/downloads/macos/), then `rm -rf venv` and recreate venv with `python3.12` |
| `No usable Python with Tk 8.6+ found` | Same — system Python is not supported |
| `command not found: python3` | Same — new Macs often have no Python until you install it |
| `Tkinter is not available` | Use python.org Python, then `rm -rf venv && ./build_mac.sh` |
| `PyEval_RestoreThread` / `Python quit unexpectedly` | Pull latest code (overlay now runs in a separate process). If it persists, set `HYDRATION_HERO_DISABLE_NATIVE_OVERLAY=1` |
| Card reminder instead of floating hero | Run `pip install -r requirements.txt`, then `python check_setup.py` |
| `Missing heroes/male/default_hero.mp4` | Run `git pull` |
| `Frame extraction failed` | Run `xcode-select --install`, then `python scripts/extract_default_frames.py --force` |
| `Permission denied` on `build_mac.sh` | Run `chmod +x build_mac.sh` |
| PyInstaller / pip errors on M5 | `rm -rf venv`, install Python 3.12 from python.org, rebuild |

If it still fails, run `./build_mac.sh` and send the **full terminal output**.

Outputs:

- `dist/Strawvarie Hydration Hero.app`
- `dist/Strawvarie-Hydration-Hero-mac.zip` — send this zip to users

First launch on Mac if blocked: **Right-click → Open → Open**

> Builds on Apple Silicon Macs target ARM Macs. Build on Intel Mac for Intel users.

## Custom hero flow

1. Open the app → **Open setup guide (step-by-step)**
2. Follow Gemini prompts to create pixel character + animation
3. Save video as `hero.mp4`
4. Copy to `~/Strawvarie Hydration Hero/hero.mp4` (use **Open hero folder** in the app)
5. Click **Create my hero** (enabled once the video is detected)
6. **Preview reminder** → adjust settings → **Minimize to dock**

## Project layout

```
main.py                 Entry point
check_setup.py          Mac/Tk diagnostic helper
build_mac.sh            PyInstaller Mac build script
hydration_hero.spec     PyInstaller config
requirements.txt        Runtime dependencies
requirements-build.txt  Build dependencies (PyInstaller)
assets/                 Static app assets (committed)
  brand/                Logo
  guide/                Customer setup guide HTML
heroes/male/            Default bundled hero
  default_hero.mp4      Source video (committed, ~2.5 MB)
  frames/               Extracted sprites (gitignored, run extract script)
hydration_hero/         Application Python package
scripts/                extract_default_frames.py
```

## User data (not in repo)

| Path | Purpose |
|------|---------|
| `~/Strawvarie Hydration Hero/` | Custom `hero.mp4` + processed frames |
| `~/.hydration_hero/settings.json` | App settings and daily log |

## Dependencies

- customtkinter, Pillow, numpy, opencv-python-headless
- pystray (Windows/Linux tray)
- pyinstaller (build only)

## License

Private / internal Strawvarie project — confirm licensing before public release.
