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
    # don't override with the env var. This prevents the wizard
    # from re-appearing after "Перейти к SynPin" in dev mode.
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

    Accepts:
        data: {
            providers: [ { name, base_url, api_key, models, type }, ... ] (optional)
            skip_provider_setup: bool (optional, default false)
        }

    When providers is empty AND skip is false, registers OpenCode
    Free by default so the system is immediately usable.

    NOTE: This endpoint does NOT mark the wizard as completed.
    The frontend calls POST /api/setup/complete separately when
    the user clicks "Перейти к SynPin". This two-step design
    keeps the setup and completion semantically distinct.
    """
    config_dir = get_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)

    providers_input = data.get("providers", [])
    skip = bool(data.get("skip_provider_setup", False))

    if not providers_input and not skip:
        providers_input = [_default_opencode_free_provider()]
    elif not providers_input and skip:
        providers_input = []

    # Build providers dict
    providers_dict: dict = {}
    for prov in providers_input:
        name = prov.get("name")
        if not name:
            raise HTTPException(400, "Each provider must have a 'name' field.")
        providers_dict[name] = {
            "api_key": prov["api_key"],
            "base_url": prov.get("base_url", "http://localhost:1234/v1"),
            "models": prov.get("models", ["default"]),
            "type": prov.get("type", "openai-compatible"),
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

    # Copy templates for other configs if missing
    _copy_template("agents.yaml")
    _copy_template("departments.yaml")
    _copy_template("otdels.yaml")
    _copy_template("settings.yaml")
    _copy_template("channels.yaml")
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
OPENCODE_FREE_MODELS = [
    "gpt-5-nano",
    "claude-haiku-4-5",
    "gemini-2.5-flash",
]


def _default_opencode_free_provider() -> dict:
    """Return the spec for the default OpenCode Free provider."""
    return {
        "name": "opencode-free",
        "base_url": OPENCODE_FREE_URL,
        "api_key": "no-auth",
        "models": list(OPENCODE_FREE_MODELS),
        "type": "openai-compatible",
        "auth_method": "no-auth",
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
