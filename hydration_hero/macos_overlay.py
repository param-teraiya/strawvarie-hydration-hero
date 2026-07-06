"""Native macOS transparent floating overlay (AppKit via pyobjc)."""

from io import BytesIO
from typing import Callable

import objc
from AppKit import (
    NSBackingStoreBuffered,
    NSColor,
    NSCompositingOperationSourceOver,
    NSFloatingWindowLevel,
    NSImage,
    NSPanel,
    NSScreen,
    NSView,
    NSWindowStyleMaskBorderless,
)
from Foundation import NSMakeRect, NSZeroRect
from PIL import Image


def pil_to_nsimage(image: Image.Image) -> NSImage:
    buffer = BytesIO()
    image.convert("RGBA").save(buffer, format="PNG")
    ns_image = NSImage.alloc().initWithData_(buffer.getvalue())
    if ns_image is None:
        raise RuntimeError("Failed to convert overlay frame to NSImage")
    return ns_image


def _dispatch_to_tk(master, handler: Callable[[int, int], None], x: int, y: int) -> None:
    """Always run click handlers on the Tk main thread."""
    master.after(0, lambda: handler(x, y))


class _OverlayView(NSView):
    def initWithFrame_clickHandler_(self, frame, handler):  # noqa: N802
        self = objc.super(_OverlayView, self).initWithFrame_(frame)
        if self is None:
            return None
        self._image = None
        self._handler = handler
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
        if self._handler is None:
            return
        loc = self.convertPoint_fromView_(event.locationInWindow(), None)
        height = self.bounds().size.height
        self._handler(int(loc.x), int(height - loc.y))


class MacOSOverlayWindow:
    """Borderless, transparent NSWindow that displays a PIL RGBA frame."""

    def __init__(
        self,
        master,
        width: int,
        height: int,
        screen_x: int,
        screen_y: int,
        on_click: Callable[[int, int], None],
    ) -> None:
        screen = NSScreen.mainScreen().frame()
        cocoa_y = int(screen.size.height) - screen_y - height
        window_frame = NSMakeRect(screen_x, cocoa_y, width, height)
        view_frame = NSMakeRect(0, 0, width, height)

        self._panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            window_frame,
            NSWindowStyleMaskBorderless,
            NSBackingStoreBuffered,
            False,
        )
        self._panel.setLevel_(NSFloatingWindowLevel)
        self._panel.setOpaque_(False)
        self._panel.setBackgroundColor_(NSColor.clearColor())
        self._panel.setHasShadow_(False)
        self._panel.setIgnoresMouseEvents_(False)
        self._panel.setCollectionBehavior_(1)  # NSWindowCollectionBehaviorCanJoinAllSpaces
        self._panel.setAcceptsMouseMovedEvents_(True)

        click_handler = lambda x, y: _dispatch_to_tk(master, on_click, x, y)
        self._view = _OverlayView.alloc().initWithFrame_clickHandler_(view_frame, click_handler)
        self._view.setImage_(None)
        self._panel.setContentView_(self._view)

    def show(self) -> None:
        self._panel.orderFrontRegardless()
        try:
            self._panel.makeKeyAndOrderFront_(None)
        except Exception:
            pass

    def set_image(self, image: Image.Image) -> None:
        self._view.setImage_(pil_to_nsimage(image))

    def close(self) -> None:
        self._panel.orderOut_(None)
        self._panel.close()
