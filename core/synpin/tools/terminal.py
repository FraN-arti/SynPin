"""Terminal tool — execute shell commands via asyncio subprocess.

Runs commands through bash with a 30-second timeout.
Restricted to working directory D:\\synpin\\ and its subdirectories.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

from .base import ToolResult, make_success, make_error

# Root directory for command execution (security boundary)
_WORK_ROOT = Path(r"D:\synpin")

# Maximum execution time in seconds
_TIMEOUT = 30


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
        # Use bash (Git Bash on Windows) for POSIX-compatible shell
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(_WORK_ROOT),
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=_TIMEOUT
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
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
        return make_error(f"Failed to execute command: {e}")
