# Strawvarie Hydration Hero

A friendly desktop hydration companion from **Strawvarie**. A pixel-art buddy lives in your
menu bar (macOS) or system tray (Windows) and gently reminds you to sip from your tumbler
through the day — and you can even turn a photo into your own buddy. Fully offline: no
accounts, no tracking, nothing leaves your computer.

Built with **Tauri v2** — a small Rust core plus a TypeScript UI. One codebase, macOS + Windows.

## The app lives in [`app/`](app/)

```bash
cd app
npm install
npm run tauri dev        # run it
npm run tauri build      # build installers
```

Full run/build instructions (including the universal macOS build): [`app/README.md`](app/README.md).

## What it does

- **Gentle reminders** — a pixel companion strolls into a screen corner, you sip, it strolls off. Never steals focus.
- **Menu-bar / tray app** — quiet, low-footprint, runs in the background. No dock clutter.
- **Make your own buddy** — turn a photo into a pixel character (via Google Gemini), imported and background-removed on-device.
- **Your rhythm** — custom interval, active/quiet hours, snooze, one-click pause.
- **Private & offline** — no accounts, no analytics, nothing leaves the machine.

## Downloads

Installers (macOS `.dmg` + Windows) are published on the
**[Releases page](https://github.com/param-teraiya/strawvarie-hydration-hero/releases/latest)**,
built automatically by GitHub Actions on each version tag (`git tag v1.0.0 && git push origin v1.0.0`).

> **First launch on macOS:** builds are currently unsigned (ad-hoc). Open the `.dmg`, drag the
> app to Applications, then use **System Settings → Privacy & Security → Open Anyway**. Apple
> notarization ($99/yr Apple Developer Program) removes this step for customers.

## Project history

This is a ground-up rebuild. The original Python/Tkinter prototype (V0) is preserved on the
[`legacy/python-v0`](https://github.com/param-teraiya/strawvarie-hydration-hero/tree/legacy/python-v0)
branch.

## License

Private / internal Strawvarie project — confirm licensing before public release.
