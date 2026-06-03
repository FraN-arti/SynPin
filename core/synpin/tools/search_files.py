"""Search files tool — search for files by name or content.

Uses ripgrep (rg) for content search and glob patterns for file search.
Restricted to searching under D:\\synpin\\.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from .base import ToolResult, make_success, make_error

# Security boundary
_ROOT = Path(r"D:\synpin")

# Max results to return
_MAX_RESULTS = 50


def _validate_path(path_str: str) -> Path | None:
    """Resolve and validate that the path is inside the root directory."""
    try:
        resolved = Path(path_str).resolve()
    except (OSError, ValueError):
        return None
    try:
        resolved.relative_to(_ROOT)
    except ValueError:
        return None
    return resolved


async def search_files(params: dict) -> ToolResult:
    """Search for files by name pattern or content.

    Params:
        pattern (str): Glob pattern (for files) or regex pattern (for content).
        path (str, optional): Directory to search in. Defaults to D:\\synpin\\.
        target (str, optional): "files" for file name search, "content" for
            content search. Defaults to "files".
        limit (int, optional): Maximum number of results. Defaults to 50.

    Returns:
        ToolResult with matching file paths or content matches.
    """
    pattern = params.get("pattern")
    if not pattern:
        return make_error("Missing required parameter: pattern")

    target = params.get("target", "files")
    limit = min(params.get("limit", _MAX_RESULTS), _MAX_RESULTS)

    # Determine search directory
    search_path_str = params.get("path", str(_ROOT))
    search_path = _validate_path(search_path_str)
    if search_path is None:
        return make_error(
            f"Path '{search_path_str}' is outside the allowed directory ({_ROOT})."
        )
    if not search_path.exists():
        return make_error(f"Path not found: {search_path_str}")

    if target == "files":
        return await _search_by_name(search_path, pattern, limit)
    elif target == "content":
        return await _search_by_content(search_path, pattern, limit)
    else:
        return make_error(f"Unknown target: {target}. Use 'files' or 'content'.")


async def _search_by_name(search_path: Path, pattern: str, limit: int) -> ToolResult:
    """Find files matching a glob pattern."""
    try:
        matches = await asyncio.to_thread(
            lambda: sorted(
                [p for p in search_path.rglob(pattern) if p.is_file()],
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )[:limit]
        )
    except Exception as e:
        return make_error(f"Search failed: {e}")

    if not matches:
        return make_success("No files found matching the pattern.")

    lines = [str(m.relative_to(_ROOT)) for m in matches]
    header = f"[{len(lines)} file(s) found]"
    return make_success(f"{header}\n" + "\n".join(lines))


async def _search_by_content(search_path: Path, pattern: str, limit: int) -> ToolResult:
    """Search file contents using ripgrep (rg)."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "rg", "--no-heading", "--line-number", "--max-count", str(limit),
            pattern, str(search_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=15)

        output = stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
        # Strip absolute paths to show relative ones
        output = output.replace(str(_ROOT) + "\\", "").replace(str(_ROOT) + "/", "")

        if not output.strip():
            # Try with -i (case insensitive) as fallback
            proc2 = await asyncio.create_subprocess_exec(
                "rg", "-i", "--no-heading", "--line-number", "--max-count", str(limit),
                pattern, str(search_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout2, _ = await asyncio.wait_for(proc2.communicate(), timeout=15)
            output = stdout2.decode("utf-8", errors="replace") if stdout2 else ""
            output = output.replace(str(_ROOT) + "\\", "").replace(str(_ROOT) + "/", "")

        if not output.strip():
            return make_success("No content matches found.")

        lines = output.strip().splitlines()[:limit]
        header = f"[{len(lines)} match(es) found]"
        return make_success(f"{header}\n" + "\n".join(lines))

    except FileNotFoundError:
        # ripgrep not installed — fall back to Python grep
        return await _fallback_content_search(search_path, pattern, limit)
    except asyncio.TimeoutError:
        return make_error("Search timed out after 15 seconds.")
    except Exception as e:
        return make_error(f"Content search failed: {e}")


async def _fallback_content_search(search_path: Path, pattern: str, limit: int) -> ToolResult:
    """Fallback content search using Python when ripgrep is unavailable."""
    import re

    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        return make_error(f"Invalid regex pattern: {e}")

    results: list[str] = []

    def _scan():
        for fpath in search_path.rglob("*"):
            if not fpath.is_file():
                continue
            # Skip binary-like files and huge files
            if fpath.stat().st_size > 1_000_000:
                continue
            try:
                text = fpath.read_text(encoding="utf-8", errors="replace")
                for i, line in enumerate(text.splitlines(), 1):
                    if regex.search(line):
                        rel = fpath.relative_to(_ROOT)
                        results.append(f"{rel}:{i}: {line.strip()}")
                        if len(results) >= limit:
                            return
            except Exception:
                continue

    await asyncio.to_thread(_scan)

    if not results:
        return make_success("No content matches found.")

    header = f"[{len(results)} match(es) found]"
    return make_success(f"{header}\n" + "\n".join(results))
