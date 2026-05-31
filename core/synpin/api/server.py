"""FastAPI application for SynPin."""

from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

app = FastAPI(
    title="SynPin",
    description="Agent-Driven Organization Platform",
    version="0.1.0",
)


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "0.1.0"}


# Serve React SPA (built static files)
# In production: ~/.synpin/web/dist/
# In dev: D:\synpin\web\dist\ (after vite build)
_CORE_DIR = Path(__file__).resolve().parents[2]
STATIC_DIR = _CORE_DIR.parent / "web" / "dist"

if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="assets")

    @app.get("/{full_path:path}")
    def serve_spa(full_path: str):
        file_path = STATIC_DIR / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(STATIC_DIR / "index.html"))
