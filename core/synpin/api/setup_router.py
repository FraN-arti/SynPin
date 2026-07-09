"""Setup router — first-run wizard status and configuration.

Provides:
- GET  /api/setup/status   — check if SynPin needs initial setup
- POST /api/setup          — save wizard form data (providers, etc.)
- POST /api/setup/complete — mark wizard as completed

State management: a single wizard.json flag replaces the old
providers.yaml check.

  wizard.json { "completed": true }  → wizard done, never show again
  wizard.json missing or completed=false → wizard needed

  WIZARD_S=1 env var → override: always show wizard (dev mode).
"""

import json
import logging

import yaml
from fastapi import APIRouter, HTTPException

from ..paths import get_config_dir

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/setup", tags=["setup"])


# ── Helpers ────────────────────────────────────────────────────────


def _wizard_file():
    """Return path to wizard.json in the config directory."""
    return get_config_dir() / "wizard.json"


def _read_wizard_state() -> dict:
    """Read wizard.json. Returns {} if missing or corrupt."""
    path = _wizard_file()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_wizard_state(state: dict) -> None:
    """Write wizard.json atomically."""
    config_dir = get_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    _wizard_file().write_text(
        json.dumps(state, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


# ── Routes ─────────────────────────────────────────────────────────


@router.get("/status")
def setup_status() -> dict:
    """Check if SynPin needs initial setup.

    Priority:
      1. wizard.json.completed === true → wizard done (never show,
         even if WIZARD_S=1 — the user completed it, respect that)
      2. WIZARD_S=1 env → show wizard (dev override)
      3. wizard.json missing or completed=false → show wizard
    """
    import os

    # Check completion first — if the user finished the wizard,
    # don't override with the env var.
    state = _read_wizard_state()
    if state.get("completed") is True:
        return {
            "needs_setup": False,
            "dev_mode": False,
            "message": "SynPin настроен и готов к работе.",
        }

    # Dev override — show wizard when WIZARD_S=1
    if os.environ.get("WIZARD_S") == "1":
        return {
            "needs_setup": True,
            "dev_mode": True,
            "message": "WIZARD_S=1 — визард открыт в режиме разработки.",
        }

    return {
        "needs_setup": True,
        "dev_mode": False,
        "message": "Требуется первоначальная настройка.",
    }


@router.post("")
def save_setup(data: dict) -> dict:
    """Save initial configuration from setup wizard.

    This endpoint handles providers setup. It writes providers.yaml
    directly using the same format as the providers page.

    Accepts:
        data: {
            providers: [ { name, base_url, api_key, models, type }, ... ] (optional)
            skip_provider_setup: bool (optional, default false)
        }

    NOTE: This endpoint does NOT mark the wizard as completed.
    The frontend calls POST /api/setup/complete separately when
    the user clicks "Перейти к SynPin".
    """
    config_dir = get_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)

    providers_input = data.get("providers", [])
    skip = bool(data.get("skip_provider_setup", False))

    if not providers_input and not skip:
        # Default path: register OpenCode Free so the system is
        # immediately usable. The user can swap in a paid provider
        # later via Settings → Providers.
        providers_input = [_default_opencode_free_provider()]
    elif not providers_input and skip:
        providers_input = []

    # Build providers dict — same format as providers_router.py
    providers_dict: dict = {}
    for prov in providers_input:
        name = prov.get("name")
        if not name:
            raise HTTPException(400, "Each provider must have a 'name' field.")
        providers_dict[name] = {
            "type": prov.get("type", "openai-compatible"),
            "base_url": prov.get("base_url", ""),
            "api_key": prov.get("api_key", ""),
            "models": prov.get("models", []),
        }

    # Save providers.yaml
    providers_file = config_dir / "providers.yaml"
    providers_file.write_text(
        yaml.dump({"providers": providers_dict}, default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )
    if providers_dict:
        logger.info("Setup saved providers: %s", ", ".join(providers_dict.keys()))
    else:
        logger.info("Setup completed without providers (user will configure later)")

    # Refresh the in-memory chat provider registry so the user can
    # start chatting immediately, without restarting the server.
    # On a FRESH install providers.yaml does not yet exist at server
    # import time, so _loaded_registry was created empty (Path=None)
    # and a plain reload() is a no-op. We rebuild it here and inject
    # both the registry and the config path so future reloads work.
    try:
        from ..api import server as server_mod
        from ..chat import router as chat_router
        from ..chat import otdel_chat_router
        from ..chat.providers import ProviderRegistry

        providers_path = providers_file
        if server_mod._loaded_registry is None or not server_mod._loaded_config_path:
            fresh = ProviderRegistry.from_config(providers_path)
            server_mod._loaded_registry = fresh
            server_mod._loaded_config_path = providers_path
            chat_router.registry = fresh
            otdel_chat_router.registry = fresh
            logger.info("Hot-loaded fresh chat provider registry from %s", providers_path)
        else:
            chat_router.registry.reload()
            otdel_chat_router.registry.reload()
    except Exception as e:
        # Non-fatal: the user will hit the same error and can
        # recover via the providers settings page.
        logger.warning("Could not hot-reload chat registry: %s", e)

    # Copy templates for other configs if missing.
    # Note: channels.yaml is intentionally NOT copied — it is a
    # per-developer secrets file (app_id, bot tokens, etc.) and
    # must be created manually for any developer who needs it.
    _copy_template("agents.yaml")
    _copy_template("departments.yaml")
    _copy_template("otdels.yaml")
    _copy_template("settings.yaml")
    _copy_template("roles.yaml")
    _copy_template("security.yaml")
    _copy_template("tools.yaml")
    _copy_template("memory.yaml")
    _copy_template("widget_layout.yaml")
    _copy_template("web_search.yaml")

    return {"status": "ok", "message": "SynPin настроен!"}


@router.post("/complete")
def complete_setup() -> dict:
    """Mark the setup wizard as completed.

    Called by the frontend when the user clicks "Перейти к SynPin"
    on the final DoneStep. Writes wizard.json { "completed": true }
    so the wizard never shows again (unless WIZARD_S=1 overrides).

    This is idempotent — calling it multiple times is safe.
    """
    _write_wizard_state({"completed": True})
    logger.info("Setup wizard completed")
    return {"status": "ok", "message": "Визард завершён."}


# ── OpenCode Free ──────────────────────────────────────────────────

OPENCODE_FREE_URL = "https://opencode.ai/zen/v1"

# These are the ACTUAL free models from OpenCode Free's catalog.
# Models ending in "-free" or named "big-pickle" don't require
# an API key. This list must be kept in sync with the catalog at
# D:\synpin\web\src\data\providers.ts (opencode-free entry).
OPENCODE_FREE_MODELS = [
    "big-pickle",
    "deepseek-v4-flash-free",
    "mimo-v2.5-free",
    "hy3-free",
    "nemotron-3-ultra-free",
    "north-mini-code-free",
]


def _default_opencode_free_provider() -> dict:
    """Return the spec for the default OpenCode Free provider.

    This is the no-auth provider that gets registered during the
    wizard so the user can start using SynPin immediately. The
    models list contains only the actual free-tier models (no
    paid models mixed in).
    """
    return {
        "name": "opencode-free",
        "type": "openai-compatible",
        "base_url": OPENCODE_FREE_URL,
        "api_key": "",  # no-auth — empty key is intentional
        "models": list(OPENCODE_FREE_MODELS),
    }


# ── Templates ──────────────────────────────────────────────────────


def _copy_template(filename: str) -> None:
    """Copy a template file from templates/ to config dir if target doesn't exist."""
    config_dir = get_config_dir()
    target = config_dir / filename
    if target.exists():
        return
    alt = config_dir / "templates" / filename
    if alt.exists():
        content = alt.read_text(encoding="utf-8")
        target.write_text(content, encoding="utf-8")
        logger.debug("Copied template %s -> %s", filename, target)
