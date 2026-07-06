"""SynPin — Multi-Agent Framework

Version resolution priority:

  1. ``VERSION`` file at the repo root — single source of truth.
     One place to change, everything reads from it.

  2. ``importlib.metadata.version("synpin-core")`` — for installed
     packages (after ``pip install -e core/``).

  3. Hard-coded fallback — last resort.
"""
from __future__ import annotations

from pathlib import Path

_FALLBACK_VERSION = "0.0.0+unknown"


def _read_version_from_file() -> str | None:
    """Read the ``VERSION`` file at the repo root."""
    cur = Path(__file__).resolve().parent
    for _ in range(6):
        candidate = cur / "VERSION"
        if candidate.exists():
            try:
                return candidate.read_text(encoding="utf-8").strip()
            except Exception:
                return None
        cur = cur.parent
    return None


def _read_version_from_installed() -> str | None:
    """Try the standard Python way: ask the package metadata."""
    try:
        from importlib.metadata import version

        return version("synpin-core")
    except Exception:
        return None


def _resolve_version() -> str:
    for source in (_read_version_from_file, _read_version_from_installed):
        try:
            v = source()
        except Exception:
            v = None
        if v:
            return v
    return _FALLBACK_VERSION


__version__ = _resolve_version()
