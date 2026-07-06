"""Platform and Python version compatibility helpers."""

import platform
import sys


def is_python_org_framework() -> bool:
    """Return True for python.org macOS framework builds."""
    return sys.base_prefix.startswith("/Library/Frameworks/Python.framework/")


def supports_macos_native_overlay() -> bool:
    """Only python.org framework Python is stable with Tk + pyobjc AppKit."""
    return (
        platform.system() == "Darwin"
        and sys.version_info[:2] == (3, 12)
        and is_python_org_framework()
    )


def python_314_or_newer() -> bool:
    return sys.version_info >= (3, 14)
