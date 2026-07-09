"""Setup router — first-run wizard status and configuration.

Provides:
- GET /api/setup/status — check if SynPin needs initial setup (virgin detection)
- POST /api/setup — save wizard form data (agents, providers, etc.)

Virgin detection: returns { needs_setup: true } if providers.yaml is
empty (providers: {}) or doesn't exist. The frontend uses this to
auto-navigate to the wizard on first run.
"""

import logging

import yaml
from fastapi import APIRouter, HTTPException

from ..paths import get_config_dir

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/setup", tags=["setup"])


@router.get("/status")
def setup_status() -> dict:
    """Check if SynPin needs initial setup.

    Two triggers:
      1. WIZARD_S=1 env var — forces wizard visible (dev mode).
      2. providers.yaml missing/empty — virgin detection (production).

    Returns:
        needs_setup: true if wizard should be shown
        message: human-readable status
        dev_mode: true if triggered by WIZARD_S (frontend can show a "dev" badge)
    """
    import os

    # Dev override — always show wizard when WIZARD_S=1
    if os.environ.get("WIZARD_S") == "1":
        return {
            "needs_setup": True,
            "dev_mode": True,
            "message": "WIZARD_S=1 — визард открыт в режиме разработки.",
        }

    config_dir = get_config_dir()
    providers_file = config_dir / "providers.yaml"

    if not providers_file.exists():
        return {
            "needs_setup": True,
            "dev_mode": False,
            "message": "Провайдеры не настроены — требуется первоначальная настройка.",
        }

    try:
        data = yaml.safe_load(providers_file.read_text(encoding="utf-8"))
        if not data or not data.get("providers"):
            return {
                "needs_setup": True,
                "dev_mode": False,
                "message": "Провайдеры не настроены — требуется указать API-ключ.",
            }
    except Exception as e:
        logger.warning("Failed to load providers.yaml: %s", e)
        return {
            "needs_setup": True,
            "dev_mode": False,
            "message": "Файл провайдеров повреждён — требуется повторная настройка.",
        }

    return {
        "needs_setup": False,
        "dev_mode": False,
        "message": "SynPin настроен и готов к работе.",
    }


@router.post("")
def save_setup(data: dict) -> dict:
    """Save initial configuration from setup wizard.

    Accepts:
        data: {
            providers: [ { name, base_url, api_key, models, type }, ... ] (optional)
            skip_provider_setup: bool (optional, default false) — if true
                and providers is empty, no provider is configured at all.
                Useful for the "I'll set up later" path.
        }

    When providers is empty AND skip_provider_setup is false, the
    default OpenCode Free provider is registered so the user can
    start using SynPin with free models immediately without having
    to paste an API key on first run. They can add a real provider
    later in Settings → Providers.

    Creates providers.yaml with the given providers (or default).
    Other configs (agents.yaml, departments.yaml, etc.) are
    generated from templates if they don't exist yet.
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
        # User explicitly chose to skip. No provider is created.
        # The system will report needs_setup=true again on next
        # load (since providers.yaml will be empty or missing),
        # but we DO need to write a marker so the wizard doesn't
        # loop forever. The simplest thing: write an empty
        # providers.yaml and rely on the user adding one later.
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


# OpenCode Free — a no-auth public endpoint that proxies free-tier
# models from various providers. Used as the default provider for
# new SynPin installations so users can hit the ground running
# without pasting an API key. They can swap in a paid provider
# later via Settings → Providers.
OPENCODE_FREE_URL = "https://opencode.ai/zen/v1"
OPENCODE_FREE_MODELS = [
    "gpt-5-nano",
    "claude-haiku-4-5",
    "gemini-2.5-flash",
]


def _default_opencode_free_provider() -> dict:
    """Return the spec for the default OpenCode Free provider.

    Used when the wizard's first run is triggered with no providers
    in the payload. No api_key needed — OpenCode Free's authMethod
    is 'no-auth' so the request goes through unauthenticated.
    """
    return {
        "name": "opencode-free",
        "base_url": OPENCODE_FREE_URL,
        "api_key": "no-auth",
        "models": list(OPENCODE_FREE_MODELS),
        "type": "openai-compatible",
        "auth_method": "no-auth",
    }


def _copy_template(filename: str) -> None:
    """Copy a template file from templates/ to config dir if target doesn't exist."""
    config_dir = get_config_dir()
    target = config_dir / filename
    if target.exists():
        return

    # Template lives in the templates/ subdirectory
    alt = config_dir / "templates" / filename
    if alt.exists():
        content = alt.read_text(encoding="utf-8")
        target.write_text(content, encoding="utf-8")
        logger.debug("Copied template %s -> %s", filename, target)
