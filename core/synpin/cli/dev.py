"""Dev-mode orchestrator: run Core (FastAPI) + Web (Vite) in parallel.

Replaces the old core/dev_server.py. Called via `synpin dev` (cmd_dev
in commands.py). Uses Rich for unified, coloured output and resolves
all paths via synpin.paths so it works in dev and prod layouts.

Behaviour:
  1. Find a free port for Core (default 2088) and for Vite (default 2099).
  2. Start Core as a subprocess, print its stdout/stderr with [CORE] prefix.
  3. Wait for /api/health to respond (max 30s).
  4. Start Vite as a subprocess, print its stdout/stderr with [WEB] prefix.
  5. Wait for either to exit or for SIGINT/SIGTERM; clean up both.

ANSI handling
-------------
On Windows, ANSI escape sequences from Vite/Node would otherwise render
as raw garbage (e.g. "[32m[1mVITE[22m..."). Rich already handles this for
Python output via colorama, but child processes' output can leak
through. We wrap the stream so any residual escape codes are stripped
before they hit the user's terminal. On a real Windows Terminal or any
VT-aware host, the parent's VT processing is the source of truth and
this strip is a no-op.
"""
from __future__ import annotations

import os
import re
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path
from queue import Empty, Queue
from typing import Optional

from .console import console

# Strip ANSI escape sequences before they hit the terminal. We only
# handle CSI (Control Sequence Introducer, ESC [...X) because that's
# what Vite/Node/uvicorn emit for colors. OSC sequences (ESC ]) are
# used for terminal title bars and hyperlinks — none of the things we
# shell out to use them, so we don't bother matching them.
_ANSI_ESCAPE_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")

# Replace Unicode glyphs that some Windows console fonts lack with their
# ASCII / 7-bit equivalents. Vite emits "➜" (U+27A8) for "Local:" /
# "Network:" lines, and a small icon for the "press h + enter" hint;
# Cascadia Mono / Consolas render some of these as flipped or missing.
# ASCII-fallbacking them keeps the dev output readable everywhere.
_UNICODE_GLYPH_MAP = str.maketrans({
    "➜": ">",   # Vite's "Local: ..." / "Network: ..." prefix
    "‣": "*",   # misc
    "—": "-",  # em-dash (some fonts show it as a tofu on old conhost)
    "–": "-",  # en-dash
    "·": ".",  # middle dot (not in some legacy fonts)
    "…": "...",  # ellipsis
    "•": "*",  # bullet
})


def _strip_ansi(line: str) -> str:
    """Remove ANSI escape sequences from a line. Cheap (regex) and
    safe — if no escape sequences are present (modern Windows Terminal
    with VT processing) the line is returned unchanged."""
    return _ANSI_ESCAPE_RE.sub("", line)


def _normalize_glyphs(line: str) -> str:
    """Replace a handful of Unicode glyphs with their ASCII equivalents
    so legacy Windows console fonts don't render them as garbage."""
    return line.translate(_UNICODE_GLYPH_MAP)


def _output_printer(queue: Queue, stop_event: threading.Event, strip_ansi: bool) -> None:
    """Print queued (prefix, line) tuples with consistent formatting.

    If `strip_ansi` is True, residual escape codes from child processes
    are stripped before printing. Rich+colorama already render Python
    output correctly, so this only affects lines coming from the
    subprocess pipes (Vite/uvicorn).
    """
    while not stop_event.is_set():
        try:
            prefix, line = queue.get(timeout=OUTPUT_POLL_INTERVAL_S)
        except Empty:
            continue
        # Order matters: strip ANSI first (so we don't match glyph
        # bytes inside an escape), then swap unicode glyphs for ASCII.
        if strip_ansi:
            line = _strip_ansi(line)
        line = _normalize_glyphs(line)
        # Vite/Node occasionally emit blank lines or lines that are
        # only whitespace — skip them so the unified output stays
        # readable.
        if not line.strip():
            continue
        # CORE / WEB prefixes both wear the orange/amber brand family —
        # CORE a saturated #f97316 (the same --orange as the web),
        # WEB a softer #f59e0b (the --accent, "gold" tone) so the two
        # services are visually distinct without drifting out of the
        # single-hue identity.
        if prefix == "CORE":
            console.print(f"[#f97316]{prefix}[/#f97316] {line}")
        elif prefix == "WEB":
            console.print(f"[#f59e0b]{prefix}[/#f59e0b] {line}")
        else:
            console.print(f"{prefix} {line}")

CORE_HOST = "0.0.0.0"
CORE_PORT = 2088
WEB_PORT = 2099
CORE_STARTUP_TIMEOUT_S = 30
OUTPUT_POLL_INTERVAL_S = 0.1


def _project_root() -> Path:
    """Locate the project root (the directory containing pyproject.toml
    and the web/ and wiki/ subdirs). The CLI is one level deep inside
    synpin/cli/, so we walk up accordingly.

    This file is at core/synpin/cli/dev.py:
      .parent        = core/synpin/cli/
      .parent.parent = core/synpin/
      .parent.parent.parent = core/
      .parent.parent.parent.parent = project root
    """
    return Path(__file__).resolve().parent.parent.parent.parent


def _find_free_port(start: int, max_attempts: int = 10) -> int:
    """Find a free TCP port starting from `start`."""
    for port in range(start, start + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("0.0.0.0", port))
                return port
        except OSError:
            continue
    return start  # fall back; uvicorn will error if it's actually taken


def _stream_output(proc: subprocess.Popen, prefix: str, queue: Queue) -> None:
    """Forward a subprocess's stdout to a queue, line by line.

    Runs on its own thread; dies when the subprocess closes its stdout.
    """
    for line in iter(proc.stdout.readline, ""):
        queue.put((prefix, line.rstrip()))
    proc.stdout.close()


def _wait_for_backend(port: int, core_proc: subprocess.Popen) -> bool:
    """Poll /api/health until it responds (or timeout). Returns success."""
    for _ in range(CORE_STARTUP_TIMEOUT_S):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=2)
            return True
        except Exception:
            if core_proc.poll() is not None:
                console.print("[error]Core process died before becoming ready.[/error]")
                return False
            time.sleep(1)
    console.print(
        f"[warning]Backend not ready after {CORE_STARTUP_TIMEOUT_S}s — starting Web anyway.[/warning]"
    )
    return False


def _start_core(port: int) -> subprocess.Popen:
    """Start the FastAPI core server."""
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["SYNPIN_DEV"] = "1"  # dev mode disables static file serving in core

    cmd = [
        sys.executable, "-u", "-m", "uvicorn",
        "synpin.api.server:app",
        "--host", CORE_HOST,
        "--port", str(port),
        "--log-level", "info",
    ]
    return subprocess.Popen(
        cmd,
        cwd=str(_project_root() / "core"),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,  # merge stderr into stdout for unified stream
        text=True,
        bufsize=1,
    )


def _start_web(port: int, backend_port: int) -> subprocess.Popen:
    """Start the Vite dev server."""
    env = os.environ.copy()
    env["BACKEND_PORT"] = str(backend_port)
    env["VITE_API_PROXY_TARGET"] = f"http://127.0.0.1:{backend_port}"

    cmd = ["npm", "run", "dev", "--", "--port", str(port)]
    # On Windows, npm is a .cmd shim — need shell=True to find it
    return subprocess.Popen(
        cmd,
        cwd=str(_project_root() / "web"),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        shell=(os.name == "nt"),
    )


def _check_prerequisites() -> None:
    """Verify required files exist before starting anything."""
    root = _project_root()
    if not (root / "core" / "pyproject.toml").exists():
        console.print(f"[error]Core not found: {root / 'core'}[/error]")
        sys.exit(1)
    if not (root / "web" / "package.json").exists():
        console.print(f"[error]Web not found: {root / 'web'}[/error]")
        sys.exit(1)
    if not (root / "web" / "node_modules").exists():
        console.print("[warning]Installing web dependencies (npm install)...[/warning]")
        npm_cmd = ["npm", "install"] if os.name != "nt" else ["cmd", "/c", "npm", "install"]
        result = subprocess.run(
            npm_cmd, cwd=str(root / "web"), capture_output=True, text=True,
            shell=(os.name == "nt"),
        )
        if result.returncode != 0:
            console.print(f"[error]npm install failed:[/error]\n{result.stderr}")
            sys.exit(1)
        console.print("[success]Web dependencies installed.[/success]")


def run_dev_server() -> None:
    """Main entry: orchestrate Core + Web in parallel with unified output."""
    from .commands import _get_version

    _check_prerequisites()

    core_port = _find_free_port(CORE_PORT)
    web_port = _find_free_port(WEB_PORT)
    version = _get_version()

    console.print()
    console.print(f"[brand]🚀 SynPin v{version} — Development Mode[/brand]")
    console.print()
    console.print(f"  [dim]Core:  http://{CORE_HOST}:{core_port}/api[/dim]")
    console.print(f"  [dim]Web:   http://localhost:{web_port}[/dim]")
    console.print(f"  [dim]Docs: http://{CORE_HOST}:{core_port}/docs[/dim]")
    console.print(f"  [dim]Stop: Ctrl+C[/dim]")
    console.print()

    processes: list[subprocess.Popen] = []
    output_queue: Queue = Queue()
    printer_stop = threading.Event()

    def _shutdown(signum: Optional[int] = None, frame=None) -> None:
        if printer_stop.is_set():
            return
        printer_stop.set()
        console.print()
        console.print("[warning]⏳  Shutting down...[/warning]")
        for proc in processes:
            if proc.poll() is None:
                try:
                    if os.name == "nt":
                        subprocess.run(
                            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                            capture_output=True,
                        )
                    else:
                        proc.terminate()
                except Exception:
                    pass
        for proc in processes:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        console.print("[success]✅  SynPin stopped.[/success]")
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _shutdown)

    # Strip ANSI escapes from child process output on Windows legacy
    # conhost. Modern Windows Terminal / pty-aware hosts render them
    # correctly, so we set this conservatively: on Unix we leave them
    # alone (the terminal is the source of truth), on Windows we strip
    # because the dev.bat -> dev.ps1 path lands on legacy conhost for
    # many users.
    strip_ansi = os.name == "nt"
    printer = threading.Thread(target=_output_printer, args=(output_queue, printer_stop, strip_ansi), daemon=True)
    printer.start()

    # Start Core
    console.print("[success]Starting Core...[/success]")
    core_proc = _start_core(core_port)
    processes.append(core_proc)
    threading.Thread(target=_stream_output, args=(core_proc, "CORE", output_queue), daemon=True).start()

    # Wait for backend health
    _wait_for_backend(core_port, core_proc)
    if core_proc.poll() is not None:
        _shutdown()

    # Start Web
    console.print("[info]Starting Web...[/info]")
    web_proc = _start_web(web_port, core_port)
    processes.append(web_proc)
    threading.Thread(target=_stream_output, args=(web_proc, "WEB", output_queue), daemon=True).start()

    console.print()

    # Wait for any process to exit, or for shutdown
    try:
        while not printer_stop.is_set():
            for proc in processes:
                if proc.poll() is not None:
                    console.print(
                        f"[error]❌  {('Core' if proc is core_proc else 'Web')} exited with code {proc.returncode}[/error]"
                    )
                    _shutdown()
            time.sleep(0.5)
    except KeyboardInterrupt:
        _shutdown()
