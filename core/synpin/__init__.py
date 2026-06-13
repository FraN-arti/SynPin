"""SynPin — Multi-Agent Framework

Version resolution priority:

  1. ``importlib.metadata.version("synpin-core")`` — the canonical answer
     for installed packages. ``pyproject.toml`` is the single source
     of truth: the ``[project] version`` field is what
     ``importlib.metadata`` reads when the package is installed
     (e.g. ``pip install -e core/``).

  2. ``pyproject.toml`` direct read — used in the in-tree dev workflow
     before pip-install has been run (e.g. when the package is
     imported via ``cwd=core`` rather than via the install registry).
     Walks up from this file to find the nearest pyproject.toml.

  3. Hard-coded fallback — last resort. Should never be reached in
     practice; exists only so a broken env doesn't AttributeError on
     import.
"""
from __future__ import annotations

import re
from pathlib import Path

_FALLBACK_VERSION = "0.0.0+unknown"


def _read_version_from_installed() -> str | None:
    """Try the standard Python way: ask the package metadata."""
    try:
        from importlib.metadata import version

        return version("synpin-core")
    except Exception:
        return None


def _read_version_from_pyproject() -> str | None:
    """Read [project] version from the nearest pyproject.toml.

    Used as a fallback when the package isn't installed. Walks up the
    filesystem from this file to find the closest pyproject.toml —
    works for both the in-repo layout (core/synpin/__init__.py →
    core/pyproject.toml) and the monorepo layout (synpin/__init__.py →
    pyproject.toml).
    """
    cur = Path(__file__).resolve().parent
    for _ in range(6):  # hard cap; we never need to walk more than a few levels
        candidate = cur / "pyproject.toml"
        if candidate.exists():
            try:
                import tomllib
            except ImportError:
                import tomli as tomllib  # type: ignore
            with open(candidate, "rb") as f:
                data = tomllib.load(f)
            return data.get("project", {}).get("version")
        cur = cur.parent
    return None


def _resolve_version() -> str:
    for source in (_read_version_from_installed, _read_version_from_pyproject):
        try:
            v = source()
        except Exception:
            v = None
        if v:
            return v
    return _FALLBACK_VERSION


__version__ = _resolve_version()
