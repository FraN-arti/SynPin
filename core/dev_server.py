#!/usr/bin/env python3
"""
SynPin Development Server
Starts both Core (FastAPI) and Web (Vite) in dev mode.
Shows unified console output with colored prefixes.
Ctrl+C stops both.

Usage: python core/dev_server.py
   or: dev.bat
"""

import os
import sys
import signal
import socket
import subprocess
import threading
from pathlib import Path
from queue import Queue, Empty

try:
    from colorama import init, Fore, Style
    init(strip=False)
except ImportError:
    class _Fake:
        RED = GREEN = YELLOW = CYAN = MAGENTA = WHITE = ""
        Style = type("Style", (), {"DIM": "", "NORMAL": "", "BRIGHT": ""})
    Fore = _Fake()
    Style = _Fake()

# Paths: this file is in core/, so ROOT is parent
ROOT = Path(__file__).resolve().parent.parent
CORE_DIR = ROOT / "core"
WEB_DIR = ROOT / "web"

CORE_HOST = "0.0.0.0"
CORE_PORT = 2088
WEB_PORT = 2099

processes: list[subprocess.Popen] = []
shutdown_event = threading.Event()


def find_free_port(start: int, max_attempts: int = 10) -> int:
    """Find a free port starting from `start`."""
    for port in range(start, start + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("0.0.0.0", port))
                return port
        except OSError:
            continue
    return start


def print_banner(core_port: int, web_port: int):
    print()
    print(f"  {Fore.CYAN}{Style.BRIGHT}╔══════════════════════════════════════════╗{Style.NORMAL}{Fore.RESET}")
    print(f"  {Fore.CYAN}{Style.BRIGHT}║{Style.NORMAL}{Fore.RESET}  {Fore.MAGENTA}{Style.BRIGHT}🚀 SynPin v0.1.0 — Development Mode{Style.NORMAL}{Fore.RESET}  {Fore.CYAN}{Style.BRIGHT}║{Style.NORMAL}{Fore.RESET}")
    print(f"  {Fore.CYAN}{Style.BRIGHT}╚══════════════════════════════════════════╝{Style.NORMAL}{Fore.RESET}")
    print()
    print(f"  {Fore.WHITE}{Style.DIM}Core:  http://{CORE_HOST}:{core_port}/api{Style.NORMAL}{Fore.RESET}")
    print(f"  {Fore.WHITE}{Style.DIM}Web:   http://localhost:{web_port}{Style.NORMAL}{Fore.RESET}")
    print(f"  {Fore.WHITE}{Style.DIM}Docs:  http://{CORE_HOST}:{core_port}/docs{Style.NORMAL}{Fore.RESET}")
    print()
    print(f"  {Fore.YELLOW}Press Ctrl+C to stop{Fore.RESET}")
    print()


def prefix_label(label: str, color: str) -> str:
    return f"  {color}[{label}]{Style.NORMAL} "


def stream_output(proc: subprocess.Popen, label: str, color: str, output_queue: Queue):
    """Read stdout/stderr from a process and put into queue with label."""
    pfx = prefix_label(label, color)

    def reader(stream, label_color):
        for line in iter(stream.readline, ""):
            if shutdown_event.is_set():
                break
            line = line.rstrip()
            if line:
                output_queue.put((label_color, line))

    t_out = threading.Thread(target=reader, args=(proc.stdout, color), daemon=True)
    t_err = threading.Thread(target=reader, args=(proc.stderr, Fore.RED), daemon=True)
    t_out.start()
    t_err.start()
    return t_out, t_err


def output_printer(output_queue: Queue):
    """Print lines from queue in order."""
    while not shutdown_event.is_set():
        try:
            color, line = output_queue.get(timeout=0.5)
            print(f"{color}{line}{Fore.RESET}", flush=True)
        except Empty:
            continue


def start_core(port: int) -> subprocess.Popen:
    """Start FastAPI core server."""
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    cmd = [
        sys.executable, "-u", "-m", "uvicorn",
        "synpin.api.server:app",
        "--host", CORE_HOST,
        "--port", str(port),
        "--log-level", "info",
    ]

    return subprocess.Popen(
        cmd,
        cwd=str(CORE_DIR),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )


def start_web(port: int) -> subprocess.Popen:
    """Start Vite dev server."""
    cmd = ["npm", "run", "dev", "--", "--port", str(port)]

    return subprocess.Popen(
        cmd,
        cwd=str(WEB_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        shell=True,
    )


def shutdown(signum=None, frame=None):
    """Gracefully stop all processes."""
    if shutdown_event.is_set():
        return
    shutdown_event.set()

    print(f"\n  {Fore.YELLOW}⏳  Shutting down...{Fore.RESET}")

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

    print(f"  {Fore.GREEN}✅  SynPin stopped{Fore.RESET}\n")
    sys.exit(0)


def main():
    # Check prerequisites
    if not (CORE_DIR / "pyproject.toml").exists():
        print(f"  {Fore.RED}❌  Core not found: {CORE_DIR}{Fore.RESET}")
        sys.exit(1)

    if not (WEB_DIR / "package.json").exists():
        print(f"  {Fore.RED}❌  Web not found: {WEB_DIR}{Fore.RESET}")
        sys.exit(1)

    # Check node_modules
    if not (WEB_DIR / "node_modules").exists():
        print(f"  {Fore.YELLOW}⚠️   Web dependencies not installed.{Fore.RESET}")
        print(f"  {Fore.YELLOW}    Run: cd web && npm install{Fore.RESET}")
        print()
        sys.exit(1)

    # Find free ports
    core_port = find_free_port(CORE_PORT)
    web_port = find_free_port(WEB_PORT)

    # Register signal handlers
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    print_banner(core_port, web_port)

    output_queue: Queue = Queue()

    # Start output printer thread
    printer = threading.Thread(target=output_printer, args=(output_queue,), daemon=True)
    printer.start()

    # Start Core
    print(f"  {Fore.CYAN}Starting Core...{Fore.RESET}")
    core_proc = start_core(core_port)
    processes.append(core_proc)
    stream_output(core_proc, "CORE", Fore.GREEN, output_queue)

    # Start Web
    print(f"  {Fore.CYAN}Starting Web...{Fore.RESET}")
    web_proc = start_web(web_port)
    processes.append(web_proc)
    stream_output(web_proc, "WEB", Fore.BLUE, output_queue)

    print()

    # Wait for processes
    try:
        while True:
            for proc in processes:
                if proc.poll() is not None:
                    print(f"\n  {Fore.RED}❌  Process exited with code {proc.returncode}{Fore.RESET}")
                    shutdown()
            if shutdown_event.is_set():
                break
            threading.Event().wait(0.5)
    except KeyboardInterrupt:
        shutdown()


if __name__ == "__main__":
    main()
