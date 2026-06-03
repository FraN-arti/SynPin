"""Code execution tool — run Python code in a restricted sandbox.

Uses exec() with a carefully restricted global namespace to prevent
dangerous operations. Captures stdout.
"""
from __future__ import annotations

import asyncio
import io
import sys
import traceback
from typing import Any

from .base import ToolResult, make_success, make_error

# Dangerous builtins to remove from the sandbox
_BLOCKED_NAMES = {
    "__import__",
    "exec",
    "eval",
    "compile",
    "open",
    "input",
    "breakpoint",
    "exit",
    "quit",
    "globals",
    "locals",
    "vars",
    "dir",
    "getattr",
    "setattr",
    "delattr",
}

# Dangerous modules to block
_BLOCKED_MODULES = {
    "os",
    "sys",
    "subprocess",
    "shutil",
    "pathlib",
    "socket",
    "http",
    "urllib",
    "requests",
    "ctypes",
    "importlib",
    "code",
    "codeop",
    "pydoc",
    "runpy",
}

# Max code execution time in seconds
_TIMEOUT = 15

# Max output length
_MAX_OUTPUT = 50_000


def _create_sandbox() -> dict[str, Any]:
    """Create a restricted Python namespace for code execution."""
    import builtins

    # Start with safe builtins
    safe_builtins = {}
    for name in dir(builtins):
        if name not in _BLOCKED_NAMES and not name.startswith("_"):
            safe_builtins[name] = getattr(builtins, name)

    # Remove type constructors that could be dangerous
    for dangerous in ("type", "classmethod", "staticmethod", "super"):
        safe_builtins.pop(dangerous, None)

    # Provide safe imports — commonly used stdlib modules
    import math
    import json
    import re
    import time
    import calendar
    import datetime
    import collections
    import collections.abc
    import itertools
    import functools
    import random
    import string
    import textwrap
    import hashlib
    import base64
    import csv
    import io
    import struct
    import copy
    import decimal
    import fractions
    import enum
    import dataclasses
    import uuid
    import threading
    import typing
    import abc
    import contextlib
    import operator
    import statistics

    safe_modules: dict[str, Any] = {
        "math": math,
        "json": json,
        "re": re,
        "time": time,
        "calendar": calendar,
        "datetime": datetime,
        "collections": collections,
        "collections.abc": collections.abc,
        "itertools": itertools,
        "functools": functools,
        "random": random,
        "string": string,
        "textwrap": textwrap,
        "hashlib": hashlib,
        "base64": base64,
        "csv": csv,
        "io": io,
        "struct": struct,
        "copy": copy,
        "decimal": decimal,
        "fractions": fractions,
        "enum": enum,
        "dataclasses": dataclasses,
        "uuid": uuid,
        "threading": threading,
        "typing": typing,
        "abc": abc,
        "contextlib": contextlib,
        "operator": operator,
        "statistics": statistics,
    }

    def safe_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name in _BLOCKED_MODULES:
            raise ImportError(f"Module '{name}' is not allowed in the sandbox.")
        if name in safe_modules:
            return safe_modules[name]
        raise ImportError(f"Module '{name}' is not available in the sandbox.")

    # Re-inject __import__ into builtins so that Python's `import` statement works
    safe_builtins["__import__"] = safe_import

    namespace: dict[str, Any] = {
        "__builtins__": safe_builtins,
        "__name__": "__sandbox__",
    }

    # Pre-import safe modules into namespace
    namespace.update(safe_modules)

    return namespace


async def code_exec(params: dict) -> ToolResult:
    """Execute Python code in a restricted sandbox.

    Params:
        code (str): Python code to execute.

    Returns:
        ToolResult with the code's stdout output.
    """
    code = params.get("code")
    if code is None:
        return make_error("Missing required parameter: code")

    sandbox = _create_sandbox()

    # Capture stdout
    stdout_capture = io.StringIO()
    old_stdout = sys.stdout

    async def _run() -> tuple[str, str | None]:
        """Run the code and return (output, error)."""
        sys.stdout = stdout_capture
        try:
            # Try compiling first to catch syntax errors
            try:
                compiled = compile(code, "<sandbox>", "exec")
            except SyntaxError as e:
                return "", f"Syntax error: {e}"

            # Execute in the sandbox
            exec(compiled, sandbox)
            return stdout_capture.getvalue(), None
        except Exception as e:
            tb = traceback.format_exc()
            return stdout_capture.getvalue(), tb
        finally:
            sys.stdout = old_stdout

    try:
        output, error = await asyncio.wait_for(_run(), timeout=_TIMEOUT)
    except asyncio.TimeoutError:
        sys.stdout = old_stdout
        return make_error(
            f"Code execution timed out after {_TIMEOUT}s.\n"
            "Avoid infinite loops or long-running operations."
        )

    if error:
        full_output = output + "\n" + error if output else error
        # Truncate if too long
        if len(full_output) > _MAX_OUTPUT:
            full_output = full_output[:_MAX_OUTPUT] + "\n... (truncated)"
        return make_error(full_output)

    if not output or not output.strip():
        return make_success("(code executed successfully, no output)")

    # Truncate if too long
    if len(output) > _MAX_OUTPUT:
        output = output[:_MAX_OUTPUT] + "\n... (truncated)"

    return make_success(output.rstrip())
