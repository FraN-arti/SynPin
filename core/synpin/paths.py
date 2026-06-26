"""Centralised filesystem paths for SynPin.

Before this module existed, the same path-resolution logic was
duplicated across at least 5 files:

  - synpin/config/manager.py     (_get_config_dir)
  - synpin/agents/manager.py     (_get_departments_dir, _get_otdels_dir, _get_agents_dir)
  - synpin/chat/router.py        (_get_data_dir)
  - synpin/chat/session_reset.py (_get_data_dir, _get_config_dir)
  - synpin/tools/memory_*.py     (_get_data_dir)
  - synpin/kanban/service.py     (_get_data_dir)

Each copy had its own slightly different logic for "dev vs prod",
its own `Path(__file__).parent.parent...` chain, and a different
`if not exists() return dev` fallback. Result: 7 places to update
whenever a path changes, and new code had no obvious place to look.

This module is the single source of truth. All other modules import
from here. Dev/prod behaviour is controlled by the SYNPIN_DEV env var
(set automatically by `synpin` CLI and by `dev_server.py`).

Path scheme
-----------

The "user data directory" is the per-user, per-OS location where all
state lives:

  Linux/Mac :  ~/.synpin/        (XDG-aware via platformdirs)
  Windows   :  %USERPROFILE%\\.synpin\\

Inside that, the data layout (set by `init_layout()` at startup):

  ~/.synpin/
    synpin.db                    (SQLite main DB if used)
    config/                      (main YAML configs)
      settings.yaml
      agents.yaml
      departments.yaml
      otdels.yaml
      ...
    templates/                   (templates for first-run install)
    data/                        (per-entity files)
      tasks/<id>.yaml
      departments/<id>/department.yaml
      otdels/<id>/otdel.yaml
    logs/                        (future)
    cache/                       (future)

For backward compatibility during the dev-to-prod transition, when
SYNPIN_DEV=1 the user data directory is the *project* `core/.synpin/`
(or `core/synpin/data/` for per-entity files). The migration of
existing data happens in the install script (TODO).

When SYNPIN_DEV is unset:

  1. If the user data directory exists, use it.
  2. Otherwise, fall back to the dev project locations so the first
     dev-run-after-clone doesn't require a manual init.

Set `SYNPIN_FORCE_PROD=1` to skip the fallback entirely.
"""
from __future__ import annotations

import os
import shutil
import threading
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# User data directory resolution
# ---------------------------------------------------------------------------

# Resolve the project root (the directory that contains pyproject.toml).
# This is used as the dev-mode data location.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
# __file__ = core/synpin/paths.py
# .parent     = core/synpin/
# .parent.parent = core/
# .parent.parent.parent = D:/synpin/  (the project root)

_USER_DATA_DIR: Optional[Path] = None
_USER_DATA_LOCK = threading.Lock()


def is_dev_mode() -> bool:
    """True when SYNPIN_DEV=1 (dev_server.py, synpin dev)."""
    return os.environ.get("SYNPIN_DEV") == "1"


def is_force_prod() -> bool:
    """True when SYNPIN_FORCE_PROD=1 (refuse to fall back to project data)."""
    return os.environ.get("SYNPIN_FORCE_PROD") == "1"


def get_user_data_dir() -> Path:
    """Return the user data directory (~/.synpin on Unix, %USERPROFILE%\\.synpin on Windows).

    Priority:
      1. SYNPIN_DATA_DIR env var (explicit override; used by tests)
      2. Dev mode (SYNPIN_DEV=1): project-relative .synpin/ for IDE work
      3. ~/.synpin/ (XDG-aware via platformdirs if available, else Path.home())
    """
    global _USER_DATA_DIR
    with _USER_DATA_LOCK:
        if _USER_DATA_DIR is not None:
            return _USER_DATA_DIR

        # 1. Explicit override (tests, advanced users)
        env = os.environ.get("SYNPIN_DATA_DIR")
        if env:
            _USER_DATA_DIR = Path(env).expanduser().resolve()
            return _USER_DATA_DIR

        # 2. Dev mode: project-relative
        #    Per the structural refactor (commit 2 of 2026-06-13), all
        #    per-entity data lives INSIDE the synpin package at
        #    core/synpin/data/ and main configs at core/synpin/config/.
        #    Pointing the user data dir at core/.synpin (the pre-
        #    refactor location) would make the running server see an
        #    empty config tree, even though the YAMLs are sitting
        #    right next to the package. The "dev" location is now
        #    the package's own config/ + data/ subdirs — same as
        #    where they were before the refactor.
        if is_dev_mode():
            _USER_DATA_DIR = _PROJECT_ROOT / "core" / "synpin"
            # Defensive check: dev mode must never resolve to a path
            # outside the project tree. If we ever land on the user's
            # home .synpin (or anywhere else), fail loudly so the
            # developer notices immediately, rather than silently
            # writing to a hidden prod-style location.
            resolved = _USER_DATA_DIR.resolve()
            project_root = _PROJECT_ROOT.resolve()
            try:
                resolved.relative_to(project_root)
            except ValueError:
                raise RuntimeError(
                    f"[paths] SYNPIN_DEV=1 but get_user_data_dir() resolved to "
                    f"{resolved} which is OUTSIDE project root {project_root}. "
                    f"This would cause dev mode to write to a non-dev location. "
                    f"Check paths.py for regressions."
                )
            return _USER_DATA_DIR

        # 3. Production: user home
        try:
            from platformdirs import user_data_dir  # type: ignore

            base = Path(user_data_dir("synpin", "synpin"))
        except ImportError:
            # platformdirs not installed (yet) — fall back to ~/.synpin
            base = Path.home() / ".synpin"

        # If force-prod is set, never fall back to dev locations
        if is_force_prod():
            _USER_DATA_DIR = base
            return _USER_DATA_DIR

        # First-run convenience: if the user data dir doesn't exist but
        # the dev project does, prefer the dev project so a fresh clone
        # of SynPin works out of the box. Set SYNPIN_FORCE_PROD=1 to skip.
        if not base.exists():
            dev_fallback = _PROJECT_ROOT / "core" / ".synpin"
            if dev_fallback.exists():
                _USER_DATA_DIR = dev_fallback
                return _USER_DATA_DIR

        _USER_DATA_DIR = base
        return _USER_DATA_DIR


def init_layout() -> None:
    """Create the standard directory layout under the user data dir.

    Idempotent. Safe to call multiple times. Used by `synpin init` and
    on first dev-server start.
    """
    for sub in ("config", "templates", "data", "logs", "cache"):
        (get_user_data_dir() / sub).mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Specific subpaths
# ---------------------------------------------------------------------------

def get_config_dir() -> Path:
    """Directory holding main YAML configs (agents.yaml, otdels.yaml, etc.)."""
    return get_user_data_dir() / "config"


def get_data_dir() -> Path:
    """Directory holding per-entity YAML files (tasks, departments, otdels).

    Note: this is *different* from the user data dir. Per-entity data
    lives at <user_data_dir>/data/...
    """
    return get_user_data_dir() / "data"


def get_departments_dir() -> Path:
    """Directory holding per-department YAML files.

    Layout: <data_dir>/departments/<dept_id>/department.yaml
    """
    return get_data_dir() / "departments"


def get_otdels_dir() -> Path:
    """Directory holding per-otdel YAML files.

    Layout: <data_dir>/otdels/<otdel_id>/otdel.yaml
    """
    return get_data_dir() / "otdels"


def get_agents_dir() -> Path:
    """Directory holding per-agent YAML files.

    Layout: <data_dir>/agents/<agent_id>/agent.yaml
    """
    return get_data_dir() / "agents"


def get_tasks_dir() -> Path:
    """Directory holding per-task YAML files (Kanban).

    Layout: <data_dir>/tasks/<task_id>.yaml
    """
    return get_data_dir() / "tasks"


def get_templates_dir() -> Path:
    """Directory holding install templates (shipped with the package).

    In dev mode this is the project's templates/ folder; in prod it's
    a copy under the user data dir that gets populated by `synpin init`.
    """
    user_templates = get_user_data_dir() / "templates"
    if user_templates.exists():
        return user_templates
    # Dev fallback: shipped templates inside the package
    return Path(__file__).resolve().parent / "config" / "templates"


def get_logs_dir() -> Path:
    return get_user_data_dir() / "logs"


def get_cache_dir() -> Path:
    return get_user_data_dir() / "cache"


# ---------------------------------------------------------------------------
# Compatibility shims for code that's still being migrated
# ---------------------------------------------------------------------------
#
# The pre-refactor code uses these as module-level functions. We keep
# the same call-site compatibility but route through the centralised
# resolution. Once all callers are migrated, remove the shims.

def project_root() -> Path:
    """The repo root (where pyproject.toml lives). Used to anchor dev paths."""
    return _PROJECT_ROOT


# ---------------------------------------------------------------------------
# Optional variants — return None when the directory doesn't exist.
# Used by session_reset.py which must not crash on a missing data dir.
# ---------------------------------------------------------------------------

def get_data_dir_or_none() -> Path | None:
    """Like get_data_dir() but returns None if the directory doesn't exist."""
    p = get_data_dir()
    return p if p.exists() else None


def get_config_dir_or_none() -> Path | None:
    """Like get_config_dir() but returns None if the directory doesn't exist."""
    p = get_config_dir()
    return p if p.exists() else None


# Re-export for older callers that imported a private symbol
__all__ = [
    "is_dev_mode",
    "is_force_prod",
    "get_user_data_dir",
    "init_layout",
    "get_config_dir",
    "get_data_dir",
    "get_departments_dir",
    "get_otdels_dir",
    "get_agents_dir",
    "get_tasks_dir",
    "get_templates_dir",
    "get_logs_dir",
    "get_cache_dir",
    "get_data_dir_or_none",
    "get_config_dir_or_none",
    "project_root",
]
