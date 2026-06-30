"""File read tool — read file contents with optional offset and limit.

Restricted to reading files under allowed directories (configurable).
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from .base import ToolResult, make_success, make_error
from ._registry import register_tool
from .security import get_allowed_roots, validate_path

# Max characters to return (1 MB safety limit)
_MAX_CHARS = 1_000_000



@register_tool(
    name='file_read',
    description='Чтение содержимого файла. Возвращает содержимое с номерами строк.',
    category='files',
    scope='all',
    dangerous=False,
)
async def file_read(params: dict) -> ToolResult:
    """Read a file's contents.

    Params:
        path (str): Path to the file (relative to allowed roots or absolute).
        offset (int, optional): Start reading from this line (1-indexed).
        limit (int, optional): Maximum number of lines to read.

    Returns:
        ToolResult with the file content as output.
    """
    path_str = params.get("path")
    if not path_str:
        return make_error("Missing required parameter: path")

    resolved = validate_path(path_str)
    if resolved is None:
        roots = get_allowed_roots()
        return make_error(
            f"Path '{path_str}' is outside the allowed directories ({', '.join(str(r) for r in roots)})."
        )

    if not resolved.exists():
        return make_error(f"File not found: {path_str}")
    if not resolved.is_file():
        return make_error(f"Path is not a file: {path_str}")

    try:
        content = await asyncio.to_thread(
            lambda: resolved.read_text(encoding="utf-8", errors="replace")
        )
    except Exception as e:
        return make_error(f"Failed to read file: {e}")

    lines = content.splitlines(keepends=True)

    offset = params.get("offset")
    limit = params.get("limit")

    # Apply offset (1-indexed)
    if offset is not None and offset > 0:
        lines = lines[offset - 1:]

    # Apply limit
    if limit is not None and limit > 0:
        lines = lines[:limit]

    output = "".join(lines)

    # Safety cap
    if len(output) > _MAX_CHARS:
        output = output[:_MAX_CHARS] + f"\n\n... (truncated, {len(content)} chars total)"

    # Add line count info
    total_lines = len(content.splitlines())
    shown_start = (offset - 1) if (offset and offset > 0) else 0
    shown_end = shown_start + len(lines)
    header = f"[Lines {shown_start + 1}-{shown_end} of {total_lines}]"

    return make_success(f"{header}\n{output}" if output else header)
