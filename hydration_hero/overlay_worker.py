"""Isolated macOS overlay process (AppKit only — no Tk in this interpreter)."""

from __future__ import annotations

import struct
import sys
import threading
from typing import Optional

import objc
from AppKit import (
    NSApplication,
    NSBackingStoreBuffered,
    NSColor,
    NSCompositingOperationSourceOver,
    NSDefaultRunLoopMode,
    NSFloatingWindowLevel,
    NSImage,
    NSPanel,
    NSScreen,
    NSView,
    NSWindowStyleMaskBorderless,
)
from Foundation import NSMakeRect, NSZeroRect

_running = True
_pending_frame: Optional[bytes] = None
_frame_lock = threading.Lock()
_panel = None


class _OverlayView(NSView):
    def initWithFrame_(self, frame):  # noqa: N802
        self = objc.super(_OverlayView, self).initWithFrame_(frame)
        if self is None:
            return None
        self._image = None
        return self

    def isOpaque(self):  # noqa: N802
        return False

    def acceptsFirstMouse_(self, event):  # noqa: N802
        return True

    def setImage_(self, image):  # noqa: N802
        self._image = image
        self.setNeedsDisplay_(True)

    def drawRect_(self, rect):  # noqa: N802
        if self._image is not None:
            self._image.drawInRect_fromRect_operation_fraction_(
                self.bounds(),
                NSZeroRect,
                NSCompositingOperationSourceOver,
                1.0,
            )

    def mouseDown_(self, event):  # noqa: N802
        loc = self.convertPoint_fromView_(event.locationInWindow(), None)
        height = self.bounds().size.height
        print(f"CLICK {int(loc.x)} {int(height - loc.y)}", flush=True)


def _read_exact(stream, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining > 0:
        chunk = stream.read(remaining)
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _stdin_loop() -> None:
    global _running, _pending_frame
    stream = sys.stdin.buffer
    while _running:
        cmd = _read_exact(stream, 1)
        if not cmd:
            _running = False
            return
        if cmd == b"Q":
            _running = False
            return
        if cmd == b"F":
            header = _read_exact(stream, 4)
            if len(header) < 4:
                _running = False
                return
            length = struct.unpack(">I", header)[0]
            payload = _read_exact(stream, length)
            if len(payload) < length:
                _running = False
                return
            with _frame_lock:
                _pending_frame = payload


def _apply_pending_frame(view: _OverlayView) -> None:
    global _pending_frame, _panel
    with _frame_lock:
        payload = _pending_frame
        _pending_frame = None
    if payload is None:
        return
    image = NSImage.alloc().initWithData_(payload)
    if image is not None:
        view.setImage_(image)
        if _panel is not None:
            _panel.orderFrontRegardless()


def run_worker(argv: list[str]) -> int:
    global _running, _panel

    if len(argv) < 4:
        print("ERROR usage: overlay_worker <width> <height> <screen_x> <screen_y>", flush=True)
        return 2

    width = int(argv[0])
    height = int(argv[1])
    screen_x = int(argv[2])
    screen_y = int(argv[3])

    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(1)  # NSApplicationActivationPolicyAccessory

    screen = NSScreen.mainScreen().frame()
    cocoa_y = int(screen.size.height) - screen_y - height
    window_frame = NSMakeRect(screen_x, cocoa_y, width, height)
    view_frame = NSMakeRect(0, 0, width, height)

    panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
        window_frame,
        NSWindowStyleMaskBorderless,
        NSBackingStoreBuffered,
        False,
    )
    _panel = panel
    panel.setLevel_(NSFloatingWindowLevel)
    panel.setOpaque_(False)
    panel.setBackgroundColor_(NSColor.clearColor())
    panel.setHasShadow_(False)
    panel.setIgnoresMouseEvents_(False)
    panel.setCollectionBehavior_(1)
    panel.setAcceptsMouseMovedEvents_(True)

    view = _OverlayView.alloc().initWithFrame_(view_frame)
    panel.setContentView_(view)
    panel.orderFrontRegardless()

    threading.Thread(target=_stdin_loop, daemon=True).start()
    print("READY", flush=True)

    while _running:
        with objc.autorelease_pool():
            event = app.nextEventMatchingMask_untilDate_inMode_dequeue_(  # noqa: N806
                0xFFFFFFFF,
                None,
                NSDefaultRunLoopMode,
                True,
            )
            if event is not None:
                app.sendEvent_(event)
            _apply_pending_frame(view)

    panel.orderOut_(None)
    panel.close()
    return 0


def main() -> None:
    raise SystemExit(run_worker(sys.argv[1:]))


if __name__ == "__main__":
    main()
