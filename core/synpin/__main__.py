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
    port = int(os.environ.get("SYNPIN_PORT", "8000"))

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

    port = int(os.environ.get("SYNPIN_PORT", "8000"))
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
        print("  version   Show version")
        print()
        return

    command = sys.argv[1]
    commands[command](sys.argv[2:])


if __name__ == "__main__":
    main()
