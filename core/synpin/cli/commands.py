"""SynPin CLI commands with Rich output."""
import sys
import os
import json
import subprocess
import time
from pathlib import Path
from .console import console

VERSION = "0.2.2"
SYNPIN_HOME = Path.home() / ".synpin"


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
    """Start SynPin server."""
    import uvicorn

    host = os.environ.get("SYNPIN_HOST", "0.0.0.0")
    port = int(os.environ.get("SYNPIN_PORT", "2088"))
    version = _get_version()

    # Kill existing process on port
    pid_file = SYNPIN_HOME / "synpin.pid"
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
                        console.print(f"[dim]⏳  Port {port} in use (PID {old_pid}) — stopping...[/dim]")
                        subprocess.run(["taskkill", "/F", "/PID", old_pid], capture_output=True)
                        time.sleep(1)
                        break

    if pid_file.exists():
        pid_file.unlink()

    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(json.dumps({"pid": os.getpid(), "port": port}))

    console.print()
    console.print(f"[brand]🚀  SynPin v{version}[/brand]")
    console.print(f"   [dim]API:  http://{host}:{port}/api[/dim]")
    console.print(f"   [dim]Web:  http://{host}:{port}[/dim]")
    console.print(f"   [dim]Docs: http://{host}:{port}/docs[/dim]")
    console.print()

    try:
        uvicorn.run(
            "synpin.api.server:app",
            host=host,
            port=port,
            reload=False,
        )
    finally:
        if pid_file.exists():
            pid_file.unlink()


def cmd_stop(args):
    """Stop running SynPin instance."""
    console.print("[dim]⏳  Stopping SynPin...[/dim]")

    pid_file = SYNPIN_HOME / "synpin.pid"

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
        console.print(f"[error]❌  SynPin is not running[/error]")


def cmd_version(args):
    """Show version."""
    version = _get_version()
    console.print(f"[brand]SynPin v{version}[/brand]")


def cmd_config(args):
    """Show configuration."""
    config_dir = SYNPIN_HOME
    config_file = config_dir / "config.yaml"

    console.print(f"[dim]Config directory:[/dim] {config_dir}")

    if config_file.exists():
        console.print(f"[dim]Config file:[/dim] {config_file}")
        console.print()
        console.print(config_file.read_text())
    else:
        console.print("[warning]No config file found. Run 'synpin setup' to create one.[/warning]")


def cmd_setup(args):
    """Initial setup wizard."""
    from rich.panel import Panel
    from rich.prompt import Prompt, Confirm

    config_dir = SYNPIN_HOME
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "config.yaml"

    if config_file.exists():
        console.print("[warning]⚠️   Config already exists. Delete it first to re-run setup.[/warning]")
        return

    version = _get_version()
    console.print(Panel.fit(
        f"[brand]🔧 SynPin Setup Wizard v{version}[/brand]",
        border_style="green"
    ))
    console.print()

    api_url = Prompt.ask("LLM API URL", default="http://localhost:1234/v1")
    model = Prompt.ask("Model name", default="default")
    port = Prompt.ask("Server port", default="2088")

    import yaml
    config = {
        "api_url": api_url,
        "model": model,
        "port": int(port),
    }
    config_file.write_text(yaml.dump(config, default_flow_style=False))
    console.print(f"\n[success]✅  Config saved to {config_file}[/success]")


def cmd_update(args):
    """Update SynPin from GitHub and rebuild if needed."""
    import shutil

    repo_dir = SYNPIN_HOME / "repo"

    if not repo_dir.exists():
        console.print("[error]ERROR: SynPin not installed. Run install.ps1 first.[/error]")
        return

    console.print("[dim]Checking for updates...[/dim]")
    console.print()

    result = subprocess.run(
        ["git", "pull"], cwd=str(repo_dir), capture_output=True, text=True
    )

    if result.returncode != 0:
        console.print(f"[error]ERROR: git pull failed:\n{result.stderr}[/error]")
        return

    if "Already up to date" in result.stdout:
        console.print("[success]Already up to date. Nothing to do.[/success]")
        return

    console.print("[success]Updates downloaded![/success]")
    console.print()

    core_changed = False
    web_changed = False

    result = subprocess.run(
        ["git", "rev-parse", "--verify", "ORIG_HEAD"],
        cwd=str(repo_dir), capture_output=True, text=True,
    )
    old_head = result.stdout.strip() if result.returncode == 0 else "HEAD@{1}"

    result = subprocess.run(
        ["git", "diff", "--name-only", old_head, "HEAD"],
        cwd=str(repo_dir), capture_output=True, text=True,
    )

    if result.returncode == 0:
        for f in result.stdout.strip().split("\n"):
            if f.startswith("core/"):
                core_changed = True
            if f.startswith("web/"):
                web_changed = True

    venv_python = synpin_home / "core" / ".venv" / "Scripts" / "python.exe"
    if not venv_python.exists():
        venv_python = synpin_home / "core" / ".venv" / "bin" / "python"

    if core_changed:
        console.print("[info]Core changed — updating Python dependencies...[/info]")
        src_core = repo_dir / "core"
        dst_core = synpin_home / "core"
        if src_core.exists():
            def ignore_venv(dir, contents):
                return [".venv"] if ".venv" in contents else []
            shutil.copytree(src_core, dst_core, dirs_exist_ok=True, ignore=ignore_venv)

        console.print("  [dim]Installing package...[/dim]")
        subprocess.run(
            ["uv", "pip", "install", "-e", str(synpin_home / "core"),
             "--python", str(venv_python)],
            capture_output=True,
        )
        console.print("  [success]OK: Core updated[/success]")
        console.print()

    if web_changed:
        console.print("[info]Web changed — rebuilding UI...[/info]")
        src_web = repo_dir / "web"
        dst_web = synpin_home / "web"
        if src_web.exists():
            def ignore_web(dir, contents):
                return [d for d in ["node_modules", "dist"] if d in contents]
            shutil.copytree(src_web, dst_web, dirs_exist_ok=True, ignore=ignore_web)

        console.print("  [dim]Building...[/dim]")
        import platform
        cmd = "npx vite build" if platform.system() == "Windows" else ["npx", "vite", "build"]
        result = subprocess.run(
            cmd, cwd=str(dst_web), capture_output=True, text=True,
            shell=(platform.system() == "Windows"),
        )
        if result.returncode != 0:
            console.print(f"  [error]ERROR: Build failed:\n{result.stderr}[/error]")
        else:
            console.print("  [success]OK: Web rebuilt[/success]")
        console.print()

    if not core_changed and not web_changed:
        console.print("[dim]Copying updated files...[/dim]")
        for item in repo_dir.iterdir():
            if item.name in (".git", "node_modules", ".venv"):
                continue
            dst = synpin_home / item.name
            if item.is_dir():
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(item, dst)
            else:
                shutil.copy2(item, dst)
        console.print("  [success]OK: Files updated[/success]")
        console.print()

    console.print("[brand]========================================[/brand]")
    console.print("[brand]  Update complete![/brand]")
    console.print("[brand]========================================[/brand]")
    console.print()
    console.print("  [dim]Restart with: synpin start[/dim]")
    console.print()


def cmd_logs(args):
    """Show server logs."""
    log_dir = SYNPIN_HOME / "logs"
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
        urllib.request.urlopen(f"http://127.0.0.1:2099", timeout=2)
        table.add_row("Frontend", "[success]✅ OK[/success]", "Port 2099")
    except Exception:
        table.add_row("Frontend", "[warning]⚠️  OFF[/warning]", "Port 2099 not responding")

    # Config files
    config_dir = SYNPIN_HOME / "config"
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
