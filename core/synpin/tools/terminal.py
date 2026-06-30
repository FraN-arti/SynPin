"""Terminal tool — execute shell commands via subprocess.

Runs commands through bash (Git Bash on Windows) or cmd with a 30-second timeout.
Default working directory: first allowed directory (configurable).
"""
from __future__ import annotations

import subprocess
import os
from pathlib import Path

from .base import ToolResult, make_success, make_error
from .security import get_allowed_roots
from ._registry import register_tool

# Default working directory for command execution
def _get_work_root() -> Path:
    roots = get_allowed_roots()
    return roots[0] if roots else Path.home() / ".synpin"

# Maximum execution time in seconds
_TIMEOUT = 30


@register_tool(
    name="terminal",
    description="Выполнение shell-команд (bash). Используй для запуска git, npm, python, ls, cat и любых других команд.",
    category="code",
    scope="all",
    dangerous=True,
)

@register_tool(
    name='terminal',
    description='Выполнение shell-команд (bash). Используй для запуска git, npm, python, ls, cat и любых других команд.',
    category='code',
    scope='all',
    dangerous=True,
)
async def terminal(params: dict) -> ToolResult:
    """Execute a shell command and return stdout + stderr.

    Params:
        command (str): The shell command to execute.
    Returns:
        ToolResult with combined stdout+stderr output.
    """
    command = params.get("command")
    if not command:
        return make_error("Missing required parameter: command")

    try:
        # Determine shell: prefer bash (Git Bash on Windows), fallback to cmd
        import shutil
        shell_cmd = shutil.which("bash") or shutil.which("sh")
        if shell_cmd:
            # Use bash with -c flag
            cmd_list = [shell_cmd, "-c", command]
        else:
            # Windows fallback: use cmd.exe
            cmd_list = ["cmd", "/c", command]

        cwd = str(_get_work_root())

        proc = subprocess.Popen(
            cmd_list,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

        try:
            stdout_bytes, stderr_bytes = proc.communicate(timeout=_TIMEOUT)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            return make_error(
                f"Command timed out after {_TIMEOUT}s and was killed.\n"
                f"Command was: {command}"
            )

        stdout = stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
        stderr = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""

        # Combine output
        parts: list[str] = []
        if stdout.strip():
            parts.append(stdout.strip())
        if stderr.strip():
            parts.append(f"[stderr]\n{stderr.strip()}")
        if proc.returncode and proc.returncode != 0:
            parts.append(f"[exit code: {proc.returncode}]")

        output = "\n".join(parts) if parts else "(no output)"

        if proc.returncode and proc.returncode != 0 and not parts:
            return make_error(f"Command exited with code {proc.returncode}")

        return make_success(output)

    except Exception as e:
        import logging
        logging.getLogger("synpin.tools").error("[terminal] %s: %s", type(e).__name__, e)
        return make_error(f"Failed to execute command: {type(e).__name__}: {e}")
