"""External agents — detection and management of external agent integrations."""
import os
import httpx
from pathlib import Path
from typing import Any
from ..agents import manager

# External agent registry — each entry defines a detectable external agent
EXTERNAL_AGENT_REGISTRY: list[dict[str, Any]] = [
    {
        "slug": "hermes-agent",
        "name": "Hermes Agent",
        "type": "hermes",
        "description": "AI агент с полным доступом к инструментам: терминал, файлы, веб, память, скиллы",
        "detect_url": "http://127.0.0.1:8642/health",
        "chat_url": "http://127.0.0.1:8642/v1/chat/completions",
        "models_url": "http://127.0.0.1:8642/v1/models",
        "default_role": "worker",
        "default_department": "dev",
        "icon_letter": "H",
        "color": "#f97316",
        "api_key_env": "HERMES_API_SERVER_KEY",  # env var name for the API key
        "api_key_default": "change-me-local-dev",  # fallback if env not set
    },
]


async def detect_external_agents() -> list[dict[str, Any]]:
    """Detect available external agents by checking their endpoints."""
    results = []

    for agent_def in EXTERNAL_AGENT_REGISTRY:
        agent_info = {
            "slug": agent_def["slug"],
            "name": agent_def["name"],
            "type": agent_def["type"],
            "description": agent_def["description"],
            "available": False,
            "models": [],
            "default_role": agent_def["default_role"],
            "default_department": agent_def["default_department"],
            "icon_letter": agent_def["icon_letter"],
            "color": agent_def["color"],
        }

        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                # Health check
                health_resp = await client.get(agent_def["detect_url"])
                if health_resp.status_code == 200:
                    agent_info["available"] = True

                    # Get available models
                    try:
                        api_key = os.environ.get(
                            agent_def.get("api_key_env", ""),
                            agent_def.get("api_key_default", ""),
                        )
                        models_resp = await client.get(
                            agent_def["models_url"],
                            headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
                        )
                        if models_resp.status_code == 200:
                            models_data = models_resp.json()
                            agent_info["models"] = [
                                m.get("id", "") for m in models_data.get("data", [])
                            ]
                    except Exception:
                        pass

        except Exception:
            agent_info["available"] = False

        results.append(agent_info)

    return results


def get_external_agents_config() -> dict[str, Any]:
    """Load external agents configuration."""
    config_path = manager._get_config_dir() / "external_agents.yaml"
    return manager._load_yaml(config_path)


def save_external_agents_config(config: dict[str, Any]) -> None:
    """Save external agents configuration."""
    config_path = manager._get_config_dir() / "external_agents.yaml"
    manager._save_yaml(config_path, config)


def register_external_agent(agent_info: dict[str, Any]) -> dict[str, Any]:
    """Register an external agent in the system."""
    config = get_external_agents_config()
    agents = config.get("agents", {})

    slug = agent_info["slug"]

    if slug not in agents:
        # New agent — generate agentid
        from ..agents.manager import _generate_agentid
        agents[slug] = {
            "agentid": _generate_agentid(),
            "name": agent_info["name"],
            "type": agent_info["type"],
            "description": agent_info["description"],
            "enabled": False,
            "role": agent_info.get("default_role", "worker"),
            "department": agent_info.get("default_department", "dev"),
            "chat_url": agent_info.get("chat_url", ""),
            "models": agent_info.get("models", []),
            "icon_letter": agent_info.get("icon_letter", "?"),
            "color": agent_info.get("color", "#6b7280"),
        }
    else:
        # Existing — update available info
        agents[slug]["available"] = agent_info.get("available", False)
        agents[slug]["models"] = agent_info.get("models", [])
        agents[slug]["name"] = agent_info.get("name", agents[slug].get("name", ""))
        agents[slug]["description"] = agent_info.get("description", agents[slug].get("description", ""))

    config["agents"] = agents
    save_external_agents_config(config)
    return agents[slug]


def load_external_agents() -> list[dict[str, Any]]:
    """Load all registered external agents."""
    config = get_external_agents_config()
    agents = config.get("agents", {})

    # Resolve role/department names
    roles_data = manager.load_roles()
    roles_list = roles_data.get("roles", [])
    depts_data = manager.load_departments()
    depts_list = depts_data.get("departments", [])

    result = []
    for slug, cfg in agents.items():
        role_id = cfg.get("role", "worker")
        dept_id = cfg.get("department", "dev")
        role_name = next((r["name"] for r in roles_list if r.get("rolesid") == role_id or r.get("id") == role_id), role_id)
        dept_name = next((d["name"] for d in depts_list if d.get("departmentsid") == dept_id or d.get("id") == dept_id), dept_id)

        result.append({
            "slug": slug,
            "agentid": cfg.get("agentid", ""),
            "name": cfg.get("name", slug),
            "type": cfg.get("type", "unknown"),
            "description": cfg.get("description", ""),
            "enabled": cfg.get("enabled", False),
            "is_primary": cfg.get("is_primary", False),
            "role": role_id,
            "role_name": role_name,
            "department": dept_id,
            "department_name": dept_name,
            "available": cfg.get("available", False),
            "models": cfg.get("models", []),
            "chat_url": cfg.get("chat_url", ""),
            "icon_letter": cfg.get("icon_letter", "?"),
            "color": cfg.get("color", "#6b7280"),
            "is_external": True,
        })

    return result


def update_external_agent(slug: str, updates: dict[str, Any]) -> dict[str, Any] | None:
    """Update an external agent's settings."""
    config = get_external_agents_config()
    agents = config.get("agents", {})

    if slug not in agents:
        return None

    # Only allow certain fields to be updated
    allowed_fields = {"name", "role", "department", "enabled", "is_primary"}
    for key, value in updates.items():
        if key in allowed_fields:
            # If setting is_primary=True, unset all others first
            if key == "is_primary" and value:
                for other_slug, other_cfg in agents.items():
                    if other_slug != slug:
                        other_cfg["is_primary"] = False
            agents[slug][key] = value

    config["agents"] = agents
    save_external_agents_config(config)

    # Broadcast agent list change if name/role/department changed (sidebar refresh)
    if any(k in updates for k in ("name", "role", "department")):
        from ..ws_broadcast import broadcast
        broadcast({"type": "agent:list_changed"})

    # Sync is_primary with settings.yaml and broadcast
    if "is_primary" in updates:
        settings_path = manager._get_config_dir() / "settings.yaml"
        settings_data = manager._load_yaml(settings_path)
        if updates["is_primary"]:
            settings_data["primary_agent_slug"] = slug
        elif settings_data.get("primary_agent_slug") == slug:
            settings_data["primary_agent_slug"] = ""
        manager._save_yaml(settings_path, settings_data)

        # Broadcast change via WebSocket
        from ..ws_broadcast import broadcast
        broadcast({"type": "agent:list_changed"})

    return load_external_agent(slug)


def load_external_agent(slug: str) -> dict[str, Any] | None:
    """Load a single external agent."""
    agents = load_external_agents()
    for agent in agents:
        if agent["slug"] == slug:
            return agent
    return None
