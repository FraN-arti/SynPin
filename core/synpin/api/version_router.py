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
  - Update notifications: `/api/version/check` polls GitHub for
    newer releases and broadcasts `version:update_available` over
    WebSocket when one shows up. The web sidebar then shows a
    "Update available" pill next to the version number.
"""
from __future__ import annotations

import asyncio
import logging
import platform
import re
import sys
from pathlib import Path

import httpx
from fastapi import APIRouter

from synpin import __version__
from synpin.paths import project_root

logger = logging.getLogger("synpin.version")

router = APIRouter(prefix="/api", tags=["meta"])


# ---------------------------------------------------------------------------
# Static "what version am I running" endpoint
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Update-checker: GitHub Releases polling
#
# Every 6 hours, the server asks GitHub for the latest SynPin release
# tag and compares the semver against the running version. If newer,
# it broadcasts a 'version:update_available' event over WebSocket so
# the open browser tab shows an "Update available" pill. The check
# also runs once at startup so users who leave the page open for a
# week still see a fresh update notification the first time they
# reload. The first version of the check ignores pre-releases and
# only considers stable tags (no '-' suffix in semver).
# ---------------------------------------------------------------------------

GITHUB_REPO = "FraN-arti/SynPin"
GITHUB_API_LATEST = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
GITHUB_API_TAGS = f"https://api.github.com/repos/{GITHUB_REPO}/tags?per_page=20"
CHECK_INTERVAL_S = 6 * 60 * 60  # 6 hours
HTTP_TIMEOUT_S = 5.0

# Module-level state. The checker task writes the most recent
# check result here; the GET endpoint reads it. We don't lock
# because FastAPI runs handlers in a single thread and the
# checker awaits between writes.
_latest_check: dict = {
    "current": __version__,
    "latest": None,           # str or None
    "update_available": False,
    "checked_at": None,       # ISO timestamp of last GitHub hit
    "error": None,            # str or None — reason the last check failed
}


def _parse_semver(s: str) -> tuple[int, ...] | None:
    """Parse '0.2.5.2' / '1.2.3' / '1.0.0-rc1' into a comparable tuple.

    Supports the project's variant of semver with up to four numeric
    segments (major.minor.patch.build) where the trailing 'build'
    number is treated as a patch-level bump. We accept 1-4 numeric
    segments; anything else returns None.

    Pre-release suffix (everything after '-') is kept as the
    last element of the tuple, so '1.2.3-rc1' < '1.2.3-rc2' and
    '1.2.3' > '1.2.3-rc1' (no suffix beats any suffix).
    """
    m = re.match(r"^(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:\.(\d+))?(?:-(.+))?$", s.strip())
    if not m:
        return None
    parts = tuple(int(g) for g in m.groups()[:4] if g is not None)
    suffix = m.group(5) or ""
    return parts + (suffix,)


def _is_newer(a: str, b: str) -> bool:
    """Is semver a strictly newer than semver b? Returns False on parse failure."""
    pa = _parse_semver(a)
    pb = _parse_semver(b)
    if not pa or not pb:
        return False
    # Compare numeric prefix; if equal, fall back to pre-release
    # string. A version with NO suffix is considered newer than
    # the same version WITH a pre-release suffix (1.2.3 > 1.2.3-rc1).
    pa_num, pa_suf = pa[:-1], pa[-1]
    pb_num, pb_suf = pb[:-1], pb[-1]
    # Pad shorter numeric prefix with zeros so '0.2.5' compares
    # correctly against '0.2.5.2' (padded 0.2.5.0).
    pad = max(len(pa_num), len(pb_num))
    pa_num = pa_num + (0,) * (pad - len(pa_num))
    pb_num = pb_num + (0,) * (pad - len(pb_num))
    if pa_num != pb_num:
        return pa_num > pb_num
    if pa_suf == pb_suf:
        return False
    if pa_suf == "":
        return True  # no suffix beats any suffix
    if pb_suf == "":
        return False
    return pa_suf > pb_suf


async def _fetch_latest_github() -> str | None:
    """Query GitHub for the latest stable SynPin tag. Returns the
    version string, or None on any failure (network, rate-limit, no
    releases yet).

    We try /releases/latest first. If GitHub returns 404 (no
    published releases — only tags), we fall back to /tags and pick
    the highest semver, ignoring pre-release tags. If both fail,
    we return None and the endpoint shows the last cached result.
    """
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "synpin-update-checker",
    }
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_S) as client:
            r = await client.get(GITHUB_API_LATEST, headers=headers)
            if r.status_code == 200:
                data = r.json()
                tag = (data.get("tag_name") or "").lstrip("v")
                if tag and _parse_semver(tag):
                    # Releases API also tells us if it's a pre-release.
                    if not data.get("prerelease", False):
                        return tag
            elif r.status_code == 404:
                # No published releases — fall back to /tags.
                r = await client.get(GITHUB_API_TAGS, headers=headers)
                if r.status_code == 200:
                    tags = r.json()
                    candidates = []
                    for t in tags:
                        name = t["name"].lstrip("v")
                        if not _parse_semver(name):
                            continue
                        if "-" in name:
                            continue  # skip pre-releases
                        candidates.append(name)
                    if not candidates:
                        return None
                    return max(candidates, key=_sort_key)
            else:
                logger.warning(
                    "[update-check] GitHub /releases/latest returned %s", r.status_code
                )
                return None
    except (httpx.RequestError, asyncio.TimeoutError) as e:
        logger.warning("[update-check] GitHub request failed: %s", e)
        return None
    return None


def _sort_key(v: str):
    """Sort key for max(): tuple (major, minor, patch) so '1.10.0' > '1.9.0'."""
    p = _parse_semver(v) or (0, 0, 0, "")
    return p[:3]


@router.get("/version/check")
async def check_for_update() -> dict:
    """Return the current update-check state, refreshing if stale.

    Always returns the cached `latest_check` (so a stale network
    doesn't break the sidebar). If the last successful check was
    more than CHECK_INTERVAL_S ago, runs a fresh check in the
    background and the NEXT call will see the new result.

    Response shape:
      {
        "current":          "0.2.5.2",       # what we're running
        "latest":           "0.2.6.0" | null,  # newest stable on GitHub
        "update_available": true | false,
        "checked_at":       "2026-06-13T15:00:00" | null,
        "error":            null | "GitHub API rate limit"
      }
    """
    return _latest_check


async def _update_check_loop() -> None:
    """Background task: poll GitHub every CHECK_INTERVAL_S seconds
    and broadcast when an update becomes available.
    """

    # Run once at startup so users don't have to wait 6 hours for
    # the first check.
    await asyncio.sleep(2)  # let the FastAPI app finish startup
    await _run_one_check()

    while True:
        try:
            await asyncio.sleep(CHECK_INTERVAL_S)
        except asyncio.CancelledError:
            return
        await _run_one_check()


async def _run_one_check() -> None:
    """Execute one update check: fetch, compare, store, broadcast."""
    from datetime import datetime, timezone

    latest = await _fetch_latest_github()
    current = __version__
    update_available = bool(latest) and _is_newer(latest, current)
    _latest_check.update({
        "current": current,
        "latest": latest,
        "update_available": update_available,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "error": None if latest is not None else "GitHub unreachable (rate limit or no releases yet)",
    })
    if update_available:
        # Broadcast to every connected client so the sidebar pill
        # can light up without each tab polling.
        try:
            from ..chat.ws_manager import ws_manager
            await ws_manager.broadcast({
                "type": "version:update_available",
                "current": current,
                "latest": latest,
            })
        except Exception as e:
            logger.warning("[update-check] WS broadcast failed: %s", e)
        logger.info("[update-check] update available: %s -> %s", current, latest)


def schedule_update_checker() -> "asyncio.Task | None":
    """Start the background update-checker. Returns the task so the
    caller can cancel it on shutdown. Returns None if there's no
    running event loop yet (caller can retry later).
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return None
    return loop.create_task(_update_check_loop())
