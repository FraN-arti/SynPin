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
    "⚡": "*",  # Vite "ready in" / "Local:" / "Network:" prefix
    "🚀": "",   # Vite banner emoji — remove (renders as ??? on legacy conhost)
    "↻": "R",   # Vite HMR reload icon
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
    return "".join(c if (0x20 <= ord(c) <= 0x7E or c in "\t\n") else ">" for c in out)


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
    processes whose image basename looks like 'node' / 'python' to
    avoid nuking unrelated services.

    Uses ``netstat -ano`` (native Windows, instant) instead of
    PowerShell to avoid hangs on fresh installs.
    """
    if os.name != "nt":
        return  # Unix: signal propagation is reliable, no orphans
    for port in (CORE_PORT, WEB_PORT):
        if port == 0:
            continue
        # Ask Windows who's listening on this port via netstat (fast, no PowerShell).
        try:
            result = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True, text=True, timeout=10,
            )
            pids: set[int] = set()
            for line in result.stdout.splitlines():
                # Lines like:  TCP  0.0.0.0:2088  0.0.0.0:0  LISTENING  12345
                parts = line.split()
                if len(parts) < 5:
                    continue
                local = parts[1]
                state = parts[3]
                try:
                    pid = int(parts[4])
                except ValueError:
                    continue
                if state != "LISTENING":
                    continue
                # Match port — local is "ip:port" or "[::]:port"
                if local.endswith(f":{port}"):
                    pids.add(pid)
        except (subprocess.TimeoutExpired, Exception):
            # netstat failed — skip orphan cleanup, not critical.
            continue

        for pid in pids:
            if pid == 0 or pid == os.getpid():
                continue
            # Get process name via wmic (fast, no PowerShell).
            try:
                info = subprocess.run(
                    ["wmic", "process", "where", f"ProcessId={pid}",
                     "get", "Name", "/value"],
                    capture_output=True, text=True, timeout=5,
                )
                name = ""
                for part in info.stdout.strip().split("\r\n"):
                    if part.startswith("Name="):
                        name = part.split("=", 1)[1].strip().lower()
                        break
                if name in ("node", "node.exe", "python", "python.exe"):
                    console.print(
                        f"[dim]Cleaning up orphan {name} (pid {pid}) on port {port}[/dim]"
                    )
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(pid)],
                        capture_output=True, timeout=5,
                    )
            except (subprocess.TimeoutExpired, Exception):
                pass  # Non-critical — skip this PID
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


def _wait_for_file_change(timeout: int = 300) -> bool:
    """Wait for a file change in the project. Returns True if change detected."""
    try:
        import watchdog.observers
        import watchdog.events
    except ImportError:
        # Fallback: just wait and assume change
        console.print("[dim]watchdog not installed — waiting 5s for change...[/dim]")
        time.sleep(5)
        return True

    project_root = _project_root()

    class ChangeHandler(watchdog.events.FileSystemEventHandler):
        def __init__(self):
            self.changed = False
        def on_modified(self, event):
            if not event.is_directory and event.src_path.endswith(('.py', '.tsx', '.ts', '.css')):
                self.changed = True
        def on_created(self, event):
            if not event.is_directory and event.src_path.endswith(('.py', '.tsx', '.ts', '.css')):
                self.changed = True

    handler = ChangeHandler()
    observer = watchdog.observers.Observer()
    try:
        observer.schedule(handler, str(project_root / "core"), recursive=True)
    except Exception:
        pass
    try:
        observer.schedule(handler, str(project_root / "web" / "src"), recursive=True)
    except Exception:
        pass
    observer.start()
    try:
        for _ in range(timeout * 2):  # Check every 0.5s
            if handler.changed:
                return True
            time.sleep(0.5)
        return False
    finally:
        observer.stop()
        observer.join()


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
        "--reload",
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


def _stdin_listener(core_port: int, stop: threading.Event, started: threading.Event) -> None:
    """Listen for keyboard shortcuts on stdin.

    Supported:
      d + enter -> open dev wizard in browser
    """
    import sys as _sys
    import subprocess as _sp
    import urllib.request as _url
    import threading as _th

    started.set()
    while not stop.is_set():
        try:
            line = _sys.stdin.readline()
            if not line:
                _th.Event().wait(0.5)
                continue
            cmd = line.strip().lower()

            if cmd == "d":
                # Open dev wizard in browser
                try:
                    _url.urlopen(f"http://localhost:{core_port}/api/setup/status", timeout=2)
                except Exception:
                    pass
                url = f"http://localhost:2099/"
                console.print(f"[info]Opening browser: {url}[/info]")
                if os.name == "nt":
                    _sp.Popen(["start", url], shell=True)
                else:
                    import subprocess as _sp2
                    try:
                        _sp2.Popen(["xdg-open", url])
                    except FileNotFoundError:
                        try:
                            _sp2.Popen(["open", url])
                        except FileNotFoundError:
                            pass
        except (EOFError, OSError):
            # Stdin closed (e.g., piped input)
            break


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

    # Sync web/package.json version from pyproject.toml (single source of truth)
    try:
        import re as _re
        pkg_path = Path(__file__).resolve().parent.parent.parent.parent / "web" / "package.json"
        if pkg_path.exists():
            pkg_text = pkg_path.read_text(encoding="utf-8")
            new_text = _re.sub(r'"version"\s*:\s*"[^"]+"', f'"version": "{version}"', pkg_text)
            if pkg_text != new_text:
                pkg_path.write_text(new_text, encoding="utf-8")  # UTF-8 without BOM
                console.print(f"  [dim]synced web/package.json -> {version}[/dim]")
    except Exception:
        pass  # Best-effort

    console.print()
    console.print(f"[brand]>> SynPin v{version} — Development Mode[/brand]")
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
        console.print("[warning]>> Shutting down...[/warning]")
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
    # NOTE: Do NOT register SIGTERM handler — uvicorn reloader sends SIGTERM
    # to restart the server process. Catching it here kills the reloader
    # and shuts down everything instead of hot-reloading.
    # if hasattr(signal, "SIGTERM"):
    #     signal.signal(signal.SIGTERM, _shutdown)

    # --- SIGINT handler: ignore if uvicorn is reloading ----------------
    # uvicorn's reloader sends SIGINT (signum=2) to the parent process
    # when it restarts the worker. The default _shutdown handler kills
    # everything, breaking hot-reload. Instead, we check if the core
    # port is still alive — if yes, it's a reload and we swallow the
    # signal. If the port is down, it's a real Ctrl+C and we shut down.

    def _sigint_handler(signum: int, frame) -> None:
        """Handle SIGINT: real Ctrl+C = shutdown, uvicorn reload = ignore."""
        import socket as _sock
        try:
            with _sock.socket(_sock.AF_INET, _sock.SOCK_STREAM) as s:
                s.settimeout(0.5)
                alive = s.connect_ex(("127.0.0.1", core_port)) == 0
        except OSError:
            alive = False
        if alive:
            # Port is still up — this is a uvicorn reload signal, not Ctrl+C
            console.print("[dim](SIGINT during reload — ignored)[/dim]")
            return
        # Port is down — real shutdown
        _shutdown(signum, frame)

    signal.signal(signal.SIGINT, _sigint_handler)

    # Strip ANSI escapes from child process output on Windows legacy
    # conhost. Modern Windows Terminal / pty-aware hosts render them
    # correctly, so we set this conservatively: on Unix we leave them
    # alone (the terminal is the source of truth), on Windows we strip
    # because the dev.bat -> dev.ps1 path lands on legacy conhost for
    # many users.
    strip_ansi = os.name == "nt"
    printer = threading.Thread(target=_output_printer, args=(output_queue, printer_stop, strip_ansi), daemon=True)
    printer.start()

    # Start stdin listener (daemon thread reads keyboard shortcuts)
    _listener_started = threading.Event()
    listener = threading.Thread(
        target=_stdin_listener,
        args=(core_port, printer_stop, _listener_started),
        daemon=True,
    )
    listener.start()

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
    # When uvicorn --reload restarts, the core process may exit and a
    # new one spawns on the same port. We detect reload by checking if
    # the port is still being served, rather than relying on poll().
    core_reloaded = False
    core_exit_time: float | None = None
    CORE_RELOAD_GRACE_S = 10.0  # uvicorn reload typically takes <5s

    def _port_alive(port: int) -> bool:
        """Check if something is listening on the given port."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.5)
                return s.connect_ex(("127.0.0.1", port)) == 0
        except OSError:
            return False

    try:
        while not printer_stop.is_set():
            for proc in processes:
                if proc.poll() is not None:
                    if proc is core_proc:
                        exit_code = proc.returncode
                        if exit_code == 0 and not core_reloaded:
                            # Clean exit — might be uvicorn reload
                            if core_exit_time is None:
                                core_exit_time = time.time()
                            if _port_alive(core_port):
                                console.print("[success]Core reloaded — watching for changes.[/success]")
                                core_reloaded = True
                                continue
                            if time.time() - core_exit_time > CORE_RELOAD_GRACE_S:
                                console.print(f"[error]❌ Core exited cleanly but port down for >{CORE_RELOAD_GRACE_S}s[/error]")
                                _shutdown()
                        elif exit_code != 0:
                            # Core crashed — bad code, skip reload
                            console.print(f"[error]❌ Core crashed (exit {exit_code}) — skipping reload. Fix the error and save.[/error]")
                            console.print("[dim]Waiting for file changes...[/dim]")
                            # Restart core — if it fails again, we'll catch it
                            try:
                                core_proc = _start_core(core_port)
                                processes[0] = core_proc
                                threading.Thread(target=_stream_output, args=(core_proc, "CORE", output_queue), daemon=True).start()
                                _wait_for_backend(core_port, core_proc)
                                if core_proc.poll() is not None:
                                    # Still crashing — wait for user to fix
                                    console.print("[dim]Core still crashing. Waiting for file change to retry...[/dim]")
                                    _wait_for_file_change()
                                    core_proc = _start_core(core_port)
                                    processes[0] = core_proc
                                    threading.Thread(target=_stream_output, args=(core_proc, "CORE", output_queue), daemon=True).start()
                                    _wait_for_backend(core_port, core_proc)
                                    if core_proc.poll() is None:
                                        console.print("[success]Core recovered after fix.[/success]")
                                        core_reloaded = True
                                    else:
                                        console.print("[error]❌ Core still crashing after fix. Shutting down.[/error]")
                                        _shutdown()
                                else:
                                    console.print("[success]Core restarted after crash.[/success]")
                                    core_reloaded = True
                                    core_exit_time = None
                            except Exception as e:
                                console.print(f"[error]Failed to restart core: {e}[/error]")
                                _shutdown()
                        # else: clean exit + already reloaded = ignore
                    elif proc is not core_proc:
                        # Web (Vite) exited
                        if core_reloaded and _port_alive(core_port):
                            console.print(f"[warning]⚠ Web exited (code {proc.returncode}), restarting...[/warning]")
                            new_web = _start_web(web_port, core_port)
                            processes[1] = new_web
                            threading.Thread(target=_stream_output, args=(new_web, "WEB", output_queue), daemon=True).start()
                        else:
                            console.print(f"[error]❌ Web exited with code {proc.returncode}[/error]")
                            _shutdown()

            # After first reload, monitor port for subsequent crashes
            if core_reloaded and not _port_alive(core_port):
                grace_start = time.time()
                while time.time() - grace_start < CORE_RELOAD_GRACE_S:
                    if _port_alive(core_port):
                        console.print("[success]Core reloaded.[/success]")
                        break
                    time.sleep(0.5)
                else:
                    console.print(f"[error]❌ Core port {core_port} down (real crash).[/error]")
                    _shutdown()

            time.sleep(0.5)
    except KeyboardInterrupt:
        _shutdown()
