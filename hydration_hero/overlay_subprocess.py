"""Run the macOS overlay in a child process so Tk never loads AppKit."""

from __future__ import annotations

import io
import struct
import subprocess
import sys
import threading
from io import BytesIO
from typing import Callable, List, Optional

from PIL import Image


def overlay_worker_command(width: int, height: int, screen_x: int, screen_y: int) -> List[str]:
    args = [str(width), str(height), str(screen_x), str(screen_y)]
    if getattr(sys, "frozen", False):
        return [sys.executable, "--overlay-worker", *args]
    return [sys.executable, "-m", "hydration_hero.overlay_worker", *args]


class SubprocessOverlayWindow:
    """Transparent floating overlay hosted in a separate Python process."""

    def __init__(
        self,
        master,
        width: int,
        height: int,
        screen_x: int,
        screen_y: int,
        on_click: Callable[[int, int], None],
        *,
        dispatch_to_main: Optional[Callable[[Callable[[], None]], None]] = None,
        on_worker_exit: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._master = master
        self._on_click = on_click
        self._dispatch_to_main = dispatch_to_main
        self._on_worker_exit = on_worker_exit
        self._closed = False
        command = overlay_worker_command(width, height, screen_x, screen_y)
        self._proc = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )
        if self._proc.stdin is None or self._proc.stdout is None:
            raise RuntimeError("Failed to start overlay worker")

        stdout_text = io.TextIOWrapper(self._proc.stdout, encoding="utf-8", newline="\n")
        ready = stdout_text.readline().strip()
        if ready != "READY":
            stderr = ""
            if self._proc.stderr is not None:
                stderr = self._proc.stderr.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Overlay worker failed to start: {ready or stderr or 'unknown error'}")

        self._stdout = stdout_text
        self._reader = threading.Thread(target=self._read_stdout, daemon=True)
        self._reader.start()
        if self._proc.stderr is not None:
            self._stderr_reader = threading.Thread(target=self._read_stderr, daemon=True)
            self._stderr_reader.start()

    def is_alive(self) -> bool:
        return not self._closed and self._proc.poll() is None

    def _schedule_on_main(self, callback: Callable[[], None]) -> None:
        if self._dispatch_to_main is not None:
            self._dispatch_to_main(callback)
            return
        self._master.after(0, callback)

    def _read_stdout(self) -> None:
        stdout = self._stdout
        for line in stdout:
            if self._closed:
                return
            stripped = line.strip()
            if stripped.startswith("CLICK "):
                parts = stripped.split()
                if len(parts) != 3:
                    continue
                x = int(parts[1])
                y = int(parts[2])
                self._schedule_on_main(lambda x=x, y=y: self._on_click(x, y))

    def _read_stderr(self) -> None:
        stderr = self._proc.stderr
        if stderr is None:
            return
        for line in io.TextIOWrapper(stderr, encoding="utf-8", errors="replace"):
            text = line.strip()
            if text:
                print(f"overlay worker: {text}", flush=True)

    def _notify_exit(self, reason: str) -> None:
        if self._on_worker_exit is None:
            return
        self._schedule_on_main(lambda: self._on_worker_exit(reason))

    def show(self) -> None:
        return

    def set_image(self, image: Image.Image) -> None:
        if self._closed or self._proc.stdin is None:
            return
        if not self.is_alive():
            self._notify_exit("overlay worker exited unexpectedly")
            return

        buffer = BytesIO()
        image.convert("RGBA").save(buffer, format="PNG", compress_level=1)
        payload = buffer.getvalue()
        try:
            self._proc.stdin.write(b"F")
            self._proc.stdin.write(struct.pack(">I", len(payload)))
            self._proc.stdin.write(payload)
            self._proc.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            self._notify_exit(f"overlay worker pipe failed: {exc}")

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._proc.stdin is not None:
            try:
                self._proc.stdin.write(b"Q")
                self._proc.stdin.flush()
            except Exception:
                pass
        try:
            self._proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self._proc.kill()
