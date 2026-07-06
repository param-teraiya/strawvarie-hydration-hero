"""Platform and Python version compatibility helpers."""

import importlib.util
import os
import platform
import sys
from typing import Optional


def _pyobjc_available() -> bool:
    try:
        return (
            importlib.util.find_spec("objc") is not None
            and importlib.util.find_spec("AppKit") is not None
        )
    except Exception:
        return False


def macos_overlay_fallback_reason() -> Optional[str]:
    """Explain why the card reminder is used instead of the floating overlay."""
    if platform.system() != "Darwin":
        return None
    if os.environ.get("HYDRATION_HERO_DISABLE_NATIVE_OVERLAY") == "1":
        return "native overlay disabled by HYDRATION_HERO_DISABLE_NATIVE_OVERLAY=1"
    if sys.version_info < (3, 8):
        return "Python 3.8+ required"
    if not _pyobjc_available():
        return "pyobjc not installed — run: pip install -r requirements.txt"
    return None


def supports_macos_native_overlay() -> bool:
    """Use the transparent overlay via an isolated AppKit worker process."""
    return macos_overlay_fallback_reason() is None


def python_314_or_newer() -> bool:
    return sys.version_info >= (3, 14)
