"""FastAPI application for SynPin."""

from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import logging
import os
import yaml

logger = logging.getLogger(__name__)

# ── CORS Origins — read from settings.yaml or use dev defaults ───────
_default_origins = [
    "http://localhost:2099", "http://localhost:2100",
    "http://127.0.0.1:2099", "http://127.0.0.1:2100",
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

app = FastAPI(
    title="SynPin",
    description="Agent-Driven Organization Platform",
    version="0.2.3",
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

# Resolve config path: prod ~/.synpin/config/ first, then dev core/config/
_config_candidates = [
    Path.home() / ".synpin" / "config" / "providers.yaml",   # production
    Path(__file__).resolve().parent.parent / "config" / "providers.yaml",  # dev
]

_loaded_registry: ProviderRegistry | None = None
_loaded_config_path: Path | None = None
for candidate in _config_candidates:
    if candidate.exists():
        _loaded_registry = ProviderRegistry.from_config(candidate)
        _loaded_config_path = candidate
        print(f"  [chat] Loaded providers from: {candidate}")
        break

if _loaded_registry is None:
    _loaded_registry = ProviderRegistry()
    _loaded_config_path = None
    print("  [chat] No providers.yaml found — chat disabled")

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


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "0.2.3"}


@app.post("/api/admin/reload")
def reload_config():
    """Manual config reload — re-reads providers.yaml."""
    if _loaded_registry and _loaded_config_path:
        _loaded_registry.reload()
        return {"status": "ok", "message": f"Reloaded from {_loaded_config_path.name}"}
    return {"status": "error", "message": "No config path set"}


# --- Config Watcher: auto-reload on file change ---
from ..config.watcher import ConfigWatcher

_config_watcher = ConfigWatcher(interval=5)

def _on_providers_changed(path: Path, mtime: float):
    """Callback when providers.yaml changes on disk."""
    if _loaded_registry:
        _loaded_registry.reload()
        print(f"  [config] ⚡ providers.yaml reloaded (mtime={mtime:.0f})")

if _loaded_config_path:
    _config_watcher.watch(_loaded_config_path, _on_providers_changed)

_config_watcher.start()
print(f"  [config] ConfigWatcher active (polling every 5s)")

# --- Session auto-reset daemon ---
from ..chat.session_reset import start_session_reset_daemon
start_session_reset_daemon(interval=60)


# Serve React SPA (built static files) — ONLY in production
# In dev mode: use Vite dev server on port 2099
# In production: ~/.synpin/web/dist/
_STATIC_DIR = Path(__file__).resolve().parent.parent.parent.parent / "web" / "dist"

# Only mount static files if NOT in dev mode (SYNPIN_DEV env var)
if _STATIC_DIR.exists() and not os.environ.get("SYNPIN_DEV"):
    app.mount("/assets", StaticFiles(directory=str(_STATIC_DIR / "assets")), name="assets")

    @app.get("/{full_path:path}")
    def serve_spa(full_path: str):
        file_path = _STATIC_DIR / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(_STATIC_DIR / "index.html"))
