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

    Returns:
        needs_setup: true if providers are empty/missing (virgin system)
        message: human-readable status
    """
    config_dir = get_config_dir()
    providers_file = config_dir / "providers.yaml"

    if not providers_file.exists():
        return {
            "needs_setup": True,
            "message": "Провайдеры не настроены — требуется первоначальная настройка.",
        }

    try:
        data = yaml.safe_load(providers_file.read_text(encoding="utf-8"))
        if not data or not data.get("providers"):
            return {
                "needs_setup": True,
                "message": "Провайдеры не настроены — требуется указать API-ключ.",
            }
    except Exception as e:
        logger.warning("Failed to load providers.yaml: %s", e)
        return {
            "needs_setup": True,
            "message": "Файл провайдеров повреждён — требуется повторная настройка.",
        }

    return {
        "needs_setup": False,
        "message": "SynPin настроен и готов к работе.",
    }


@router.post("")
def save_setup(data: dict) -> dict:
    """Save initial configuration from setup wizard.

    Accepts:
        data: {
            providers: [ { name, base_url, api_key, models, type }, ... ]
        }

    Creates providers.yaml with the given providers. Other configs
    (agents.yaml, departments.yaml, etc.) are generated from templates
    if they don't exist yet.
    """
    config_dir = get_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)

    providers = data.get("providers", [])
    if not providers:
        raise HTTPException(400, "At least one provider is required.")

    # Build providers dict
    providers_dict: dict = {}
    for prov in providers:
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
    logger.info("Setup saved providers: %s", ", ".join(providers_dict.keys()))

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
