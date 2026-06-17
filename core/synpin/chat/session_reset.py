"""Session auto-reset background task.

Reads settings from memory.yaml:
  sessions:
    auto_reset:
      enabled: true
      mode: daily | timer | time
      reset_time: "00:00"    # for mode=time
      interval_hours: 24     # for mode=timer
    archive_on_reset: true
    max_history: 100

When triggered, archives current session files and creates fresh ones.
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

# Last reset tracking (in-memory, resets on server restart)
_last_reset: dict[str, float] = {}


from ..paths import (
    get_data_dir_or_none as _get_data_dir,
    get_config_dir_or_none as _get_config_dir,
)


def _load_yaml(path: Path) -> dict:
    """Safe YAML loader."""
    try:
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def _get_sessions_config() -> dict:
    """Read sessions config from memory.yaml."""
    config_dir = _get_config_dir()
    if not config_dir:
        return {}
    mem_cfg = _load_yaml(config_dir / "memory.yaml")
    return mem_cfg.get("sessions", {})


def _should_reset(sessions_cfg: dict) -> bool:
    """Check if session reset should trigger now."""
    auto_reset = sessions_cfg.get("auto_reset", {})
    if not auto_reset.get("enabled", False):
        return False

    mode = auto_reset.get("mode", "daily")
    now = datetime.now()

    if mode == "daily":
        reset_time = auto_reset.get("reset_time", "00:00")
        try:
            h, m = map(int, reset_time.split(":"))
            target = now.replace(hour=h, minute=m, second=0, microsecond=0)
            if now >= target:
                # Check if we already reset today
                last = _last_reset.get("daily", 0)
                today_start = target.timestamp()
                if last >= today_start:
                    return False
                return True
        except Exception:
            pass

    elif mode == "timer":
        interval = auto_reset.get("interval_hours", 24) * 3600
        last = _last_reset.get("timer", 0)
        if time.time() - last >= interval:
            return True

    elif mode == "time":
        reset_time = auto_reset.get("reset_time", "00:00")
        try:
            h, m = map(int, reset_time.split(":"))
            target = now.replace(hour=h, minute=m, second=0, microsecond=0)
            if now >= target:
                last = _last_reset.get("time", 0)
                if last >= target.timestamp():
                    return False
                return True
        except Exception:
            pass

    return False


def _archive_session(session_path: Path, archive_dir: Path):
    """Archive a session file."""
    archive_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = session_path.stem
    archive_name = f"{stem}_{timestamp}.json"
    archive_path = archive_dir / archive_name

    try:
        shutil.copy2(session_path, archive_path)
        # Clear the original session
        session_path.write_text("[]", encoding="utf-8")
        logger.info("Archived session %s → %s", session_path.name, archive_name)
    except Exception as e:
        logger.warning("Failed to archive %s: %s", session_path, e)


def _reset_sessions():
    """Archive all active session files."""
    data_dir = _get_data_dir()
    if not data_dir:
        return

    sessions_cfg = _get_sessions_config()
    archive_on_reset = sessions_cfg.get("archive_on_reset", True)
    max_history = sessions_cfg.get("max_history", 100)

    # Find all session files: data/agents/{slug}/sessions/{channel}.json
    agents_dir = data_dir / "agents"
    if not agents_dir.exists():
        return

    reset_count = 0
    for agent_dir in agents_dir.iterdir():
        if not agent_dir.is_dir():
            continue
        sessions_dir = agent_dir / "sessions"
        if not sessions_dir.exists():
            continue

        for session_file in sessions_dir.glob("*.json"):
            try:
                messages = json.loads(session_file.read_text(encoding="utf-8"))
                if not isinstance(messages, list):
                    continue

                # Check if session needs reset
                needs_reset = False

                # Reset if exceeds max_history
                if max_history and len(messages) > max_history:
                    needs_reset = True

                # Reset if session is older than 24 hours
                if messages:
                    last_ts = messages[-1].get("timestamp", "")
                    if last_ts:
                        try:
                            last_dt = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
                            age = datetime.now().astimezone() - last_dt
                            if age > timedelta(hours=24):
                                needs_reset = True
                        except Exception:
                            pass

                if needs_reset:
                    if archive_on_reset:
                        archive_dir = session_file.parent / "archive"
                        _archive_session(session_file, archive_dir)
                    else:
                        session_file.write_text("[]", encoding="utf-8")
                    reset_count += 1

            except Exception as e:
                logger.warning("Error processing session %s: %s", session_file, e)

    if reset_count > 0:
        logger.info("Session auto-reset: archived %d sessions", reset_count)


def _session_reset_loop(interval: int = 60):
    """Background loop that checks for session reset every `interval` seconds."""
    while True:
        try:
            sessions_cfg = _get_sessions_config()
            if _should_reset(sessions_cfg):
                logger.info("Session auto-reset triggered")
                _reset_sessions()
                # Update last reset time
                mode = sessions_cfg.get("auto_reset", {}).get("mode", "daily")
                _last_reset[mode] = time.time()
                _last_reset["daily"] = time.time()
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
