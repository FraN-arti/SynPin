"""ConfigWatcher — automatic hot-reload of config files.

Polls file mtimes every N seconds. When a file changes, calls registered
callback. Zero dependencies beyond stdlib.

Usage:
    watcher = ConfigWatcher(interval=5)
    watcher.watch("providers.yaml", on_providers_changed)
    watcher.start()  # Background daemon thread
    ...
    watcher.stop()
"""
import logging
import threading
import time
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)


class ConfigWatcher:
    """Background thread that polls file mtimes and fires callbacks on change."""

    def __init__(self, interval: float = 5.0):
        self._interval = interval
        self._watches: list[tuple[Path, Callable]] = []
        self._mtimes: dict[Path, float] = {}
        self._thread: threading.Thread | None = None
        self._running = False

    def watch(self, path: str | Path, callback: Callable) -> None:
        """Register a file to watch. callback is called with (path, new_mtime) when changed."""
        path = Path(path).resolve()
        if not path.exists():
            logger.warning(f"[config-watcher] File does not exist: {path}")
            return

        self._watches.append((path, callback))
        self._mtimes[path] = path.stat().st_mtime
        # Per-file "Watching X" lines go to DEBUG — they're useful when
        # debugging watcher behavior, but for normal startup we want a
        # single summary, not N lines.
        logger.debug(f"[config-watcher] Watching: {path}")

    def start(self) -> None:
        """Start the background polling thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True, name="config-watcher")
        self._thread.start()
        # The startup summary line ("ConfigWatcher: N files, polling every 5s")
        # is emitted from lifespan. Keep this at DEBUG so we don't duplicate.
        logger.debug(f"[config-watcher] Started (interval={self._interval}s)")

    def stop(self) -> None:
        """Stop the polling thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None

    def _poll_loop(self) -> None:
        """Background loop — check mtimes and fire callbacks."""
        while self._running:
            time.sleep(self._interval)
            for path, callback in self._watches:
                try:
                    if not path.exists():
                        continue
                    current_mtime = path.stat().st_mtime
                    if current_mtime != self._mtimes.get(path):
                        old = self._mtimes.get(path, 0)
                        self._mtimes[path] = current_mtime
                        logger.info(f"[config-watcher] Changed: {path.name} (mtime {old} → {current_mtime})")
                        try:
                            callback(path, current_mtime)
                        except Exception as e:
                            logger.error(f"[config-watcher] Callback error for {path.name}: {e}")
                except Exception as e:
                    logger.error(f"[config-watcher] Poll error for {path}: {e}")
