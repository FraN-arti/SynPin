"""FastAPI application for SynPin."""

from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from synpin import __version__
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from ..cli.console import console
import logging
import os
import yaml

logger = logging.getLogger(__name__)

# ── CORS Origins — read from settings.yaml or use dev defaults ───────
# Tauri webview origins are included so the desktop cockpit app can
# reach the API from its own window without preflight failures.
_default_origins = [
    "http://localhost:2099", "http://localhost:2100",
    "http://127.0.0.1:2099", "http://127.0.0.1:2100",
    "tauri://localhost",
    "http://tauri.localhost",
    "https://tauri.localhost",
] 

_cors_origins = _default_origins
_settings_candidates = [
    Path.home() / ".synpin" / "config" / "settings.yaml",
    Path(__file__).resolve().parent.parent / "config" / "settings.yaml",
]
for _sp in _settings_candidates:
    if _sp.exists():
        try:
            with open(_sp, encoding="utf-8") as _sf:
                _settings = yaml.safe_load(_sf) or {}
            _custom = _settings.get("server", {}).get("cors_origins")
            if _custom and isinstance(_custom, list):
                _cors_origins = _custom
                logger.info("CORS origins loaded from settings.yaml: %s", _cors_origins)
        except Exception:
            pass
        break

import asyncio
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle — replaces deprecated on_event('startup').

    Startup output is intentionally compact. Each subsystem registers itself
    with `console.print(...)` and we print a single summary block at the end.
    Verbose per-line logging is reserved for actual problems.
    """
    from ..cli.console import console as _startup_console

    started: list[str] = []  # human-readable list for the final summary

    # ── WS broadcast: capture the running loop for thread-safe broadcasts ──
    from .. import ws_broadcast
    ws_broadcast.init(asyncio.get_running_loop())
    started.append("ws broadcast")

    # ── Background tasks ──────────────────────────────────────────────────
    from .version_router import _update_check_loop
    asyncio.create_task(_update_check_loop())
    started.append("github update-checker (6h)")

    try:
        from ..kanban.service import KanbanService
        from ..kanban.auto_delete import schedule_auto_delete
        svc = KanbanService()
        task = schedule_auto_delete(svc)
        if task:
            started.append("kanban auto-delete")
    except Exception as e:
        logger.warning("[auto-delete] failed to start: %s", e)

    try:
        from ..kanban.deadline import schedule_deadline_checker
        task = schedule_deadline_checker(svc)
        if task:
            started.append("deadline checker")
    except Exception as e:
        logger.warning("[deadline] failed to start: %s", e)

    try:
        from ..connections.auto_approval import schedule_auto_approval
        task = schedule_auto_approval()
        if task:
            started.append("connections auto-approval")
    except Exception as e:
        logger.warning("[auto-approval] failed to start: %s", e)

    # ── Cron scheduler ────────────────────────────────────────────────
    try:
        # Start all background services via DaemonManager
        from ..services.daemon_manager import DaemonManager
        _daemon_manager = DaemonManager()
        app.state.daemon_manager = _daemon_manager

        # 1. Cron scheduler
        from ..cron.scheduler import _tick_loop
        _daemon_manager.register("cron-scheduler", _tick_loop, interval=60, is_async=True)

        # 2. Session auto-reset
        from ..chat.session_reset import _reset_sessions, _should_reset, _get_sessions_config
        import time as _time_module
        _last_reset_by_mode: dict = {}

        async def _session_reset_tick():
            try:
                cfg = _get_sessions_config()
                if _should_reset(cfg):
                    _reset_sessions()
                    mode = cfg.get("auto_reset", {}).get("mode", "daily")
                    _last_reset_by_mode[mode] = _time_module.time()
                    _last_reset_by_mode["daily"] = _time_module.time()
            except Exception:
                pass

        _daemon_manager.register("session-reset", _session_reset_tick, interval=60, is_async=True)

        # Start all
        _daemon_manager.start()
        started.append("daemon manager (cron + session-reset)")
    except Exception as e:
        logger.warning("[cron] Failed to start scheduler: %s", e)

    # ── Trigger engine (event-driven automation: idle_head, etc.) ──
    try:
        from ..triggers.engine import get_engine
        from ..triggers.actions.log import LogAction
        from ..triggers.actions.agent_prompt import AgentPromptAction
        trigger_eng = get_engine()
        trigger_eng.register_action(LogAction())
        trigger_eng.register_action(AgentPromptAction())
        # Start engine in a background task — it spawns its own watchers
        # and event processor; no periodic tick needed.
        asyncio.create_task(trigger_eng.start())
        started.append("trigger engine")
    except Exception as e:
        logger.warning("[triggers] Failed to start engine: %s", e)

    yield  # ← app runs here

    # ── Shutdown (if needed) ──────────────────────────────────────────────


app = FastAPI(
    title="SynPin",
    description="Agent-Driven Organization Platform",
    version=__version__,
    lifespan=lifespan,
)

# Allow Vite dev server to reach the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Chat provider setup ---
from ..chat import ProviderRegistry
from ..chat import router as chat_router

# Resolve config path. In dev mode the in-repo config wins so
# the developer is editing the same file the server is reading.
# In production we fall back to ~/.synpin/config/. The previous
# version of this list had production FIRST, which silently
# picked up stale config files left over from older installs
# and produced confusing errors (e.g. providers.yaml in the
# list-as-dict format from a previous release, when the new
# code expects dict-of-dicts). SYNPIN_DEV is read once at
# import time and used to swap the order.
from ..paths import get_config_dir
_dev_user_dir = get_config_dir()  # respects SYNPIN_DEV at import
_config_candidates = [
    _dev_user_dir / "providers.yaml",                  # dev (preferred)
    Path.home() / ".synpin" / "config" / "providers.yaml",  # production (fallback)
]

_loaded_registry: ProviderRegistry | None = None
_loaded_config_path: Path | None = None
for candidate in _config_candidates:
    if candidate.exists():
        _loaded_registry = ProviderRegistry.from_config(candidate)
        _loaded_config_path = candidate
        console.print(f"  [chat] Loaded providers from: {candidate}")
        break

if _loaded_registry is None:
    _loaded_registry = ProviderRegistry()
    _loaded_config_path = None
    console.print("  [chat] No providers.yaml found — chat disabled")

# Inject registry into the router module
chat_router.registry = _loaded_registry
app.include_router(chat_router.router)

# Otdel chat router
from ..chat import otdel_chat_router
otdel_chat_router.registry = _loaded_registry
app.include_router(otdel_chat_router.router)

# WebSocket router
from ..chat import ws_router
app.include_router(ws_router.router)

# Providers config management API
from .providers_router import router as providers_router
app.include_router(providers_router)

# Agents config management API
from .agents_router import router as agents_router
app.include_router(agents_router)

# External agents detection and management API
from .external_agents_router import router as external_agents_router
app.include_router(external_agents_router)

# Connections — inter-department relationships
from .connections_router import router as connections_router
app.include_router(connections_router)

# Cron — scheduled tasks for agents
from .cron_router import router as cron_router
app.include_router(cron_router)

# Tools — global enable/disable for LLM-callable tools
from .tools_router import router as tools_router
app.include_router(tools_router)

# Skills — global enable/disable for skills library
from .skills_router import router as skills_router
app.include_router(skills_router)

# Hermes Agent chat proxy
from .hermes_chat_router import router as hermes_chat_router
app.include_router(hermes_chat_router)

# Memory management API
from .memory_router import router as memory_router
app.include_router(memory_router)

# Config management API (compaction, sessions, context_window)
from .config_router import router as config_router
app.include_router(config_router)

# Stats and usage API
from .stats_router import router as stats_router
app.include_router(stats_router)

# TweakCN themes API
from .themes_router import router as themes_router
app.include_router(themes_router)

# Kanban task board API
from .kanban_router import router as kanban_router
app.include_router(kanban_router)

# Kanban config API (columns, labels, widget)
from .kanban_config_router import router as kanban_config_router
app.include_router(kanban_config_router)

# Projects API
from ..projects.router import router as projects_router
app.include_router(projects_router)

# Version metadata endpoint
from .version_router import router as version_router
app.include_router(version_router)

# Setup wizard API (virgin detection, first-run config)
from .setup_router import router as setup_router
app.include_router(setup_router)

# Triggers (plugin-style automation engine)
from .triggers_router import router as triggers_router
app.include_router(triggers_router)

# Widget layout endpoint
from .widgets_router import router as widgets_router
app.include_router(widgets_router)

# Events (in-app toast stack, settings, read state)
from ..events.api import router as events_router
app.include_router(events_router)

# Head protocol settings (retry-limit knob shared by all otdels)
from .protocol_router import router as protocol_router
app.include_router(protocol_router)

@app.get("/api/health")
def health():
    return {"status": "ok", "version": __version__}


@app.post("/api/admin/reload")
def reload_config():
    """Manual config reload — re-reads providers.yaml."""
    if _loaded_registry and _loaded_config_path:
        _loaded_registry.reload()
        return {"status": "ok", "message": f"Reloaded from {_loaded_config_path.name}"}
    return {"status": "error", "message": "No config path set"}


# --- Config Watcher: auto-reload on file change ---
# Polls every 5s. When any watched YAML changes on disk, the
# relevant in-memory state is reloaded and a WebSocket event is
# pushed to all connected clients. This makes the production
# synpin-start experience equivalent to HMR: edit a YAML in your
# editor, the running server picks it up, the open browser tab
# sees the new state without a reload.
from ..config.watcher import ConfigWatcher
from ..paths import (
    get_config_dir,
    get_otdels_dir,
)

_config_watcher = ConfigWatcher(interval=5)


def _broadcast_config_event(event_type: str, payload: dict) -> None:
    """Push a config:updated event to all connected WS clients."""
    from ..ws_broadcast import broadcast
    broadcast({"type": event_type, **payload})


def _on_providers_changed(path: Path, mtime: float) -> None:
    """Reload providers when providers.yaml changes on disk."""
    if _loaded_registry:
        _loaded_registry.reload()
        # Use logger.debug instead of console.print so per-reload events
        # stay quiet in normal startup. Flip the synpin logger to DEBUG
        # (`synpin start --verbose`) to see them.
        logger.debug("[config] providers.yaml reloaded (mtime=%.0f)", mtime)
        _broadcast_config_event("providers:updated", {"mtime": mtime})


def _on_yaml_changed(label: str) -> "callable":
    """Return a callback that logs + broadcasts when a YAML changes."""
    def _cb(path: Path, mtime: float) -> None:
        logger.debug("[config] %s reloaded from disk (mtime=%.0f)", label, mtime)
        _broadcast_config_event(f"{label}:updated", {"mtime": mtime})
    return _cb


# Wire the watcher to every user-editable config file. We catch
# OSError per file (a file may be absent on a fresh install, and
# watcher.watch already logs that) so one missing file doesn't
# break the whole watcher startup.
def _safe_watch(path: Path, label: str) -> None:
    if path and path.exists():
        _config_watcher.watch(path, _on_yaml_changed(label))


# providers.yaml — already done above.
if _loaded_config_path:
    _config_watcher.watch(_loaded_config_path, _on_providers_changed)

# Main config dir YAMLs (agents, departments, otdels, settings, etc.)
for yaml_name in ("agents.yaml", "departments.yaml", "otdels.yaml",
                  "settings.yaml", "channels.yaml", "memory.yaml",
                  "tools.yaml", "roles.yaml", "security.yaml"):
    _safe_watch(get_config_dir() / yaml_name, yaml_name.replace(".yaml", ""))

# Per-department and per-otdel data dirs — every file inside is a
# live entity that the UI reads on every request. We add watchers
# for any existing subdir's department.yaml / otdel.yaml.
def _watch_per_entity_dirs(parent: Path, suffix: str) -> None:
    if not parent.exists():
        return
    for sub in parent.iterdir():
        if sub.is_dir():
            _safe_watch(sub / f"{suffix}.yaml", f"{suffix} {sub.name}")

_watch_per_entity_dirs(get_otdels_dir(), "otdel")

# Kanban config (columns.yaml, labels.yaml, settings.yaml,
# widget.yaml) — small, but the user edits them via the UI and
# also sometimes by hand, so watcher makes sense.
kanban_cfg = Path(__file__).resolve().parent.parent / "kanban" / "config"
for yaml_name in ("columns.yaml", "labels.yaml", "settings.yaml", "widget.yaml"):
    _safe_watch(kanban_cfg / yaml_name, f"kanban-{yaml_name.replace('.yaml', '')}")

_config_watcher.start()
watched = sum(1 for p, _ in _config_watcher._watches)
# Report watched files once via the lifespan summary rather than logging
# here on the import path. We stash the count on app.state so lifespan
# can include it in its compact summary line.
app.state._config_watcher_count = watched


# Serve React SPA (built static files) — ONLY in production
# In dev mode: use Vite dev server on port 2099
# In production: ~/.synpin/web/dist/ (installed via pip install synpin)
# Fallback: web/dist relative to source (for editable installs)
_STATIC_DIR_CANDIDATES = [
    Path.home() / ".synpin" / "web" / "dist",  # production (pip install)
    Path(__file__).resolve().parent.parent.parent.parent / "web" / "dist",  # dev (editable)
]
_STATIC_DIR = next((p for p in _STATIC_DIR_CANDIDATES if p.exists()), _STATIC_DIR_CANDIDATES[0])

# Only mount static files if NOT in dev mode (SYNPIN_DEV env var)
if _STATIC_DIR.exists() and not os.environ.get("SYNPIN_DEV"):
    app.mount("/assets", StaticFiles(directory=str(_STATIC_DIR / "assets")), name="assets")

    @app.get("/{full_path:path}")
    def serve_spa(full_path: str):
        file_path = _STATIC_DIR / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(_STATIC_DIR / "index.html"))
