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

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
python scripts/extract_default_frames.py   # once after clone (~1 min)
python main.py
```

If the window does not appear on Mac:

```bash
python check_setup.py
```

## Build Mac app (for sharing)

```bash
chmod +x build_mac.sh
./build_mac.sh
```

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
hydration_hero/         Application package
  assets/               Logo + setup guide HTML
heroes/male/            Default hero source video (committed)
  default_hero.mp4      Extract to frame_*.png locally (gitignored)
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
