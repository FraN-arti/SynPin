"""File write tool — write content to a file.

Creates parent directories as needed. Overwrites existing files.
Restricted to writing files under D:\\synpin\\.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from .base import ToolResult, make_success, make_error

# Security boundary — all file writes must be under this directory
_ROOT = Path(r"D:\synpin")


def _validate_path(path_str: str) -> Path | None:
    """Resolve and validate that the path is inside the root directory.
    
    Handles forward slashes, relative paths, whitespace, quotes.
    """
    if not path_str:
        return None

    path_str = path_str.strip().strip('"').strip("'")
    path_str = path_str.replace("/", "\\")

    try:
        p = Path(path_str)
        if not p.is_absolute():
            p = _ROOT / p
        resolved = p.resolve()
    except (OSError, ValueError):
        return None

    try:
        resolved.relative_to(_ROOT)
    except ValueError:
        return None

    return resolved


async def file_write(params: dict) -> ToolResult:
    """Write content to a file (overwrites existing content).

    Params:
        path (str): Path to the file (relative to D:\\synpin\\ or absolute).
        content (str): Content to write.

    Returns:
        ToolResult with a success message including bytes written.
    """
    path_str = params.get("path")
    if not path_str:
        return make_error("Missing required parameter: path")

    content = params.get("content")
    if content is None:
        return make_error("Missing required parameter: content")

    resolved = _validate_path(path_str)
    if resolved is None:
        return make_error(
            f"Path '{path_str}' is outside the allowed directory ({_ROOT})."
        )

    try:
        # Create parent directories if needed
        await asyncio.to_thread(resolved.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(
            resolved.write_text, content, encoding="utf-8"
        )
    except Exception as e:
        return make_error(f"Failed to write file: {e}")

    size = len(content.encode("utf-8"))
    lines = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
    return make_success(
        f"Written {size} bytes ({lines} lines) to {path_str}"
    )
