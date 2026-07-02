"""Security config — allowed directories for file operations.

Two layers of access control:

1. Static `allowed_roots` (security.yaml) — global whitelist. Anything
   outside these roots is denied.

2. Project `work_dir` expansion — when an agent slug is supplied and
   the agent is a head of an otdel that participates in some project,
   the project's `work_dir` is treated as an additional allowed root.
   This is the only way to expand access beyond the static whitelist.
"""
from __future__ import annotations

from pathlib import Path
from ..config.manager import load_yaml

# Cache for allowed roots
_allowed_roots: list[Path] | None = None


def get_allowed_roots() -> list[Path]:
    """Get list of allowed root directories for file operations.

    Reads from security.yaml (or settings.yaml fallback).
    Returns cached value on subsequent calls.
    """
    global _allowed_roots
    if _allowed_roots is not None:
        return _allowed_roots

    try:
        # Try security.yaml first
        config = load_yaml("security.yaml")
        if not config:
            # Fallback to settings.yaml
            config = load_yaml("settings.yaml")
        # Both security.yaml and settings.yaml wrap settings under a
        # 'security' key. Unwrap it so we can read allowed_directories
        # at the right nesting level.
        config = config.get("security", config) if config else {}
    except Exception:
        config = {}

    roots = config.get("allowed_directories", [])
    if not roots:
        roots = [str(Path.home() / ".synpin")]

    _allowed_roots = list(dict.fromkeys(Path(r).resolve() for r in roots))  # deduplicate
    return _allowed_roots


def _project_work_dirs_for_agent(agent_slug: str | None) -> list[Path]:
    """Return the work_dir of every project this agent has access to.

    "Has access" means: the agent is the head of an otdel that
    appears in the project's departments[]. (Workers inherit access
    transitively through their head, but the per-agent scope check
    here is on the head itself; expand if you need worker access too.)

    Empty list if the agent slug is missing, no otdel is headed by
    them, or no project has a work_dir set.
    """
    if not agent_slug:
        return []

    try:
        from ..paths import get_otdels_dir, get_data_dir
        from ..projects.config import ProjectConfig
    except Exception:
        return []

    # Find otdels headed by this agent.
    headed_otdels: list[str] = []
    otdels_dir = get_otdels_dir()
    if not otdels_dir.exists():
        return []
    import yaml
    for entry in otdels_dir.iterdir():
        if not entry.is_dir():
            continue
        otdel_yaml = entry / "otdel.yaml"
        if not otdel_yaml.exists():
            continue
        try:
            data = yaml.safe_load(otdel_yaml.read_text(encoding="utf-8"))
        except Exception:
            continue
        if data.get("head") == agent_slug:
            headed_otdels.append(data.get("otdelid") or entry.name)

    if not headed_otdels:
        return []

    # Find work_dirs of projects where any of those otdels participates.
    work_dirs: list[Path] = []
    try:
        cfg = ProjectConfig(get_data_dir())
        for project in cfg.load_all_projects():
            for d in project.departments:
                if d.id in headed_otdels and project.work_dir:
                    try:
                        work_dirs.append(Path(project.work_dir).resolve())
                    except (OSError, ValueError):
                        # Bad work_dir; skip silently — better to fail
                        # closed than open the whole filesystem.
                        pass
    except Exception:
        return work_dirs

    # Deduplicate while preserving order.
    return list(dict.fromkeys(work_dirs))


def validate_path(
    path_str: str,
    allowed_roots: list[Path] | None = None,
    agent_slug: str | None = None,
) -> Path | None:
    """Resolve and validate that the path is inside allowed directories.

    Path is allowed if it lives under:
      1. The static `allowed_roots` (security.yaml), OR
      2. The work_dir of any project the calling agent (or its head)
         is bound to (only consulted when `agent_slug` is provided).

    Handles:
    - Forward slashes (D:/synpin/dev.bat)
    - Relative paths (./dev.bat, dev.bat) — resolved against first root
    - Trailing/leading whitespace
    - Paths without drive letter (resolved relative to first allowed root)
    """
    if not path_str:
        return None

    # Clean up
    path_str = path_str.strip().strip('"').strip("'")
    path_str = path_str.replace("/", "\\")  # Normalize forward slashes

    try:
        p = Path(path_str)
        if not p.is_absolute():
            # Relative path: resolve relative to first allowed root
            roots = allowed_roots or get_allowed_roots()
            if not roots:
                return None
            p = roots[0] / p
        resolved = p.resolve()
    except (OSError, ValueError):
        return None

    # Build the effective allowlist: static + project-scoped.
    static_roots = list(allowed_roots) if allowed_roots else list(get_allowed_roots())
    project_roots = _project_work_dirs_for_agent(agent_slug)
    effective_roots = static_roots + project_roots

    for root in effective_roots:
        try:
            resolved.relative_to(root)
            return resolved
        except ValueError:
            continue

    return None


def clear_cache():
    """Clear cached allowed roots (for config reload)."""
    global _allowed_roots
    _allowed_roots = None