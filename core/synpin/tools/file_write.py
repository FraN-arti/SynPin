"""File write tool — write content to a file.

Creates parent directories as needed. Overwrites existing files.
Restricted to writing files under allowed directories (configurable).
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from .base import ToolResult, make_success, make_error
from ._registry import register_tool
from .security import get_allowed_roots, validate_path



@register_tool(
    name='file_write',
    description='Запись/перезапись содержимого файла. Создаёт файл или перезаписывает существующий.',
    category='files',
    scope='all',
    dangerous=True,
)
async def file_write(params: dict) -> ToolResult:
    """Write content to a file (overwrites existing content).

    Params:
        path (str): Path to the file (relative to allowed roots or absolute).
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

    resolved = validate_path(path_str)
    if resolved is None:
        roots = get_allowed_roots()
        return make_error(
            f"Path '{path_str}' is outside the allowed directories ({', '.join(str(r) for r in roots)})."
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
