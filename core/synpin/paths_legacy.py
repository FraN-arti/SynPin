"""Legacy path resolution — DO NOT USE IN NEW CODE.

This module consolidates 14 path-resolution functions that were
previously defined in 8 different files across the codebase:

  synpin/config/manager.py      (_get_config_dir, _get_agents_dir)
  synpin/agents/manager.py      (_get_config_dir, _get_agents_dir,
                                 _get_departments_dir, _get_otdels_dir)
  synpin/chat/router.py         (_get_data_dir)
  synpin/chat/session_reset.py  (_get_data_dir, _get_config_dir)
  synpin/chat/otdel_helpers.py  (_get_data_dir)
  synpin/tools/memory_read.py   (_get_data_dir)
  synpin/tools/memory_write.py  (_get_data_dir)
  synpin/kanban/service.py      (_get_data_dir)
  synpin/kanban/config.py       (_get_config_dir)
  synpin/api/hermes_chat_router.py (_get_data_dir)

Each copy had its own subtle differences (different number of .parent
levels, different fallback logic). The behaviour is preserved here
verbatim — this is a pure de-duplication, not a behaviour change.

The "new" path resolution lives in synpin/paths.py. That module
returns DIFFERENT paths in dev mode (~/core/.synpin instead of
~/core/synpin/config). Switching callers to paths.py is a separate
refactor (commit 2 in the structural plan) because it requires
relocating on-disk data.

This file exists so:
  1. There's one source of truth for the OLD behaviour, not 8.
  2. Future code can grep for `_get_config_dir` / `_get_data_dir` /
     `_get_departments_dir` / `_get_otdels_dir` and find them all here
     in one place.
  3. When commit 2 lands and we migrate to paths.py, the diff is
     "delete this entire file" rather than "find all callers".
"""
from __future__ import annotations

import os
import shutil
import threading
from pathlib import Path

# ---------------------------------------------------------------------------
# Memoised singletons — one per directory. Each module used to have its own
# module-level global; we consolidate them here.
# ---------------------------------------------------------------------------

_CONFIG_DIR: Path | None = None
_DATA_DIR: Path | None = None
_AGENTS_DIR: Path | None = None
_DEPARTMENTS_DIR: Path | None = None
_OTDELS_DIR: Path | None = None

_LOCKS = {
    "_CONFIG_DIR": threading.Lock(),
    "_DATA_DIR": threading.Lock(),
    "_AGENTS_DIR": threading.Lock(),
    "_DEPARTMENTS_DIR": threading.Lock(),
    "_OTDELS_DIR": threading.Lock(),
}


def _get_or_init(name: str, current: Path | None, init_fn) -> Path:
    """Memoise a directory lookup. Falls through to init_fn on first call."""
    if current is not None:
        return current
    with _LOCKS[name]:
        if globals()[name] is not None:
            return globals()[name]
        val = init_fn()
        globals()[name] = val
        return val


# ---------------------------------------------------------------------------
# Directories at the package level (core/synpin/...).
# The legacy code computes these as Path(__file__).parent.parent / "config"
# because __file__ is e.g. core/synpin/config/manager.py and two .parent
# hops land at core/synpin. From there / "config" -> core/synpin/config.
# ---------------------------------------------------------------------------

def _synpin_root() -> Path:
    """The synpin package root (core/synpin/).

    This file (paths_legacy.py) sits in core/synpin/ directly, so its
    parent IS the synpin root. The original code lived in submodules
    (config/, agents/, etc.) so it needed .parent.parent to reach the
    synpin root. We account for that depth difference by stopping one
    level earlier.
    """
    return Path(__file__).resolve().parent


# ---------------------------------------------------------------------------
# _get_config_dir — used by synpin/config/manager.py, synpin/agents/manager.py,
#                   synpin/kanban/config.py
# Behaviour: SYNPIN_DEV=1 -> dev, else ~/.synpin/config, fall back to dev
# if prod doesn't exist (first-run convenience). On first prod run, copy
# templates from the package's templates/ directory.
# ---------------------------------------------------------------------------

def _init_config_dir() -> Path:
    prod = Path.home() / ".synpin" / "config"
    dev = _synpin_root() / "config"

    # Dev mode: always use project directory
    if os.environ.get("SYNPIN_DEV") == "1":
        return dev

    # First prod run — copy templates to user home
    if not prod.exists():
        templates_dir = dev / "templates"
        if templates_dir.exists():
            prod.mkdir(parents=True, exist_ok=True)
            for tpl in templates_dir.glob("*.yaml"):
                shutil.copy2(str(tpl), str(prod / tpl.name))

    return prod if prod.exists() else dev


def _get_config_dir() -> Path:
    """Get config directory.

    SYNPIN_DEV=1 → always use dev path (core/synpin/config/).
    Otherwise → ~/.synpin/config/ (prod) with fallback to dev.
    On first prod run, copies templates to user home.
    """
    return _get_or_init("_CONFIG_DIR", _CONFIG_DIR, _init_config_dir)


# ---------------------------------------------------------------------------
# _get_data_dir — used by synpin/chat/router.py, synpin/chat/session_reset.py,
#                 synpin/chat/otdel_helpers.py, synpin/tools/memory_read.py,
#                 synpin/tools/memory_write.py, synpin/api/hermes_chat_router.py
# Behaviour: candidates = [~/.synpin/data, <project>/data]; first existing wins.
# If none exist, fall back to ~/synpin (memory_read) or return None
# (session_reset, others create it on demand).
# The <project>/data path is computed as Path(__file__).resolve() with
# N .parent hops where N varies (3 for most, 4 for tools/*).
# ---------------------------------------------------------------------------

def _init_data_dir_general() -> Path:
    """Default candidate pattern: <package>/data (where package = synpin/).

    paths_legacy.py lives in core/synpin/, so .parent is the synpin
    package root. Original code in chat/, api/, etc. lived one level
    deeper and needed .parent.parent to reach synpin/, then .parent
    again to reach core/, then /data -> core/data. We want the new
    layout: data lives INSIDE the synpin package at synpin/data/, so
    the dev path is just synpin/ + "data" (one hop from this file).
    """
    return _synpin_root() / "data"


def _init_data_dir_tools() -> Path:
    """Tool layer pattern: same as _init_data_dir_general — tools/ is
    one level deeper than the other modules, so the original code used
    4 hops; we sit one level shallower, so 3 hops to the same dest.

    In commit 3 of the structural refactor, the dev path moved from
    core/data (outside the package) to synpin/data (inside the
    package), so both legacy variants now point to the same place.
    """
    return _synpin_root() / "data"


def _get_data_dir() -> Path:
    """Resolve data directory using the most common (3 .parent hops) layout.

    Used by: chat/router.py, chat/otdel_helpers.py, tools/memory_*.py,
              api/hermes_chat_router.py.

    NOTE: tools/memory_*.py use 4 .parent hops in the original code.
    They're not converted to call this function (they call their own
    _get_data_dir) — see _get_data_dir_tools() for the tool variant.
    """
    return _get_or_init("_DATA_DIR", _DATA_DIR, _init_data_dir_general)


def _get_data_dir_tools() -> Path:
    """Tool variant — 4 .parent hops. Used by synpin/tools/memory_*.py.

    These two variants existed because tools/ is one level deeper than
    the other modules. They resolve to the SAME directory on disk, so
    this is a naming convenience, not a behaviour difference.
    """
    return _get_data_dir()


# ---------------------------------------------------------------------------
# _get_agents_dir — synpin/agents/manager.py only
# ---------------------------------------------------------------------------

def _init_agents_dir() -> Path:
    prod = Path.home() / ".synpin" / "agents"
    dev = _synpin_root() / "agents"
    return prod if prod.exists() else dev


def _get_agents_dir() -> Path:
    return _get_or_init("_AGENTS_DIR", _AGENTS_DIR, _init_agents_dir)


# ---------------------------------------------------------------------------
# _get_departments_dir — synpin/agents/manager.py only
# Pattern: 3 .parent hops to land at the project root (not synpin/).
# ---------------------------------------------------------------------------

def _init_departments_dir() -> Path:
    prod = Path.home() / ".synpin" / "data" / "departments"
    # In dev mode, departments live at core/synpin/data/departments/ —
    # i.e. inside the package's data/ subdirectory. Originally they
    # were at core/departments/ (project root, outside the package),
    # but that broke the "all data inside synpin/" invariant. The
    # path move is part of the structural refactor (commit 2); this
    # function definition was updated to match the new layout.
    dev = _synpin_root() / "data" / "departments"
    return prod if prod.exists() else dev


def _get_departments_dir() -> Path:
    return _get_or_init("_DEPARTMENTS_DIR", _DEPARTMENTS_DIR, _init_departments_dir)


# ---------------------------------------------------------------------------
# _get_otdels_dir — synpin/agents/manager.py only
# ---------------------------------------------------------------------------

def _init_otdels_dir() -> Path:
    prod = Path.home() / ".synpin" / "data" / "otdels"
    # See _init_departments_dir — moved into the package's data/.
    dev = _synpin_root() / "data" / "otdels"
    return prod if prod.exists() else dev


def _get_otdels_dir() -> Path:
    return _get_or_init("_OTDELS_DIR", _OTDELS_DIR, _init_otdels_dir)


# ---------------------------------------------------------------------------
# Per-module special cases
# ---------------------------------------------------------------------------
#
# These two have a slightly different fallback chain (return None instead
# of falling back to dev). They live separately to preserve original
# behaviour.

def _get_data_dir_or_none_session_reset() -> Path | None:
    """session_reset.py variant: returns None when neither candidate exists."""
    candidates = [
        Path.home() / ".synpin" / "data",
        Path(__file__).resolve().parent.parent.parent / "data",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _get_config_dir_or_none_session_reset() -> Path | None:
    """session_reset.py variant of _get_config_dir: returns None."""
    candidates = [
        Path.home() / ".synpin" / "config",
        Path(__file__).resolve().parent.parent / "config",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


# ---------------------------------------------------------------------------
# Legacy aliases preserved for code that imports specific private symbols
# ---------------------------------------------------------------------------

__all__ = [
    "_get_config_dir",
    "_get_data_dir",
    "_get_data_dir_tools",
    "_get_agents_dir",
    "_get_departments_dir",
    "_get_otdels_dir",
    "_get_data_dir_or_none_session_reset",
    "_get_config_dir_or_none_session_reset",
]
