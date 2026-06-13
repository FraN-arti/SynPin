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
    so legacy Windows console fonts don't render them as garbage.

    We also strip any other non-ASCII character that we didn't
    explicitly map. Vite/Node occasionally emit glyphs the local
    font can't render (Cascadia Mono on legacy conhost is a common
    offender — em-dashes, en-dashes, and the U+27A8 arrow show up
    as mojibake like 'вћњ'). Rather than enumerate every possible
    glyph, we just neuter anything we can't represent: replace with
    '?' for control-ish or punctuation glyphs, drop for whitespace
    ones. ASCII letters and digits always pass through.

    The trade-off: a Russian/Chinese/emoji text line would lose its
    script characters here. We don't expect that from Vite/uvicorn
    output, but if it ever shows up we can add an allow-list.
    """
    # First: explicit mappings we know we want to keep meaningful
    out = line.translate(_UNICODE_GLYPH_MAP)
    # Second: nuke remaining non-ASCII. ASCII letters/digits/punct
    # (0x20..0x7E) and tab/newline pass through. Anything else
    # becomes '?'.
    return "".join(c if (0x20 <= ord(c) <= 0x7E or c in "\t\n") else "?" for c in out)


# Uvicorn and most Python loggers prefix each line with a level tag
# ('INFO:', 'WARNING:', 'ERROR:', 'DEBUG:', 'CRITICAL:') optionally
# surrounded by spaces. We colour the tag inline so the eye can pick
# out severity at a glance, but leave the message text in the default
# colour so it stays readable.
_LOG_LEVEL_RE = re.compile(r"^(\s*)(INFO|WARNING|ERROR|DEBUG|CRITICAL)(\s*:)(.*)$")


def _color_log_level(line: str) -> str:
    """Wrap a uvicorn-style log line's level tag in a Rich colour tag.

    Returns the line unchanged if it doesn't match the expected shape —
    Vite output, plain stdout from a custom tool, or anything that
    doesn't start with a recognised level tag just passes through.
    """
    m = _LOG_LEVEL_RE.match(line)
    if not m:
        return line
    indent, level, colon, rest = m.groups()
    colors = {
        "INFO":     "#f59e0b",   # gold (brand accent, calm/normal)
        "WARNING":  "#fbbf24",   # amber-400 (warmer, attention)
        "ERROR":    "red",       # red (alarm)
        "DEBUG":    "dim",       # low-emphasis
        "CRITICAL": "bold red",  # bold red (severe)
    }
    color = colors.get(level, "dim")
    # Use Rich's [color]text[/color] markup. We mark the indent and
    # the message body as plain so the surrounding colour tags from
    # the CORE/WEB prefix don't bleed into the level tag's colour.
    return f"{indent}[{color}]{level}[/{color}]{colon}{rest}"


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
        #
        # Uvicorn-style log lines start with an uppercase level tag
        # (INFO, WARNING, ERROR, DEBUG) followed by ':'. When we see
        # one, we colour the tag inline so the eye can pick out
        # "which severity is this?" at a glance. INFO is gold
        # (#f59e0b, the brand accent — calm/normal), WARNING is a
        # warmer amber (#fbbf24), ERROR is red, DEBUG is dim.
        if prefix == "CORE":
            console.print(f"[#f97316]{prefix}[/#f97316] {_color_log_level(line)}")
        elif prefix == "WEB":
            console.print(f"[#f59e0b]{prefix}[/#f59e0b] {_color_log_level(line)}")
        else:
            console.print(f"{prefix} {_color_log_level(line)}")

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


def _kill_orphan_vite() -> None:
    """Kill any orphan Vite process from a previous synpin dev run.

    On Windows, Ctrl+C of the synpin dev Python process tree can
    leave the underlying node.exe (Vite) alive — particularly if
    Vite had spawned esbuild workers that adopted the orphaned
    state. The next 'synpin dev' would then skip the default port
    and bind to 2100/2101/..., which is technically correct but
    confusing for the user (they expect 2099).

    We detect orphans by asking the OS what's listening on 2099 and
    2088. Anything there that isn't us is killed. We only kill
    processes whose parent or whose image basename looks like
    'node' / 'python' to avoid nuking unrelated services.
    """
    if os.name != "nt":
        return  # Unix: signal propagation is reliable, no orphans
    for port in (CORE_PORT, WEB_PORT):
        if port == 0:
            continue
        # Ask Windows who's listening on this port.
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"Get-NetTCPConnection -LocalPort {port} -State Listen -ErrorAction SilentlyContinue "
             f"| Select-Object -ExpandProperty OwningProcess -Unique"],
            capture_output=True, text=True, timeout=5,
        )
        pids = {int(x) for x in result.stdout.split() if x.strip().isdigit()}
        for pid in pids:
            if pid == 0 or pid == os.getpid():
                continue
            # Sanity check: only kill if it's node or python.
            # We don't want to nuke a Postgres or a Redis that
            # happens to listen on 2088.
            info = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f"(Get-Process -Id {pid} -ErrorAction SilentlyContinue).ProcessName"],
                capture_output=True, text=True, timeout=5,
            )
            name = info.stdout.strip().lower()
            if name in ("node", "node.exe", "python", "python.exe"):
                console.print(
                    f"[dim]Cleaning up orphan {name} (pid {pid}) on port {port}[/dim]"
                )
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(pid)],
                    capture_output=True, timeout=5,
                )
        # Brief settle so the kernel reclaims the port.
        if pids:
            time.sleep(0.5)


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

    # On Windows, a previous dev run can leave a Vite process
    # bound to 2099 if Ctrl+C didn't propagate all the way down
    # the node tree. Clean those up before we look for ports, so
    # the new run gets the canonical defaults (2088 + 2099) and
    # not bumped-to-2100 fallback values.
    _kill_orphan_vite()

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
