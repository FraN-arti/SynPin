"""FastAPI application for SynPin."""

from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

app = FastAPI(
    title="SynPin",
    description="Agent-Driven Organization Platform",
    version="0.1.0",
)


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
