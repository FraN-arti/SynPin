"""SynPin CLI entry point.

Usage:
    synpin start      Start SynPin server
    synpin stop       Stop running SynPin
    synpin status     Show server status
    synpin config     Show/edit configuration
    synpin logs       Show server logs
    synpin version    Show version
    synpin setup      Initial setup wizard
"""

import sys
import os
from pathlib import Path


def cmd_start(args):
    """Start SynPin production server."""
    import uvicorn

    host = os.environ.get("SYNPIN_HOST", "0.0.0.0")
    port = int(os.environ.get("SYNPIN_PORT", "2088"))

    print(f"🚀 SynPin v0.1.0")
    print(f"   API:  http://{host}:{port}/api")
    print(f"   Web:  http://{host}:{port}")
    print(f"   Docs: http://{host}:{port}/docs")
    print()

    uvicorn.run(
        "synpin.api.server:app",
        host=host,
        port=port,
        reload=False,
    )


def cmd_stop(args):
    """Stop running SynPin instance."""
    import subprocess

    print("⏳  Stopping SynPin...")

    # Find and kill synpin uvicorn processes
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/F", "/IM", "python.exe", "/FI", "WINDOWTITLE eq SynPin*"],
            capture_output=True,
        )
    else:
        subprocess.run(["pkill", "-f", "synpin"], capture_output=True)

    print("✅  SynPin stopped")


def cmd_status(args):
    """Show server status."""
    import urllib.request

    port = int(os.environ.get("SYNPIN_PORT", "2088"))
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=2)
        print(f"✅  SynPin is running on port {port}")
    except Exception:
        print(f"❌  SynPin is not running")


def cmd_version(args):
    """Show version."""
    print("SynPin v0.1.0")


def cmd_config(args):
    """Show configuration."""
    config_dir = Path.home() / ".synpin"
    config_file = config_dir / "config.yaml"

    print(f"Config directory: {config_dir}")

    if config_file.exists():
        print(f"Config file: {config_file}")
        print(config_file.read_text())
    else:
        print("No config file found. Run 'synpin setup' to create one.")


def cmd_setup(args):
    """Initial setup wizard."""
    from pathlib import Path

    config_dir = Path.home() / ".synpin"
    config_dir.mkdir(parents=True, exist_ok=True)

    config_file = config_dir / "config.yaml"

    if config_file.exists():
        print("⚠️   Config already exists. Delete it first to re-run setup.")
        return

    print("🔧 SynPin Setup Wizard")
    print()

    # Ask for LLM API URL
    api_url = input("LLM API URL [http://localhost:1234/v1]: ").strip()
    if not api_url:
        api_url = "http://localhost:1234/v1"

    # Ask for model name
    model = input("Model name [default]: ").strip()
    if not model:
        model = "default"

    # Ask for port
    port = input("Server port [8000]: ").strip()
    if not port:
        port = "8000"

    import yaml
    config = {
        "api_url": api_url,
        "model": model,
        "port": int(port),
    }

    config_file.write_text(yaml.dump(config, default_flow_style=False))
    print(f"\n✅  Config saved to {config_file}")


def cmd_update(args):
    """Update SynPin from GitHub and rebuild if needed."""
    import subprocess
    import shutil

    synpin_home = Path.home() / ".synpin"
    repo_dir = synpin_home / "repo"

    if not repo_dir.exists():
        print("ERROR: SynPin not installed. Run install.ps1 first.")
        return

    print("Checking for updates...")
    print()

    # Step 1: Git pull
    result = subprocess.run(
        ["git", "pull"],
        cwd=str(repo_dir),
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"ERROR: git pull failed:\n{result.stderr}")
        return

    if "Already up to date" in result.stdout:
        print("Already up to date. Nothing to do.")
        return

    print("Updates downloaded!")
    print()

    # Step 2: Check what changed
    core_changed = False
    web_changed = False

    # Check changed files
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD@{1}", "HEAD"],
        cwd=str(repo_dir),
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        changed_files = result.stdout.strip().split("\n")
        for f in changed_files:
            if f.startswith("core/"):
                core_changed = True
            if f.startswith("web/"):
                web_changed = True

    # Step 3: Rebuild as needed
    venv_python = synpin_home / "core" / ".venv" / "Scripts" / "python.exe"

    if core_changed:
        print("Core changed - updating Python dependencies...")
        # Copy updated core files
        src_core = repo_dir / "core"
        dst_core = synpin_home / "core"
        if src_core.exists():
            # Copy core directory (excluding .venv)
            for item in src_core.iterdir():
                if item.name == ".venv":
                    continue
                dst = dst_core / item.name
                if dst.exists():
                    if dst.is_dir():
                        shutil.rmtree(dst)
                    else:
                        dst.unlink()
                if item.is_dir():
                    shutil.copytree(item, dst)
                else:
                    shutil.copy2(item, dst)

        # Reinstall package
        print("  Installing package...")
        subprocess.run(
            ["uv", "pip", "install", "-e", str(synpin_home / "core"),
             "--python", str(venv_python)],
            capture_output=True,
        )
        print("  OK: Core updated")
        print()

    if web_changed:
        print("Web changed - rebuilding UI...")
        # Copy updated web source
        src_web = repo_dir / "web"
        dst_web = synpin_home / "web"
        # Copy source files (not node_modules, dist)
        for item in src_web.iterdir():
            if item.name in ("node_modules", "dist"):
                continue
            dst = dst_web / item.name
            if dst.exists():
                if dst.is_dir():
                    shutil.rmtree(dst)
                else:
                    dst.unlink()
            if item.is_dir():
                shutil.copytree(item, dst)
            else:
                shutil.copy2(item, dst)

        # Rebuild
        print("  Building...")
        subprocess.run(
            ["npm", "run", "build"],
            cwd=str(dst_web),
            capture_output=True,
        )
        print("  OK: Web rebuilt")
        print()

    if not core_changed and not web_changed:
        # Just copy changed files (wiki, docs, etc.)
        print("Copying updated files...")
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
        print("  OK: Files updated")
        print()

    print("========================================")
    print("  Update complete!")
    print("========================================")
    print()
    print("  Restart with: synpin start")
    print()


def cmd_logs(args):
    """Show server logs."""
    log_dir = Path.home() / ".synpin" / "logs"
    log_file = log_dir / "synpin.log"

    if not log_file.exists():
        print("No logs found.")
        return

    # Show last 50 lines
    lines = log_file.read_text().splitlines()
    for line in lines[-50:]:
        print(line)


def main():
    commands = {
        "start": cmd_start,
        "stop": cmd_stop,
        "status": cmd_status,
        "version": cmd_version,
        "config": cmd_config,
        "setup": cmd_setup,
        "update": cmd_update,
        "logs": cmd_logs,
    }

    if len(sys.argv) < 2 or sys.argv[1] not in commands:
        print("Usage: synpin <command>")
        print()
        print("Commands:")
        print("  start     Start SynPin server")
        print("  stop      Stop running SynPin")
        print("  status    Show server status")
        print("  config    Show/edit configuration")
        print("  logs      Show server logs")
        print("  setup     Initial setup wizard")
        print("  update    Update from GitHub and rebuild")
        print("  version   Show version")
        print()
        return

    command = sys.argv[1]
    commands[command](sys.argv[2:])


if __name__ == "__main__":
    main()
