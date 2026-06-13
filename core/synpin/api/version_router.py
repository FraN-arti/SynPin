"""Version endpoint — exposes the running server's version + runtime info.

Single source of truth is the `__version__` in synpin/__init__.py, which
in turn reads from importlib.metadata (i.e. pyproject.toml) and falls
back to direct pyproject.toml read for the in-tree dev workflow.

This endpoint exists for:
  - Web UI live version display (subscribes via WebSocket event
    `version:changed`, falls back to polling /api/version)
  - Operators wanting to verify a deployed instance is the expected
    build (the path component is the resolved install location —
    pip vs in-tree dev are visually distinct)
  - Health-check integrations
"""
from __future__ import annotations

import platform
import sys
from pathlib import Path

from fastapi import APIRouter

from synpin import __version__
from synpin.paths import project_root

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/version")
def get_version() -> dict:
    """Return the running server's version and runtime info.

    Response shape:
      {
        "version":      "0.2.5.2",
        "python":       "3.11.9",
        "platform":     "Windows-10-10.0.19045-SP0",
        "synpin_root":  "D:/synpin",     # project root, used by the dev layout
        "synpin_pkg":   "D:/synpin/core/synpin",  # where the synpin package lives
        "install":      "editable" | "system",  # editable install or not
      }
    """
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    synpin_pkg = Path(__file__).resolve().parent.parent
    return {
        "version": __version__,
        "python": py_version,
        "platform": platform.platform(),
        "synpin_root": str(project_root()),
        "synpin_pkg": str(synpin_pkg),
        "install": _detect_install_kind(),
    }


def _detect_install_kind() -> str:
    """Best-effort 'editable' vs 'system' detection.

    We compare the package location with the importlib.metadata
    location. If they differ (the package is on disk under the repo
    rather than in site-packages), we're in editable / dev mode.
    """
    try:
        from importlib.metadata import distribution
        import synpin as _pkg  # local import to avoid cycle at module load

        dist = distribution("synpin-core")
        if dist.files is None:
            return "system"
        # If the package's __init__ lives under the editable location
        # (i.e. inside our repo, not under site-packages), call it editable.
        pkg_path = Path(_pkg.__file__).resolve()
        dist_path = Path(str(dist.locate_file("."))).resolve()
        # dist.locate_file('.') returns the package's installation root —
        # for editable installs that's the source dir, for system installs
        # that's site-packages.
        if str(pkg_path).startswith(str(dist_path)):
            return "editable"
        return "system"
    except Exception:
        return "unknown"
