"""SynPin CLI commands with Rich output."""
import sys
import os
import json
import subprocess
import time
from pathlib import Path
from .console import console

VERSION = "0.2.2"


def _runtime_dir() -> Path:
    """Where to write SynPin runtime files (pid, logs).

    Resolves through paths.py so dev and prod share the same
    folder layout (the install dir IS the dev dir). Falls back
    to ~/.synpin for legacy compatibility but new code should
    never write outside the install dir.
    """
    from ..paths import get_user_data_dir
    return get_user_data_dir()


def _get_version() -> str:
    """Read version from pyproject.toml or installed package."""
    # Try pyproject.toml first (dev mode)
    try:
        import tomllib
        pyproject = Path(__file__).resolve().parent.parent.parent / "pyproject.toml"
        if pyproject.exists():
            with open(pyproject, "rb") as f:
                data = tomllib.load(f)
                return data.get("project", {}).get("version", VERSION)
    except Exception:
        pass
    # Fallback to installed package
    try:
        import importlib.metadata
        return importlib.metadata.version("synpin-core")
    except Exception:
        return VERSION


def cmd_start(args):
    """Start SynPin server.

    By default the startup output is compact: only the header and a few
    key events. WebSocket connect/disconnect and per-file watcher lines
    are suppressed. Pass --verbose / -v to see every uvicorn INFO line
    (useful when something fails to start).
    """
    import uvicorn

    host = os.environ.get("SYNPIN_HOST", "0.0.0.0")
    port = int(os.environ.get("SYNPIN_PORT", "2088"))
    version = _get_version()

    # --verbose / -v : show full uvicorn output. Default is compact.
    verbose = any(a in ("--verbose", "-v") for a in args)

    # Kill existing process on port
    pid_file = _runtime_dir() / "synpin.pid"
    if os.name == "nt":
        result = subprocess.run(
            ["netstat", "-ano"], capture_output=True, text=True, errors="replace"
        )
        if result.stdout:
            for line in result.stdout.splitlines():
                if f":{port}" in line and "LISTENING" in line:
                    parts = line.split()
                    if parts:
                        old_pid = parts[-1]
                        console.print(f"[dim]Port {port} in use (PID {old_pid}) - stopping...[/dim]")
                        subprocess.run(["taskkill", "/F", "/PID", old_pid], capture_output=True)
                        time.sleep(1)
                        break

    if pid_file.exists():
        pid_file.unlink()

    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(json.dumps({"pid": os.getpid(), "port": port}))

    # Structured startup banner — compact width matching content.
    from rich import box as rich_box
    from rich.panel import Panel

    console.print()
    console.print(
        Panel(
            f"[brand]SynPin v{version}[/brand]  [dim]·  Multi-agent workspace[/dim]\n\n"
            f"  [accent]API[/accent]   http://localhost:{port}\n"
            f"  [accent]Web[/accent]   http://localhost:{port}\n"
            f"  [accent]Docs[/accent]  http://localhost:{port}/docs",
            border_style="brand",
            box=rich_box.ROUNDED,
            padding=(1, 2),
            width=44,
        )
    )
    console.print()

    # "Готов к работе" line — printed before uvicorn starts so the user
    # sees it immediately under the banner. Uvicorn output is suppressed
    # in non-verbose mode (WARNING level), so this is the last visible line.
    if not verbose:
        console.print(
            f"  [accent]● Готов к работе.[/accent]"
            f"  [dim]Нажмите Ctrl+C для остановки.[/dim]"
        )
        console.print()

    # Per-logger levels. By default we want a quiet startup:
    #   - uvicorn.access WARNING: no per-WS-connect spam
    #   - synpin logger WARNING: only the important things bubble up
    #     (the rich startup summary is printed directly to console from
    #     lifespan, so we don't need logger.info for those steps).
    # --verbose flips everything to INFO so debugging a broken startup
    # still gives you the full picture.
    access_level = "INFO" if verbose else "WARNING"
    synpin_level = "INFO" if verbose else "WARNING"
    uvicorn_level = "INFO" if verbose else "WARNING"

    log_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "rich": {
                "format": "%(message)s",
                "datefmt": "[%X]",
            }
        },
        "handlers": {
            "rich": {
                "class": "rich.logging.RichHandler",
                "formatter": "rich",
                "console": console,            # reuse the brand console
                "rich_tracebacks": True,
                "show_path": False,
                "show_time": verbose,          # timestamps only when verbose
                "markup": True,
                "log_time_format": "[%X]",
            }
        },
        "loggers": {
            "uvicorn":        {"handlers": ["rich"], "level": uvicorn_level, "propagate": False},
            "uvicorn.error":  {"handlers": ["rich"], "level": uvicorn_level, "propagate": False},
            "uvicorn.access": {"handlers": ["rich"], "level": access_level, "propagate": False},
            "synpin":         {"handlers": ["rich"], "level": synpin_level, "propagate": False},
        },
    }

    try:
        uvicorn.run(
            "synpin.api.server:app",
            host=host,
            port=port,
            reload=False,
            log_config=log_config,
        )
    finally:
        if pid_file.exists():
            pid_file.unlink()


def cmd_stop(args):
    """Stop running SynPin instance."""
    console.print("[dim]⏳  Stopping SynPin...[/dim]")

    pid_file = _runtime_dir() / "synpin.pid"

    if pid_file.exists():
        try:
            data = json.loads(pid_file.read_text())
            pid = data.get("pid")
            if pid:
                if os.name == "nt":
                    subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
                else:
                    os.kill(pid, 9)
                console.print("[success]✅  SynPin stopped[/success]")
                pid_file.unlink(missing_ok=True)
                return
        except Exception:
            pass

    port = int(os.environ.get("SYNPIN_PORT", "2088"))
    if os.name == "nt":
        result = subprocess.run(
            ["netstat", "-ano"], capture_output=True, text=True, errors="replace"
        )
        if result.stdout:
            for line in result.stdout.splitlines():
                if f":{port}" in line and "LISTENING" in line:
                    parts = line.split()
                    if parts:
                        subprocess.run(["taskkill", "/F", "/PID", parts[-1]], capture_output=True)
                        console.print("[success]✅  SynPin stopped[/success]")
                        pid_file.unlink(missing_ok=True)
                        return
    else:
        subprocess.run(["fuser", "-k", f"{port}/tcp"], capture_output=True)

    console.print("[success]✅  SynPin stopped (was not running)[/success]")


def cmd_status(args):
    """Show server status."""
    import urllib.request

    port = int(os.environ.get("SYNPIN_PORT", "2088"))
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=2)
        console.print(f"[success]✅  SynPin is running on port {port}[/success]")
    except Exception:
        console.print("[error]❌  SynPin is not running[/error]")


def cmd_version(args):
    """Show version."""
    version = _get_version()
    console.print(f"[brand]SynPin v{version}[/brand]")


def cmd_config(args):
    """Show configuration."""
    config_dir = _runtime_dir()
    config_file = config_dir / "config.yaml"

    console.print(f"[dim]Config directory:[/dim] {config_dir}")

    if config_file.exists():
        console.print(f"[dim]Config file:[/dim] {config_file}")
        console.print()
        console.print(config_file.read_text())
    else:
        console.print("No config file found. Start the server to launch the setup wizard.")


def cmd_update(args):
    """Update SynPin from GitHub and reinstall changed components.

    The current install layout has SynPin as a git-cloned repo
    (not a copy under ~/.synpin/repo), so the update flow is:
    1. 'git pull' inside the repo the user is running from,
    2. detect which parts changed (core / web / scripts),
    3. reinstall only the changed parts (pip install -e core,
       npm install in web, or nothing if neither changed).
    """

    # The repo the user is running from. We get this from the
    # location of the synpin-core package install (editable mode
    # preserves the original path), which is the cleanest way to
    # detect the active repo even when the user invoked us via
    # `synpin` (which resolves through pip's installed paths).
    synpin_pkg = Path(__file__).resolve().parent.parent
    # synpin/cli/commands.py is at core/synpin/cli/, so .parent.parent
    # lands at core/synpin/ — go one more step up to the repo root.
    repo_dir = synpin_pkg.parent.parent
    # The package lives in core/synpin/ inside the repo.

    # Make sure we're actually inside a git repo before we run
    # destructive operations.
    if not (repo_dir / ".git").exists():
        console.print(
            f"[error]ERROR: Not a git repository: {repo_dir}[/error]\n"
            "[dim]Run 'synpin update' from inside the cloned SynPin repo "
            "(the one with .git/, dev.bat, install.sh etc).[/dim]"
        )
        return

    console.print(f"[dim]Repo: {repo_dir}[/dim]")
    console.print("[dim]Checking for updates...[/dim]")
    console.print()

    result = subprocess.run(
        ["git", "pull", "--rebase", "--autostash"],
        cwd=str(repo_dir), capture_output=True, text=True,
    )
    if result.returncode != 0:
        console.print(f"[error]ERROR: git pull failed:\n{result.stderr}[/error]")
        return

    if "Already up to date" in result.stdout:
        console.print("[success]Already up to date. Nothing to do.[/success]")
        return

    console.print("[success]Updates downloaded![/success]")
    console.print()

    # Detect what changed since the last fetch position.
    core_changed = False
    web_changed = False
    other_changed = False

    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD@{1}", "HEAD"],
        cwd=str(repo_dir), capture_output=True, text=True,
    )
    if result.returncode == 0:
        for f in result.stdout.strip().split("\n"):
            if f.startswith("core/"):
                core_changed = True
            elif f.startswith("web/"):
                web_changed = True
            else:
                other_changed = True
    else:
        # If we can't diff (e.g. no previous HEAD@{1}), just treat
        # the whole thing as "something changed" and reinstall both.
        core_changed = web_changed = other_changed = True

    if core_changed:
        console.print("[info]Core changed — reinstalling Python package...[/info]")
        rc = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-e", str(repo_dir / "core"), "--quiet"],
            capture_output=True, text=True,
        )
        if rc.returncode != 0:
            console.print(f"[error]ERROR: pip install failed:\n{rc.stderr}[/error]")
        else:
            console.print("  [success]OK: Core reinstalled[/success]")
        console.print()

    if web_changed:
        web_dir = repo_dir / "web"
        if (web_dir / "package.json").exists():
            if (web_dir / "node_modules").exists():
                console.print("[info]Web changed — running npm install...[/info]")
                rc = subprocess.run(
                    ["npm", "install", "--no-fund", "--no-audit"],
                    cwd=str(web_dir), capture_output=True, text=True,
                    shell=(os.name == "nt"),
                )
                if rc.returncode != 0:
                    console.print(f"[error]ERROR: npm install failed:\n{rc.stderr}[/error]")
                else:
                    console.print("  [success]OK: Web dependencies updated[/success]")

                console.print("[info]Building frontend (npm run build)...[/info]")
                rc = subprocess.run(
                    ["npm", "run", "build"],
                    cwd=str(web_dir), capture_output=True, text=True,
                    shell=(os.name == "nt"),
                )
                if rc.returncode != 0:
                    console.print(f"[error]ERROR: npm run build failed:\n{rc.stderr}[/error]")
                else:
                    console.print("  [success]OK: Frontend built[/success]")
            else:
                console.print(
                    "[info]Web changed but web/node_modules is missing. "
                    "Run 'cd web && npm install' once.[/info]"
                )
        else:
            console.print("[info]Web changed but no package.json found, skipping.[/info]")
        console.print()

    if other_changed and not core_changed and not web_changed:
        # Only docs / scripts / etc. changed — no rebuild needed.
        console.print(
            "[dim]Only docs/scripts changed — no rebuild required.[/dim]\n"
            "  [success]OK: Files updated[/success]"
        )
        console.print()

    console.print("[brand]========================================[/brand]")
    console.print("[brand]  Update complete![/brand]")
    console.print("[brand]========================================[/brand]")
    console.print()
    console.print("  [dim]Restart with: synpin start[/dim]  (or  synpin dev)")
    console.print()


def cmd_logs(args):
    """Show server logs."""
    log_dir = _runtime_dir() / "logs"
    log_file = log_dir / "synpin.log"

    if not log_file.exists():
        console.print("[warning]No logs found.[/warning]")
        return

    lines = log_file.read_text().splitlines()
    for line in lines[-50:]:
        console.print(line)


def cmd_doctor(args):
    """Health check — verify everything is installed correctly."""
    from rich.table import Table

    table = Table(title="SynPin Doctor", show_header=True, header_style="bold cyan")
    table.add_column("Check", style="cyan", width=16)
    table.add_column("Status", width=10)
    table.add_column("Details", style="dim")

    # Python
    try:
        import sys
        py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        ok = sys.version_info >= (3, 11)
        table.add_row("Python", "[success]✅ OK[/success]" if ok else "[error]❌ FAIL[/error]", py_ver)
    except Exception as e:
        table.add_row("Python", "[error]❌ FAIL[/error]", str(e))

    # Node.js (on Windows needs shell=True)
    try:
        node_cmd = ["node", "--version"] if os.name != "nt" else ["cmd", "/c", "node", "--version"]
        result = subprocess.run(node_cmd, capture_output=True, text=True, timeout=5, shell=(os.name == "nt"))
        node_ver = result.stdout.strip()
        table.add_row("Node.js", "[success]✅ OK[/success]" if result.returncode == 0 else "[error]❌ FAIL[/error]", node_ver)
    except FileNotFoundError:
        table.add_row("Node.js", "[error]❌ FAIL[/error]", "not installed")
    except Exception as e:
        table.add_row("Node.js", "[error]❌ FAIL[/error]", str(e))

    # npm (on Windows needs .cmd extension or shell=True)
    try:
        npm_cmd = ["npm", "--version"] if os.name != "nt" else ["cmd", "/c", "npm", "--version"]
        result = subprocess.run(npm_cmd, capture_output=True, text=True, timeout=5, shell=(os.name == "nt"))
        npm_ver = result.stdout.strip()
        table.add_row("npm", "[success]✅ OK[/success]" if result.returncode == 0 and npm_ver else "[error]❌ FAIL[/error]", npm_ver or "not installed")
    except FileNotFoundError:
        table.add_row("npm", "[error]❌ FAIL[/error]", "not installed")
    except Exception as e:
        table.add_row("npm", "[error]❌ FAIL[/error]", str(e))

    # Backend port
    port = int(os.environ.get("SYNPIN_PORT", "2088"))
    try:
        import urllib.request
        urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=2)
        table.add_row("Backend", "[success]✅ OK[/success]", f"Port {port}")
    except Exception:
        table.add_row("Backend", "[warning]⚠️  OFF[/warning]", f"Port {port} not responding")

    # Frontend port
    try:
        import urllib.request
        urllib.request.urlopen("http://127.0.0.1:2099", timeout=2)
        table.add_row("Frontend", "[success]✅ OK[/success]", "Port 2099")
    except Exception:
        table.add_row("Frontend", "[warning]⚠️  OFF[/warning]", "Port 2099 not responding")

    # Config files
    config_dir = _runtime_dir() / "config"
    configs = ["agents.yaml", "otdels.yaml", "providers.yaml", "settings.yaml"]
    found = sum(1 for c in configs if (config_dir / c).exists())
    total = len(configs)
    status = "[success]✅ OK[/success]" if found == total else "[warning]⚠️  PARTIAL[/warning]"
    table.add_row("Config", status, f"{found}/{total} files in {config_dir}")

    # Git
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=5,
            cwd=str(Path(__file__).resolve().parent.parent.parent.parent),
        )
        branch = result.stdout.strip()
        table.add_row("Git", "[success]✅ OK[/success]" if result.returncode == 0 else "[warning]⚠️[/warning]", branch)
    except Exception:
        table.add_row("Git", "[warning]⚠️[/warning]", "unknown")

    console.print(table)


def cmd_dev(args):
    """Run Core + Web together with unified output (dev mode)."""
    from .dev import run_dev_server
    run_dev_server()
