"""Agent manager — loads agents from agents.yaml + per-agent agent.yaml,
merges with global memory.yaml defaults, auto-creates agent directories."""
import yaml
import os
import random
import string
from pathlib import Path
from typing import Any

_AGENTS_DIR = None
_CONFIG_DIR = None


def _generate_agentid() -> str:
    """Generate unique 8-character alphanumeric agentid."""
    chars = string.ascii_lowercase + string.digits
    return ''.join(random.choices(chars, k=8))


def _generate_long_id(length: int = 12) -> str:
    """Generate unique alphanumeric ID (default 12 chars)."""
    chars = string.ascii_lowercase + string.digits
    return ''.join(random.choices(chars, k=length))


def _get_config_dir() -> Path:
    global _CONFIG_DIR
    if _CONFIG_DIR is not None:
        return _CONFIG_DIR
    prod = Path.home() / ".synpin" / "config"
    dev = Path(__file__).resolve().parent.parent / "config"
    _CONFIG_DIR = prod if prod.exists() else dev
    return _CONFIG_DIR


def _get_agents_dir() -> Path:
    global _AGENTS_DIR
    if _AGENTS_DIR is not None:
        return _AGENTS_DIR
    prod = Path.home() / ".synpin" / "agents"
    dev = Path(__file__).resolve().parent.parent / "agents"
    _AGENTS_DIR = prod if prod.exists() else dev
    return _AGENTS_DIR


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _save_yaml(path: Path, data: dict[str, Any]) -> None:
    """Save YAML — caller must hold lock if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    os.replace(str(tmp_path), str(path))


# ─── Default agent.yaml template ──────────────────────────────────

_DEFAULT_AGENT_YAML = {
    "name": "",
    "description": "",
    "personality": {
        "tone": "professional",
        "style": "analytical",
        "traits": ["thinks before answering"],
    },
    "system_prompt": "",
    "behavior": {
        "max_iterations": 10,
        "temperature": 0.7,
        "max_tokens": 4096,
    },
    "memory": {},
}

_DEFAULT_NAMES: dict[str, str] = {
    "architect": "Архитектор",
    "developer": "Разработчик",
    "qa-engineer": "QA Инженер",
}


def _global_memory_defaults() -> dict[str, Any]:
    """Extract memory defaults from memory.yaml."""
    mem = _load_yaml(_get_config_dir() / "memory.yaml")
    agent_mem = mem.get("agent_memory", {})
    session = agent_mem.get("session", {})
    lifecycle = mem.get("lifecycle", {})
    cleanup = lifecycle.get("cleanup", {})
    retention = lifecycle.get("retention", {})

    return {
        "max_sessions": session.get("max_sessions_per_agent", 50),
        "session_summary": session.get("session_summary", True),
        "summary_max_length": session.get("summary_max_length", 500),
        "archive_sessions_after_days": cleanup.get("archive_sessions_after_days", 90),
        "delete_archived_after_days": cleanup.get("delete_archived_after_days", 365),
        "compact_memory_threshold": cleanup.get("compact_memory_threshold", 50),
        "lesson_retention_days": retention.get("lessons", "keep"),
        "session_retention_days": retention.get("session_summaries", 90),
    }


def ensure_agent_dir(slug: str) -> Path:
    """Ensure agent directory exists with agent.yaml + memory structure.
    Returns the agent directory path."""
    agents_dir = _get_agents_dir()
    agent_dir = agents_dir / slug

    if agent_dir.exists():
        # Migration: add agentid if missing
        agent_yaml_path = agent_dir / "agent.yaml"
        agent_data = _load_yaml(agent_yaml_path)
        if not agent_data.get("agentid"):
            agent_data["agentid"] = _generate_agentid()
            _save_yaml(agent_yaml_path, agent_data)
        return agent_dir

    agent_dir.mkdir(parents=True, exist_ok=True)

    # Create agent.yaml with defaults
    agent_yaml_path = agent_dir / "agent.yaml"
    defaults = dict(_DEFAULT_AGENT_YAML)
    defaults["name"] = _DEFAULT_NAMES.get(slug, slug.replace("-", " ").title())
    defaults["agentid"] = _generate_agentid()
    _save_yaml(agent_yaml_path, defaults)

    # Create memory directories
    (agent_dir / "memory" / "sessions").mkdir(parents=True, exist_ok=True)
    (agent_dir / "memory" / "facts").mkdir(parents=True, exist_ok=True)

    return agent_dir


def load_agents() -> dict[str, Any]:
    """Load all agents from agents.yaml, ensure directories, merge configs.
    Returns list of resolved agent dicts."""
    data = _load_yaml(_get_config_dir() / "agents.yaml")
    agents_cfg = data.get("agents", {})
    global_memory = _global_memory_defaults()

    result = []
    for slug, cfg in agents_cfg.items():
        # Ensure directory exists (auto-create on first load)
        ensure_agent_dir(slug)

        # Load per-agent agent.yaml
        agent_yaml_path = _get_agents_dir() / slug / "agent.yaml"
        agent_data = _load_yaml(agent_yaml_path)

        # Merge memory: global defaults → agent overrides
        agent_memory = dict(global_memory)
        if "memory" in agent_data and agent_data["memory"]:
            agent_memory.update(agent_data["memory"])

        # Build resolved agent
        personality = agent_data.get("personality", {})
        behavior = agent_data.get("behavior", {})

        # Parse provider from model if not explicit (e.g. "9router/general-agent" → provider="9router", model="general-agent")
        raw_model = cfg.get("model", "default")
        provider = cfg.get("provider", None)
        model = raw_model
        if not provider and "/" in raw_model:
            provider, model = raw_model.split("/", 1)

        # Resolve role/department IDs to human-readable names
        role_id = agent_data.get("role", cfg.get("role", "worker"))
        dept_id = agent_data.get("department", cfg.get("department", "dev"))
        roles_list = load_roles()
        depts_list = load_departments()
        role_name = next((r["name"] for r in roles_list if r.get("rolesid") == role_id or r.get("id") == role_id), role_id)
        dept_name = next((d["name"] for d in depts_list if d.get("departmentsid") == dept_id or d.get("id") == dept_id), dept_id)

        resolved = {
            "slug": slug,
            "agentid": agent_data.get("agentid", ""),
            "enabled": cfg.get("enabled", True),
            "role": role_id,
            "role_name": role_name,
            "department": dept_id,
            "department_name": dept_name,
            "model": model,
            "provider": provider,
            "skills": cfg.get("skills", []),
            # From agent.yaml
            "name": agent_data.get("name", _DEFAULT_NAMES.get(slug, slug.replace("-", " ").title())),
            "description": agent_data.get("description", ""),
            "tone": personality.get("tone", "professional"),
            "style": personality.get("style", "analytical"),
            "traits": personality.get("traits", []),
            "system_prompt": agent_data.get("system_prompt", ""),
            # Behavior
            "max_iterations": behavior.get("max_iterations", 10),
            "temperature": behavior.get("temperature", 0.7),
            "max_tokens": behavior.get("max_tokens", 4096),
            # Memory (resolved)
            "memory": agent_memory,
        }
        result.append(resolved)

    return {"agents": result}


def get_agent(slug: str) -> dict[str, Any] | None:
    """Get a single resolved agent by slug."""
    data = load_agents()
    for agent in data.get("agents", []):
        if agent["slug"] == slug:
            return agent
    return None


def create_agent(name: str, role: str = "", department: str = "",
                 model: str = "", description: str = "", system_prompt: str = "",
                 tone: str = "", style: str = "", traits: list[str] | None = None,
                 temperature: float = 0.7, max_tokens: int | None = None) -> dict[str, Any]:
    """Create a new agent from scratch. Returns the created agent."""
    # Generate agentid first — it becomes the slug (directory name + key)
    agentid = _generate_agentid()
    slug = agentid

    # Ensure unique slug (extremely unlikely but safe)
    config_path = _get_config_dir() / "agents.yaml"
    data = _load_yaml(config_path)
    agents = data.get("agents", {})
    while slug in agents:
        agentid = _generate_agentid()
        slug = agentid

    # Create agent directory + agent.yaml
    agent_dir = ensure_agent_dir(slug)
    agent_yaml = agent_dir / "agent.yaml"
    agent_data: dict[str, Any] = {
        "agentid": agentid,
        "name": name,
    }
    if role:
        agent_data["role"] = role
    if department:
        agent_data["department"] = department
    if description:
        agent_data["description"] = description
    if system_prompt:
        agent_data["system_prompt"] = system_prompt
    if tone or style or traits:
        agent_data["personality"] = {}
        if tone:
            agent_data["personality"]["tone"] = tone
        if style:
            agent_data["personality"]["style"] = style
        if traits:
            agent_data["personality"]["traits"] = traits
    if temperature != 0.7 or max_tokens is not None:
        agent_data["behavior"] = {}
        if temperature != 0.7:
            agent_data["behavior"]["temperature"] = temperature
        if max_tokens is not None:
            agent_data["behavior"]["max_tokens"] = max_tokens
    _save_yaml(agent_yaml, agent_data)

    # Add to agents.yaml (operational config)
    if "agents" not in data:
        data["agents"] = {}
    data["agents"][slug] = {
        "model": model,
        "enabled": True,
    }
    _save_yaml(config_path, data)

    return get_agent(slug) or {}


def delete_agent(slug: str) -> bool:
    """Remove an agent: delete from agents.yaml and remove agent directory."""
    config_path = _get_config_dir() / "agents.yaml"
    data = _load_yaml(config_path)
    agents = data.get("agents", {})
    if slug not in agents:
        return False
    del agents[slug]
    data["agents"] = agents
    _save_yaml(config_path, data)

    # Remove agent directory (agent.yaml, memory, avatar, etc.)
    import shutil
    agent_dir = _get_agents_dir() / slug
    if agent_dir.exists():
        shutil.rmtree(agent_dir)

    return True


def save_agent(slug: str, updates: dict[str, Any]) -> dict[str, Any]:
    """Save agent updates. Operational → agents.yaml, personalization + role/dept → agent.yaml."""
    # Operational fields → agents.yaml (role & department NOT here — they go to agent.yaml)
    operational_keys = {"enabled", "model", "provider", "skills"}
    operational = {k: v for k, v in updates.items() if k in operational_keys}

    # Personalization + role/dept → agent.yaml
    personalization_keys = {"name", "description", "role", "department", "tone", "style", "traits",
                           "system_prompt", "max_iterations", "temperature", "max_tokens", "memory"}
    personalization = {k: v for k, v in updates.items() if k in personalization_keys}

    # Update agents.yaml
    if operational:
        config_path = _get_config_dir() / "agents.yaml"
        data = _load_yaml(config_path)
        if slug in data.get("agents", {}):
            data["agents"][slug].update(operational)
            _save_yaml(config_path, data)

    # Update agent.yaml
    if personalization:
        agent_dir = ensure_agent_dir(slug)
        agent_yaml_path = agent_dir / "agent.yaml"
        agent_data = _load_yaml(agent_yaml_path)

        # Split personalization into sub-sections
        if "name" in personalization:
            agent_data["name"] = personalization.pop("name")
        if "description" in personalization:
            agent_data["description"] = personalization.pop("description")
        if "system_prompt" in personalization:
            agent_data["system_prompt"] = personalization.pop("system_prompt")
        if "role" in personalization:
            agent_data["role"] = personalization.pop("role")
        if "department" in personalization:
            agent_data["department"] = personalization.pop("department")

        personality_fields = {"tone", "style", "traits"}
        personality_data = {k: personalization.pop(k) for k in personality_fields if k in personalization}
        if personality_data:
            if "personality" not in agent_data:
                agent_data["personality"] = {}
            agent_data["personality"].update(personality_data)

        behavior_fields = {"max_iterations", "temperature", "max_tokens"}
        behavior_data = {k: personalization.pop(k) for k in behavior_fields if k in personalization}
        if behavior_data:
            if "behavior" not in agent_data:
                agent_data["behavior"] = {}
            agent_data["behavior"].update(behavior_data)

        if "memory" in personalization:
            agent_data["memory"] = personalization.pop("memory")

        _save_yaml(agent_yaml_path, agent_data)

    return get_agent(slug) or {}


# ─── Roles & Departments ─────────────────────────────────────────

def load_roles() -> list[dict[str, Any]]:
    """Load roles from config/roles.yaml with migration."""
    config_path = _get_config_dir() / "roles.yaml"
    data = _load_yaml(config_path)
    roles = data.get("roles", [])

    # Migration: rename 'id' → 'rolesid', generate new 12-char ID
    migrated = False
    for role in roles:
        if "rolesid" not in role:
            if "id" in role:
                role.pop("id")  # Remove old id
            role["rolesid"] = _generate_long_id()
            migrated = True

    if migrated:
        _save_yaml(config_path, {"roles": roles})

    return roles


def save_roles(roles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Save roles list to config/roles.yaml."""
    config_path = _get_config_dir() / "roles.yaml"

    # Ensure each role has rolesid
    for role in roles:
        if not role.get("rolesid"):
            role["rolesid"] = _generate_long_id()

    _save_yaml(config_path, {"roles": roles})
    return roles


def load_departments() -> list[dict[str, Any]]:
    """Load departments from config/departments.yaml with migration."""
    config_path = _get_config_dir() / "departments.yaml"
    data = _load_yaml(config_path)
    departments = data.get("departments", [])

    # Migration: rename 'id' → 'departmentsid', generate new 12-char ID
    migrated = False
    for dept in departments:
        if "departmentsid" not in dept:
            if "id" in dept:
                dept.pop("id")  # Remove old id
            dept["departmentsid"] = _generate_long_id()
            migrated = True

    if migrated:
        _save_yaml(config_path, {"departments": departments})

    return departments


def save_departments(departments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Save departments list to config/departments.yaml."""
    config_path = _get_config_dir() / "departments.yaml"

    # Ensure each department has departmentsid
    for dept in departments:
        if not dept.get("departmentsid"):
            dept["departmentsid"] = _generate_long_id()

    _save_yaml(config_path, {"departments": departments})
    return departments
