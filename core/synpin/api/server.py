"""FastAPI application for SynPin."""

from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import os

app = FastAPI(
    title="SynPin",
    description="Agent-Driven Organization Platform",
    version="0.1.0",
)

# Allow Vite dev server to reach the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:2099", "http://localhost:2100", "http://127.0.0.1:2099", "http://127.0.0.1:2100"],
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
for candidate in _config_candidates:
    if candidate.exists():
        _loaded_registry = ProviderRegistry.from_config(candidate)
        print(f"  [chat] Loaded providers from: {candidate}")
        break

if _loaded_registry is None:
    _loaded_registry = ProviderRegistry()
    print("  [chat] No providers.yaml found — chat disabled")

# Inject registry into the router module
chat_router.registry = _loaded_registry
app.include_router(chat_router.router)

# Providers config management API
from .providers_router import router as providers_router
app.include_router(providers_router)


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "0.1.0"}


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
