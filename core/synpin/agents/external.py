"""External agents — detection and management of external agent integrations."""
import os
import httpx
from typing import Any
from ..agents import manager
from ..paths import get_config_dir

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
        # Two-stage detection. Both must succeed for `available=True` to
        # propagate to the Sidebar. Stage 1 = binary present on disk.
        # Stage 2 = gateway HTTP responding 200. Stage 1 is fast (sync
        # filesystem + --version probe); stage 2 is async with a 3s timeout.
        "binary_paths": [
            # `Scripts/hermes` is the bash-style link under MSYS; Windows
            # actually executes `hermes.exe` in that directory. We list
            # both forms so detection works whether the worker process is
            # bash-launched or Windows-launched.
            "C:/Users/Shakaho/AppData/Local/hermes/hermes-agent/venv/Scripts/hermes",
            "C:/Users/Shakaho/AppData/Local/hermes/hermes-agent/venv/Scripts/hermes.exe",
            "C:/Users/Shakaho/AppData/Roaming/hermes/venv/Scripts/hermes",
            "C:/Users/Shakaho/AppData/Roaming/hermes/venv/Scripts/hermes.exe",
            "/usr/local/bin/hermes",
            "/opt/hermes/venv/bin/hermes",
        ],
        "default_role": "worker",
        "default_department": "dev",
        "icon_letter": "H",
        "color": "#f97316",
        "api_key_env": "HERMES_API_SERVER_KEY",  # env var name for the API key
        "api_key_default": "change-me-local-dev",  # fallback if env not set
    },
]


async def _check_binary_candidate(candidate: str) -> dict[str, Any] | None:
    """Async stage 1 — try one binary path. Returns install info or None.

    Runs the `--version` probe via asyncio.to_thread so it doesn't block
    the event loop (uvicorn-watcher kills workers that freeze the loop).
    """
    if not candidate:
        return None
    import asyncio
    import os
    import shutil

    if shutil.which(candidate):
        runnable = candidate
    elif os.path.isfile(candidate):
        runnable = candidate
    else:
        return None

    def _probe() -> str | None:
        import subprocess
        try:
            proc = subprocess.run(
                [runnable, "--version"],
                capture_output=True, text=True, timeout=3,
            )
            text = (proc.stdout or proc.stderr or "").strip()
            return text.split("\n", 1)[0] if text else None
        except Exception:
            return None

    version = await asyncio.to_thread(_probe)
    if version is None and not os.path.isfile(runnable):
        # probe failed AND the binary doesn't exist on disk → not installed
        return None
    if version is None:
        # Binary exists but probe failed (broken venv, etc.) — try next.
        return None
    return {"installed": True, "path": runnable, "version": version}


async def detect_external_agents() -> list[dict[str, Any]]:
    """Detect external agents in two stages: binary on disk → gateway reachable.

    Returns a list of agent_info dicts with two stage flags surfaced:
      - installed       : bool  — stage 1
      - available       : bool  — stage 2 (default False; requires stage 1)
      - install_path    : str | None
      - install_version : str | None
    The Sidebar / agent:list_changed broadcast path uses `available`.
    """
    results = []

    for agent_def in EXTERNAL_AGENT_REGISTRY:
        agent_info: dict[str, Any] = {
            "slug": agent_def["slug"],
            "name": agent_def["name"],
            "type": agent_def["type"],
            "description": agent_def["description"],
            "available": False,
            "installed": False,
            "install_path": None,
            "install_version": None,
            "models": [],
            "default_role": agent_def["default_role"],
            "default_department": agent_def["default_department"],
            "icon_letter": agent_def["icon_letter"],
            "color": agent_def["color"],
        }

        # Stage 1: binary present and runnable (async — non-blocking probe).
        for candidate in agent_def.get("binary_paths", []):
            found = await _check_binary_candidate(candidate)
            if found:
                agent_info["installed"] = True
                agent_info["install_path"] = found["path"]
                agent_info["install_version"] = found["version"]
                break

        # Stage 2: gateway reachable — only if stage 1 succeeded.
        # If the binary isn't installed, the gateway certainly isn't either,
        # so don't waste a 3s timeout on a dead URL.
        if not agent_info["installed"]:
            results.append(agent_info)
            continue

        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                health_resp = await client.get(agent_def["detect_url"])
                if health_resp.status_code == 200:
                    agent_info["available"] = True

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
    config_path = get_config_dir() / "external_agents.yaml"
    return manager._load_yaml(config_path)


def save_external_agents_config(config: dict[str, Any]) -> None:
    """Save external agents configuration."""
    config_path = get_config_dir() / "external_agents.yaml"
    manager._save_yaml(config_path, config)


def diff_external_state(prev: list[dict[str, Any]], next_: list[dict[str, Any]]) -> bool:
    """Return True if any agent's `available` or `installed` flag flipped.

    Used by ws_router to decide whether to broadcast an external_agents
    event without sending on every reconnect.
    """
    by_slug_prev = {a.get("slug"): a for a in prev}
    for a in next_:
        slug = a.get("slug")
        prev_a = by_slug_prev.get(slug, {})
        if prev_a.get("available") != a.get("available"):
            return True
        if prev_a.get("installed") != a.get("installed"):
            return True
    return False


def register_external_agent(agent_info: dict[str, Any]) -> dict[str, Any]:
    """Register an external agent in the system.

    Updates `available`, `installed`, `models`, `install_path`, and
    `install_version` on each run so the WS-driven UI can react to
    gateway up/down without an F5.
    """
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
        # Existing — update the live state flags driven by detect_external_agents.
        # installed/install_path/install_version flip here too, so a
        # freshly-installed binary without a running gateway is reflected
        # in /api/external-agents and the front-end can render the right hint.
        agents[slug]["available"] = agent_info.get("available", False)
        agents[slug]["installed"] = agent_info.get("installed", agents[slug].get("installed", False))
        agents[slug]["models"] = agent_info.get("models", [])
        agents[slug]["name"] = agent_info.get("name", agents[slug].get("name", ""))
        agents[slug]["description"] = agent_info.get("description", agents[slug].get("description", ""))
        if agent_info.get("install_path"):
            agents[slug]["install_path"] = agent_info["install_path"]
        if agent_info.get("install_version"):
            agents[slug]["install_version"] = agent_info["install_version"]

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
            # Two-stage detection flags — installed is stage 1 (binary on disk),
            # available is stage 2 (gateway /health 200). Only both-green → chat.
            "installed": cfg.get("installed", False),
            "install_path": cfg.get("install_path"),
            "install_version": cfg.get("install_version"),
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
        settings_path = get_config_dir() / "settings.yaml"
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
