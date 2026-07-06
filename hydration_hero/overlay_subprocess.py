"""Run the macOS overlay in a child process so Tk never loads AppKit."""

from __future__ import annotations

import base64
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
    ) -> None:
        self._master = master
        self._on_click = on_click
        self._dispatch_to_main = dispatch_to_main
        self._closed = False
        command = overlay_worker_command(width, height, screen_x, screen_y)
        self._proc = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        if self._proc.stdin is None or self._proc.stdout is None:
            raise RuntimeError("Failed to start overlay worker")

        ready = self._proc.stdout.readline().strip()
        if ready != "READY":
            stderr = ""
            if self._proc.stderr is not None:
                stderr = self._proc.stderr.read()
            raise RuntimeError(f"Overlay worker failed to start: {ready or stderr or 'unknown error'}")

        self._reader = threading.Thread(target=self._read_stdout, daemon=True)
        self._reader.start()

    def _schedule_on_main(self, callback: Callable[[], None]) -> None:
        if self._dispatch_to_main is not None:
            self._dispatch_to_main(callback)
            return
        self._master.after(0, callback)

    def _read_stdout(self) -> None:
        stdout = self._proc.stdout
        if stdout is None:
            return
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

    def show(self) -> None:
        return

    def set_image(self, image: Image.Image) -> None:
        if self._closed or self._proc.stdin is None:
            return
        buffer = BytesIO()
        image.convert("RGBA").save(buffer, format="PNG")
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        self._proc.stdin.write(f"FRAME {encoded}\n")
        self._proc.stdin.flush()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._proc.stdin is not None:
            try:
                self._proc.stdin.write("QUIT\n")
                self._proc.stdin.flush()
            except Exception:
                pass
        try:
            self._proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self._proc.kill()
