"""Single source of truth for current time across SynPin.

Every module that needs "now" should call `synpin.time.now()` instead of
`datetime.now()`.  This returns the machine's local time — whatever the
server OS clock shows.  No timezone math, no config, no magic.

Enhanced: supports optional timezone override via settings.yaml:
    server:
      timezone: "Europe/Moscow"
"""
from __future__ import annotations

import socket
import platform
from datetime import datetime


def _load_timezone() -> str | None:
    """Load timezone from settings.yaml, return None if not configured."""
    try:
        import yaml
        from pathlib import Path

        candidates = [
            Path.home() / ".synpin" / "config" / "settings.yaml",
            Path(__file__).resolve().parent / "config" / "settings.yaml",
        ]
        for p in candidates:
            if p.exists():
                with open(p, encoding="utf-8") as f:
                    cfg = yaml.safe_load(f) or {}
                tz = cfg.get("server", {}).get("timezone")
                if tz:
                    return str(tz)
        return None
    except Exception:
        return None


_cached_timezone: str | None = None
_timezone_loaded = False


def _get_timezone() -> str | None:
    """Get configured timezone (cached after first load)."""
    global _cached_timezone, _timezone_loaded
    if not _timezone_loaded:
        _cached_timezone = _load_timezone()
        _timezone_loaded = True
    return _cached_timezone


def reload_timezone() -> None:
    """Force reload timezone from config (call after settings change)."""
    global _cached_timezone, _timezone_loaded
    _timezone_loaded = False
    _cached_timezone = None


def now() -> datetime:
    """Return current machine time (naive, local)."""
    return datetime.now()


def now_iso() -> str:
    """Return current machine time as ISO string."""
    return now().isoformat()


def now_str() -> str:
    """Return current machine time as human-readable string."""
    return now().strftime("%Y-%m-%d %H:%M:%S")


def now_with_tz() -> dict:
    """Return current time with timezone info.

    Returns dict with:
        - datetime: current time string
        - timezone: configured timezone or "local"
        - timestamp: unix timestamp
        - weekday: day of week (ru)
    """
    current = now()
    tz = _get_timezone()
    weekday_ru = [
        "Понедельник", "Вторник", "Среда", "Четверг",
        "Пятница", "Суббота", "Воскресенье"
    ]
    return {
        "datetime": current.strftime("%Y-%m-%d %H:%M:%S"),
        "timezone": tz or "local",
        "timestamp": int(current.timestamp()),
        "weekday": weekday_ru[current.weekday()],
        "date": current.strftime("%Y-%m-%d"),
        "time": current.strftime("%H:%M:%S"),
    }


def get_system_info() -> dict:
    """Return system information for UI display and agent tools.

    Returns dict with:
        - hostname: machine hostname
        - platform: OS info
        - python_version: Python version
        - ip_addresses: list of local IPs
        - synpin_version: from synpin.__version__
        - uptime: server uptime string
    """
    import sys
    import time as _time

    # Get local IP addresses
    ips = []
    try:
        hostname = socket.gethostname()
        addr_info = socket.getaddrinfo(hostname, None, socket.AF_INET)
        seen = set()
        for info in addr_info:
            ip = info[4][0]
            if ip not in seen and not ip.startswith("127."):
                ips.append(ip)
                seen.add(ip)
    except Exception:
        pass

    if not ips:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.1)
            s.connect(("8.8.8.8", 80))
            ips.append(s.getsockname()[0])
            s.close()
        except Exception:
            ips.append("127.0.0.1")

    # SynPin version
    try:
        from synpin import __version__
        version = __version__
    except Exception:
        version = "unknown"

    # Uptime
    try:
        from .api.stats_router import _SERVER_START
        uptime_s = int(_time.time() - _SERVER_START)
        days = uptime_s // 86400
        hours = (uptime_s % 86400) // 3600
        mins = (uptime_s % 3600) // 60
        if days > 0:
            uptime = f"{days}d {hours}h {mins}m"
        elif hours > 0:
            uptime = f"{hours}h {mins}m"
        else:
            uptime = f"{mins}m"
    except Exception:
        uptime = "unknown"

    return {
        "hostname": socket.gethostname(),
        "platform": f"{platform.system()} {platform.release()}",
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "ip_addresses": ips,
        "synpin_version": version,
        "uptime": uptime,
        "time": now_with_tz(),
    }
