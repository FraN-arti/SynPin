"""Security config — allowed directories for file operations."""
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
            config = config.get("security", {}) if config else {}
    except Exception:
        config = {}

    roots = config.get("allowed_directories", [])
    if not roots:
        roots = [str(Path.home() / ".synpin")]

    _allowed_roots = list(dict.fromkeys(Path(r).resolve() for r in roots))  # deduplicate
    return _allowed_roots


def validate_path(path_str: str, allowed_roots: list[Path] | None = None) -> Path | None:
    """Resolve and validate that the path is inside allowed directories.
    
    Handles:
    - Forward slashes (D:/synpin/dev.bat)
    - Relative paths (./dev.bat, dev.bat)
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

    # Security: must be under one of the allowed roots
    roots = allowed_roots or get_allowed_roots()
    for root in roots:
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
