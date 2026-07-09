"""Unified path helpers: writable files next to the app, bundled assets from the package."""

from __future__ import annotations

import os
import sys


def app_dir() -> str:
    """Directory next to the frozen exe, or the entry-script directory in development."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)

    main = sys.modules.get("__main__")
    main_file = getattr(main, "__file__", None)
    if main_file:
        return os.path.abspath(os.path.dirname(main_file))
    return os.path.abspath(".")


def writable_path(*parts: str) -> str:
    """Build a path under :func:`app_dir` for configs, data logs, and functional logs."""
    return os.path.join(app_dir(), *parts)


def bundle_path(relative_path: str) -> str:
    """Resolve a read-only asset packed by PyInstaller (``_MEIPASS``) or next to the app."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = sys._MEIPASS
    else:
        base = app_dir()
    return os.path.join(base, relative_path)
