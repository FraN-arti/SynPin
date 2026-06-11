"""SynPin CLI entry point.

Usage:
    synpin start      Start SynPin server
    synpin stop       Stop running SynPin
    synpin status     Show server status
    synpin config     Show/edit configuration
    synpin logs       Show server logs
    synpin version    Show version
    synpin setup      Initial setup wizard
    synpin update     Update from GitHub
    synpin doctor     Health check
"""
import sys
from .cli.commands import (
    cmd_start, cmd_stop, cmd_status, cmd_version,
    cmd_config, cmd_setup, cmd_update, cmd_logs, cmd_doctor,
)
from .cli.console import console


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
        "doctor": cmd_doctor,
    }

    if len(sys.argv) < 2 or sys.argv[1] not in commands:
        console.print("[brand]SynPin[/brand] — Multi-Agent Framework")
        console.print()
        console.print("[dim]Usage:[/dim] synpin <command>")
        console.print()
        for name, fn in commands.items():
            doc = (fn.__doc__ or "").strip()
            console.print(f"  [cyan]{name:12}[/cyan] {doc}")
        console.print()
        return

    commands[sys.argv[1]](sys.argv[2:])


if __name__ == "__main__":
    main()
