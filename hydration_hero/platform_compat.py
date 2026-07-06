"""Platform and Python version compatibility helpers."""

import platform
import os
import sys


def is_python_org_framework() -> bool:
    """Return True for python.org macOS framework builds."""
    return sys.base_prefix.startswith("/Library/Frameworks/Python.framework/")


def supports_macos_native_overlay() -> bool:
    """Use the native AppKit overlay only when explicitly enabled.

    Tk + pyobjc/AppKit can abort the Python interpreter on macOS even with
    python.org 3.12. Keep the card reminder as the stable default.
    """
    return (
        platform.system() == "Darwin"
        and sys.version_info[:2] == (3, 12)
        and is_python_org_framework()
        and os.environ.get("HYDRATION_HERO_ENABLE_NATIVE_OVERLAY") == "1"
    )


def python_314_or_newer() -> bool:
    return sys.version_info >= (3, 14)
