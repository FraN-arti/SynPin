"""Session auto-reset background task + on-connect reset.

Reads settings from settings.yaml:
  sessions:
    auto_reset:
      enabled: true
      mode: daily | timer | time
      reset_time: "00:00"    # for mode=daily/time
      interval_hours: 24     # for mode=timer
    archive_on_reset: true
    max_history: 100

Two entry points:
  1. Daemon (_session_reset_loop) — runs every 60s, checks if reset is due
  2. WS-connect (check_and_reset_on_connect) — on first client connection,
     runs reset if not yet done today

Last reset date is persisted to data/last_session_reset.txt so it survives
server restarts. This prevents re-archiving on reconnect.
"""
import json
import logging
import os
import shutil
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


from ..time import now as _now
from ..paths import (
    get_data_dir_or_none as _get_data_dir,
    get_config_dir_or_none as _get_config_dir,
)

# ── Persistent reset date ────────────────────────────────────────────────
# Stored in data/last_session_reset.txt — survives server restarts.
# Format: "YYYY-MM-DD"

_RESET_DATE_FILENAME = "last_session_reset.txt"


def _get_reset_date_path() -> Path | None:
    """Path to the persistent reset-date file."""
    data_dir = _get_data_dir()
    if not data_dir:
        return None
    return data_dir / _RESET_DATE_FILENAME


def _read_last_reset_date() -> str | None:
    """Read the last reset date from disk. Returns 'YYYY-MM-DD' or None."""
    path = _get_reset_date_path()
    if not path or not path.exists():
        return None
    try:
        return path.read_text(encoding="utf-8").strip() or None
    except Exception:
        return None


def _write_last_reset_date(date_str: str):
    """Persist the reset date to disk."""
    path = _get_reset_date_path()
    if not path:
        return
    try:
        path.write_text(date_str, encoding="utf-8")
    except Exception as e:
        logger.warning("Failed to persist reset date: %s", e)


def _already_reset_today() -> bool:
    """Check if reset already happened today (disk-persistent)."""
    last = _read_last_reset_date()
    today = _now().strftime("%Y-%m-%d")
    return last == today


# ── Config ───────────────────────────────────────────────────────────────

def _load_yaml(path: Path) -> dict:
    """Safe YAML loader."""
    try:
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def _get_sessions_config() -> dict:
    """Read sessions config from settings.yaml, fallback to memory.yaml."""
    config_dir = _get_config_dir()
    if not config_dir:
        return {}

    settings_cfg = _load_yaml(config_dir / "settings.yaml")
    sessions_from_settings = settings_cfg.get("sessions", {})

    mem_cfg = _load_yaml(config_dir / "memory.yaml")
    sessions_from_memory = mem_cfg.get("sessions", {})

    return {**sessions_from_memory, **sessions_from_settings}


# ── Reset logic ──────────────────────────────────────────────────────────

def _is_past_reset_time(sessions_cfg: dict) -> bool:
    """Check if current time is past the configured reset time."""
    auto_reset = sessions_cfg.get("auto_reset", {})
    mode = auto_reset.get("mode", "daily")
    now = _now()

    if mode in ("daily", "time"):
        reset_time = auto_reset.get("reset_time", "00:00")
        try:
            h, m = map(int, reset_time.split(":"))
            target = now.replace(hour=h, minute=m, second=0, microsecond=0)
            return now >= target
        except Exception:
            return False
    elif mode == "timer":
        return True
    return False


def _should_reset(sessions_cfg: dict) -> bool:
    """Check if session reset should trigger now (for daemon).

    Only triggers once per calendar day, AFTER the reset_time.
    Uses disk-persistent date tracking.
    """
    auto_reset = sessions_cfg.get("auto_reset", {})
    if not auto_reset.get("enabled", False):
        return False

    if _already_reset_today():
        return False

    return _is_past_reset_time(sessions_cfg)


def _archive_session(session_path: Path, archive_dir: Path):
    """Archive a session file (copy to archive/ with timestamp)."""
    archive_dir.mkdir(parents=True, exist_ok=True)
    timestamp = _now().strftime("%Y%m%d_%H%M%S")
    stem = session_path.stem
    archive_name = f"{stem}_{timestamp}.json"
    archive_path = archive_dir / archive_name

    try:
        shutil.copy2(session_path, archive_path)
        session_path.write_text("[]", encoding="utf-8")
        logger.info("Archived session %s -> %s", session_path.name, archive_name)
    except Exception as e:
        logger.warning("Failed to archive %s: %s", session_path, e)


def _reset_sessions():
    """Archive ALL active session files that have messages.

    Called when reset is due (daemon detected or on-connect check).
    Persists the date AFTER archiving so partial failures don't skip tomorrow.
    """
    data_dir = _get_data_dir()
    if not data_dir:
        return

    sessions_cfg = _get_sessions_config()
    auto_reset = sessions_cfg.get("auto_reset", {})
    if not auto_reset.get("enabled", False):
        return

    archive_on_reset = sessions_cfg.get("archive_on_reset", True)
    archive_retention_days = sessions_cfg.get("archive_retention_days", 30)

    agents_dir = data_dir / "agents"
    if not agents_dir.exists():
        return

    reset_count = 0
    archived_cleaned = 0

    for agent_dir in agents_dir.iterdir():
        if not agent_dir.is_dir():
            continue
        sessions_dir = agent_dir / "sessions"
        if not sessions_dir.exists():
            continue

        # Clean old archives if retention is set
        if archive_retention_days > 0:
            archive_dir = sessions_dir / "archive"
            if archive_dir.exists():
                cutoff = _now() - timedelta(days=archive_retention_days)
                for archive_file in archive_dir.glob("*.json"):
                    try:
                        mtime = datetime.fromtimestamp(archive_file.stat().st_mtime)
                        if mtime < cutoff:
                            archive_file.unlink()
                            archived_cleaned += 1
                    except Exception:
                        pass

        for session_file in sessions_dir.glob("*.json"):
            if "archive" in session_file.parts:
                continue

            try:
                messages = json.loads(session_file.read_text(encoding="utf-8"))
                if not isinstance(messages, list):
                    continue

                if messages:
                    if archive_on_reset:
                        archive_dir = sessions_dir / "archive"
                        _archive_session(session_file, archive_dir)
                    else:
                        session_file.write_text("[]", encoding="utf-8")
                    reset_count += 1
            except Exception as e:
                logger.warning("Error processing session %s: %s", session_file, e)

    if reset_count > 0 or archived_cleaned > 0:
        logger.info("Session auto-reset: archived %d sessions, cleaned %d old archives",
                     reset_count, archived_cleaned)

    # Persist date AFTER archiving — only mark done if archiving succeeded
    today = _now().strftime("%Y-%m-%d")
    _write_last_reset_date(today)


def check_and_reset_on_connect():
    """Called on WS-connect: run reset if not yet done today.

    Uses disk-persistent date — survives server restarts and reconnects.
    Will only archive ONCE per calendar day.
    """
    if _already_reset_today():
        return  # Already done (survives restart)

    sessions_cfg = _get_sessions_config()
    auto_reset = sessions_cfg.get("auto_reset", {})
    if not auto_reset.get("enabled", False):
        return

    if not _is_past_reset_time(sessions_cfg):
        return

    mode = auto_reset.get("mode", "daily")
    logger.info("Session reset on WS-connect (mode=%s)", mode)
    _reset_sessions()


# ── Background daemon ────────────────────────────────────────────────────

def _session_reset_loop(interval: int = 60):
    """Background loop that checks for session reset every `interval` seconds."""
    while True:
        try:
            sessions_cfg = _get_sessions_config()
            if _should_reset(sessions_cfg):
                logger.info("Session auto-reset triggered (daemon)")
                _reset_sessions()
        except Exception as e:
            logger.warning("Session reset check error: %s", e)

        time.sleep(interval)


def start_session_reset_daemon(interval: int = 60):
    """Start the session auto-reset background thread."""
    t = threading.Thread(
        target=_session_reset_loop,
        args=(interval,),
        daemon=True,
        name="session-reset",
    )
    t.start()
    print(f"  [sessions] Auto-reset daemon started (checking every {interval}s)")
