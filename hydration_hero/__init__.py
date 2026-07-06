"""Hydration Hero package initialization."""

import platform
import sys
import types


def _install_safe_darkdetect() -> None:
    """Prevent CustomTkinter from loading AppKit via darkdetect on macOS."""
    if platform.system() != "Darwin" or "darkdetect" in sys.modules:
        return

    darkdetect = types.ModuleType("darkdetect")
    darkdetect.theme = lambda: "Light"  # type: ignore[attr-defined]
    sys.modules["darkdetect"] = darkdetect


_install_safe_darkdetect()
