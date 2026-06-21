"""Agent manager — loads agents from agents.yaml + per-agent agent.yaml,
merges with global memory.yaml defaults, auto-creates agent directories."""
import yaml
import os
import random
import string
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

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


def _is_hash_id(value: str) -> bool:
    """Check if a value looks like a generated hash ID (12-char alphanumeric)."""
    return len(value) == 12 and all(c in string.ascii_lowercase + string.digits for c in value)


from ..paths import (
    get_config_dir as _get_config_dir,
    get_agents_dir as _get_agents_dir,
    get_otdels_dir as _get_otdels_dir,
)


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
    compaction = mem.get("compaction", {})
    sessions_cfg = mem.get("sessions", {})
    ctx = mem.get("context_window", {})

    return {
        # Legacy memory settings
        "max_sessions": session.get("max_sessions_per_agent", 50),
        "session_summary": session.get("session_summary", True),
        "summary_max_length": session.get("summary_max_length", 500),
        "archive_sessions_after_days": cleanup.get("archive_sessions_after_days", 90),
        "delete_archived_after_days": cleanup.get("delete_archived_after_days", 365),
        "compact_memory_threshold": cleanup.get("compact_memory_threshold", 50),
        "lesson_retention_days": retention.get("lessons", "keep"),
        "session_retention_days": retention.get("session_summaries", 90),
        # Compaction settings
        "compaction_enabled": compaction.get("enabled", True),
        "compaction_trigger_percent": compaction.get("trigger_percent", 80),
        "compaction_keep_recent": compaction.get("keep_recent", 10),
        "compaction_strategy": compaction.get("strategy", "truncate"),
        # Session settings
        "session_auto_reset_enabled": sessions_cfg.get("auto_reset", {}).get("enabled", True),
        "session_auto_reset_mode": sessions_cfg.get("auto_reset", {}).get("mode", "daily"),
        "session_auto_reset_time": sessions_cfg.get("auto_reset", {}).get("reset_time", "00:00"),
        "session_auto_reset_interval": sessions_cfg.get("auto_reset", {}).get("interval_hours", 24),
        "session_archive_on_reset": sessions_cfg.get("archive_on_reset", True),
        "session_max_history": sessions_cfg.get("max_history", 100),
        # Global context window
        "context_window_default": ctx.get("default", 128000),
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

        # Context window: per-agent override or global default
        ctx_override = agent_data.get("context_window") or agent_memory.get("context_window")
        context_window = ctx_override or global_memory.get("context_window_default", 128000)

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
        roles_data = load_roles()
        roles_list = roles_data.get("roles", [])
        depts_data = load_departments()
        depts_list = depts_data.get("departments", [])
        role_name = next((r["name"] for r in roles_list if r.get("rolesid") == role_id or r.get("id") == role_id), role_id)
        dept_name = next((d["name"] for d in depts_list if d.get("departmentsid") == dept_id or d.get("id") == dept_id), dept_id)

        resolved = {
            "slug": slug,
            "agentid": agent_data.get("agentid", ""),
            "enabled": cfg.get("enabled", True),
            "is_primary": cfg.get("is_primary", False),
            "role": role_id,
            "role_name": role_name,
            "department": dept_id,
            "department_name": dept_name,
            "model": model,
            "provider": provider,
            "skills": cfg.get("skills", []),
            "tools": agent_data.get("tools", []),
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
            "context_window": context_window,
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
    # Use default role from config if not provided
    if not role:
        roles_data = load_roles()
        default_role = roles_data.get("is_default")
        role = default_role or "worker"

    # Use default department from config if not provided
    if not department:
        depts_data = load_departments()
        default_dept = depts_data.get("is_default")
        department = default_dept or "dev"

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
    """Remove an agent: delete from agents.yaml, remove directory, and clean up memberships."""
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

    # Remove chat history (data/agents/<slug>/sessions/)
    from ..paths import get_data_dir
    data_dir = get_data_dir()
    if data_dir:
        history_dir = data_dir / "agents" / slug
        if history_dir.exists():
            shutil.rmtree(history_dir)

    # Clean up agent from all departments and otdels
    _remove_agent_from_groups(slug)

    return True


def _remove_agent_from_groups(slug: str) -> None:
    """Remove an agent slug from all department and otdel memberships."""
    changed = False

    # Clean departments.yaml
    departments_path = _get_config_dir() / "departments.yaml"
    if departments_path.exists():
        dept_data = _load_yaml(departments_path)
        departments = dept_data.get("departments", [])
        for dept in departments:
            members = dept.get("members", [])
            if isinstance(members, list) and slug in members:
                dept["members"] = [m for m in members if m != slug]
                changed = True
        if changed:
            dept_data["departments"] = departments
            _save_yaml(departments_path, dept_data)

    # Clean otdels.yaml
    otdels_path = _get_config_dir() / "otdels.yaml"
    if otdels_path.exists():
        otdel_data = _load_yaml(otdels_path)
        otdels = otdel_data.get("otdels", [])
        for otdel in otdels:
            # Remove from workers array
            workers = otdel.get("workers", [])
            if isinstance(workers, list) and slug in workers:
                otdel["workers"] = [w for w in workers if w != slug]
                changed = True
            # If this agent was the head, remove head reference
            if otdel.get("head") == slug:
                otdel["head"] = ""
                changed = True
            # Recalculate agent_count
            head = otdel.get("head")
            workers = otdel.get("workers", [])
            otdel["agent_count"] = (1 if head else 0) + len(workers)
            changed = True
        if changed:
            otdel_data["otdels"] = otdels
            _save_yaml(otdels_path, otdel_data)
            # Also update otdel.yaml inside each otdel directory
            for otdel in otdels:
                otdel_id = otdel.get("otdelid")
                if not otdel_id:
                    continue
                otdel_dir = _get_otdels_dir() / otdel_id
                if otdel_dir.exists():
                    _save_yaml(otdel_dir / "otdel.yaml", otdel)


def cleanup_orphaned_agent_memberships() -> dict[str, Any]:
    """Remove non-existent agents from all department/otdel memberships."""
    existing_agents = set(_load_yaml(_get_config_dir() / "agents.yaml").get("agents", {}).keys())
    # Also include agents from individual directories
    agents_dir = _get_agents_dir()
    if agents_dir.exists():
        for agent_dir in agents_dir.iterdir():
            if agent_dir.is_dir() and (agent_dir / "agent.yaml").exists():
                existing_agents.add(agent_dir.name)
    cleaned_otdels = []
    cleaned_departments = []

    # Clean otdels from config + individual directories
    otdels_path = _get_config_dir() / "otdels.yaml"
    if otdels_path.exists():
        otdel_data = _load_yaml(otdels_path)
        otdels = otdel_data.get("otdels", [])
        for otdel in otdels:
            otdel_id = otdel.get("otdelid")
            changed = False
            # Clean head
            if otdel.get("head") and otdel["head"] not in existing_agents:
                otdel["head"] = ""
                changed = True
            # Clean workers
            workers = [w for w in otdel.get("workers", []) if w in existing_agents]
            if len(workers) != len(otdel.get("workers", [])):
                otdel["workers"] = workers
                changed = True
            # Recalculate agent_count
            new_count = (1 if otdel.get("head") else 0) + len(otdel.get("workers", []))
            if otdel.get("agent_count") != new_count:
                otdel["agent_count"] = new_count
                changed = True
            if changed and otdel_id:
                cleaned_otdels.append(otdel_id)
        if cleaned_otdels:
            otdel_data["otdels"] = otdels
            _save_yaml(otdels_path, otdel_data)
            for otdel in otdels:
                otdel_id = otdel.get("otdelid")
                if not otdel_id:
                    continue
                otdel_dir = _get_otdels_dir() / otdel_id
                if otdel_dir.exists():
                    _save_yaml(otdel_dir / "otdel.yaml", otdel)

    # Also clean individual otdel directories (fallback for directory-based otdels)
    otdels_dir = _get_otdels_dir()
    if otdels_dir.exists():
        for otdel_dir in otdels_dir.iterdir():
            if not otdel_dir.is_dir():
                continue
            otdel_file = otdel_dir / "otdel.yaml"
            if not otdel_file.exists():
                continue
            otdel = _load_yaml(otdel_file)
            otdel_id = otdel.get("otdelid")
            changed = False
            # Clean head
            if otdel.get("head") and otdel["head"] not in existing_agents:
                otdel["head"] = ""
                changed = True
            # Clean workers
            workers = [w for w in otdel.get("workers", []) if w in existing_agents]
            if len(workers) != len(otdel.get("workers", [])):
                otdel["workers"] = workers
                changed = True
            # Recalculate agent_count
            new_count = (1 if otdel.get("head") else 0) + len(otdel.get("workers", []))
            if otdel.get("agent_count") != new_count:
                otdel["agent_count"] = new_count
                changed = True
            if changed and otdel_id:
                _save_yaml(otdel_file, otdel)
                cleaned_otdels.append(otdel_id)

    # Clean departments from config + individual directories
    departments_path = _get_config_dir() / "departments.yaml"
    if departments_path.exists():
        dept_data = _load_yaml(departments_path)
        departments = dept_data.get("departments", [])
        for dept in departments:
            dept_id = dept.get("departmentsid")
            members = dept.get("members", [])
            if isinstance(members, list):
                new_members = [m for m in members if m in existing_agents]
                if len(new_members) != len(members):
                    dept["members"] = new_members
                    if dept_id:
                        cleaned_departments.append(dept_id)
        if cleaned_departments:
            dept_data["departments"] = departments
            _save_yaml(departments_path, dept_data)

    return {"otdels": cleaned_otdels, "departments": cleaned_departments}


def save_agent(slug: str, updates: dict[str, Any]) -> dict[str, Any]:
    """Save agent updates. Operational → agents.yaml, personalization + role/dept → agent.yaml.

    The union of operational_keys and personalization_keys is the set of
    fields AgentUpdate accepts. Any other key in `updates` is logged
    as a warning and written through to the YAML anyway — better to
    have a noisy warning than to silently drop a field. The front end
    can only send fields defined in the Pydantic schema (extra=forbid
    on BaseRequest), so unknown keys here mean either a programmatic
    caller (test/seed) or a future field added to the schema without
    updating this allow-list.
    """
    # Operational fields → agents.yaml (role & department NOT here — they go to agent.yaml)
    operational_keys = {"enabled", "model", "provider", "skills", "is_primary"}
    operational = {k: v for k, v in updates.items() if k in operational_keys}

    # Personalization + role/dept → agent.yaml
    personalization_keys = {"name", "description", "role", "department", "tone", "style", "traits",
                           "system_prompt", "max_iterations", "temperature", "max_tokens", "memory",
                           "tools", "context_window"}
    personalization = {k: v for k, v in updates.items() if k in personalization_keys}

    # Loud-not-silent: anything not in the allow-list. Pydantic forbids extras
    # at the API boundary, so anything reaching this branch is either a
    # future schema field (good — update the allow-list) or a programmatic
    # caller. In neither case should we silently drop.
    known = operational_keys | personalization_keys
    unknown = {k: v for k, v in updates.items() if k not in known}
    if unknown:
        logger.warning(
            "[agent %s] save_agent got fields outside the allow-list: %s. "
            "These will be written to the YAML. If this is a new schema field, "
            "add it to operational_keys or personalization_keys in save_agent.",
            slug, sorted(unknown.keys()),
        )
        # Send unknown fields to agent.yaml — they're likely something
        # the schema accepts but we haven't enumerated. Better to persist
        # than to lose, and the warning makes the divergence visible.
        personalization = {**personalization, **unknown}

    # Update agents.yaml
    if operational:
        config_path = _get_config_dir() / "agents.yaml"
        data = _load_yaml(config_path)
        if slug in data.get("agents", {}):
            # If setting is_primary=True, unset all others first
            if operational.get("is_primary"):
                for other_slug, other_cfg in data.get("agents", {}).items():
                    if other_slug != slug:
                        other_cfg["is_primary"] = False
            data["agents"][slug].update(operational)
            _save_yaml(config_path, data)
            
            # Sync is_primary with settings.yaml and broadcast
            if "is_primary" in operational:
                # Update primary_agent_slug in settings.yaml
                settings_path = _get_config_dir() / "settings.yaml"
                settings_data = _load_yaml(settings_path)
                if operational["is_primary"]:
                    settings_data["primary_agent_slug"] = slug
                elif settings_data.get("primary_agent_slug") == slug:
                    settings_data["primary_agent_slug"] = ""
                _save_yaml(settings_path, settings_data)
                
                # Broadcast change via WebSocket
                try:
                    import asyncio
                    from ..chat.ws_manager import ws_manager
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        loop.create_task(ws_manager.broadcast({
                            "type": "agent:primary_changed",
                            "slug": slug if operational["is_primary"] else "",
                        }))
                except Exception:
                    pass

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

def load_roles() -> dict[str, Any]:
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
        elif not _is_hash_id(role["rolesid"]):
            # Migration: replace non-hash rolesid with generated hash
            old_id = role["rolesid"]
            role["rolesid"] = _generate_long_id()
            migrated = True

    if migrated:
        _save_yaml(config_path, {"roles": roles})

    return {"roles": roles, "is_default": data.get("is_default")}


def save_roles(roles: list[dict[str, Any]], is_default: str = None) -> list[dict[str, Any]]:
    """Save roles list to config/roles.yaml."""
    config_path = _get_config_dir() / "roles.yaml"

    # Preserve existing is_default if not provided
    if is_default is None:
        data = _load_yaml(config_path)
        is_default = data.get("is_default")

    # Ensure each role has rolesid
    for role in roles:
        if not role.get("rolesid"):
            role["rolesid"] = _generate_long_id()

    save_data = {"roles": roles}
    if is_default is not None:
        save_data["is_default"] = is_default
    _save_yaml(config_path, save_data)
    return roles


# ─── Departments (full CRUD with directories) ────────────────────


def load_departments() -> dict[str, Any]:
    """Load departments from config/departments.yaml."""
    config_path = _get_config_dir() / "departments.yaml"
    data = _load_yaml(config_path)
    return {"departments": data.get("departments", []), "is_default": data.get("is_default")}


def save_departments(departments: list[dict[str, Any]], is_default: str = None) -> list[dict[str, Any]]:
    """Save departments list to config/departments.yaml."""
    config_path = _get_config_dir() / "departments.yaml"
    # Preserve existing is_default if not provided
    if is_default is None:
        data = _load_yaml(config_path)
        is_default = data.get("is_default")
    for dept in departments:
        if not dept.get("departmentsid"):
            dept["departmentsid"] = _generate_long_id()
    save_data = {"departments": departments}
    if is_default is not None:
        save_data["is_default"] = is_default
    _save_yaml(config_path, save_data)
    return departments


def _count_agents_in_department(dept_id: str) -> int:
    """Count how many agents belong to a department."""
    agents_data = _load_yaml(_get_config_dir() / "agents.yaml")
    agents_cfg = agents_data.get("agents", {})
    count = 0
    for slug, cfg in agents_cfg.items():
        agent_yaml_path = _get_agents_dir() / slug / "agent.yaml"
        agent_data = _load_yaml(agent_yaml_path)
        dept = agent_data.get("department", cfg.get("department", ""))
        if dept == dept_id:
            count += 1
    return count


def get_departments_with_agents() -> list[dict[str, Any]]:
    """Load departments with agent counts resolved."""
    departments = load_departments().get("departments", [])
    for dept in departments:
        dept_id = dept.get("departmentsid", "")
        dept["agent_count"] = _count_agents_in_department(dept_id)
    return departments


def get_department(dept_id: str) -> dict[str, Any] | None:
    """Get a single department by ID."""
    departments = load_departments().get("departments", [])
    for dept in departments:
        if dept.get("departmentsid") == dept_id:
            dept["agent_count"] = _count_agents_in_department(dept_id)
            return dept
    return None


def create_department(name: str, description: str = "", color: str = "#f97316",
                      mentor_role: str = "", escalation: str = "") -> dict[str, Any]:
    """Create a new department: generates ID, saves to config."""
    dept_id = _generate_long_id()

    dept_data = {
        "departmentsid": dept_id,
        "name": name,
        "description": description,
        "color": color,
        "mentor_role": mentor_role,
        "escalation": escalation,
    }

    # Add to departments.yaml config
    config_path = _get_config_dir() / "departments.yaml"
    data = _load_yaml(config_path)
    departments = data.get("departments", [])
    departments.append(dept_data)
    data["departments"] = departments
    _save_yaml(config_path, data)

    dept_data["agent_count"] = 0
    return dept_data


def update_department(dept_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
    """Update a department's fields. Returns updated department or None if not found."""
    config_path = _get_config_dir() / "departments.yaml"
    data = _load_yaml(config_path)
    departments = data.get("departments", [])

    found = False
    for dept in departments:
        if dept.get("departmentsid") == dept_id:
            dept.update({k: v for k, v in updates.items() if k != "departmentsid"})
            found = True
            break

    if not found:
        return None

    data["departments"] = departments
    _save_yaml(config_path, data)

    return get_department(dept_id)


def delete_department(dept_id: str) -> bool:
    """Delete a department: remove from config."""
    config_path = _get_config_dir() / "departments.yaml"
    data = _load_yaml(config_path)
    departments = data.get("departments", [])

    new_departments = [d for d in departments if d.get("departmentsid") != dept_id]
    if len(new_departments) == len(departments):
        return False  # Not found

    data["departments"] = new_departments
    _save_yaml(config_path, data)

    return True


# ─── Otdels (Organizational units with chat channels) ─────────────
# NOTE: Otdels are SEPARATE from Departments (agent groupings).
# Departments = categories in Agents tab (departments.yaml, departmentsid)
# Otdels = org units with chat channels (otdels.yaml, otdelid)


def load_otdels() -> list[dict[str, Any]]:
    """Load otdels from config/otdels.yaml."""
    config_path = _get_config_dir() / "otdels.yaml"
    data = _load_yaml(config_path)
    return data.get("otdels", [])


def save_otdels(otdels: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Save otdels list to config/otdels.yaml."""
    config_path = _get_config_dir() / "otdels.yaml"
    for otdel in otdels:
        if not otdel.get("otdelid"):
            otdel["otdelid"] = _generate_long_id()
    _save_yaml(config_path, {"otdels": otdels})
    return otdels


def _count_agents_in_otdel(otdel: dict) -> int:
    """Count agents in an otdel: head (if set) + workers."""
    count = 0
    if otdel.get("head"):
        count += 1
    count += len(otdel.get("workers", []))
    return count


def get_otdels_with_agents() -> list[dict[str, Any]]:
    """Load otdels with agent counts resolved."""
    otdels = load_otdels()
    for otdel in otdels:
        otdel["agent_count"] = _count_agents_in_otdel(otdel)
    return otdels


def get_otdel(otdel_id: str) -> dict[str, Any] | None:
    """Get a single otdel by ID."""
    otdels = load_otdels()
    for otdel in otdels:
        if otdel.get("otdelid") == otdel_id:
            otdel["agent_count"] = _count_agents_in_otdel(otdel)
            return otdel
    return None


def create_otdel(name: str, description: str = "", color: str = "#f97316",
                 mentor_role: str = "", escalation: str = "",
                 head: str = "", workers: list[str] | None = None) -> dict[str, Any]:
    """Create a new otdel: generates ID, creates directory + otdel.yaml, saves to config."""
    otdel_id = _generate_long_id()
    otdels_dir = _get_otdels_dir()
    otdel_dir = otdels_dir / otdel_id
    otdel_dir.mkdir(parents=True, exist_ok=True)

    # Create otdel.yaml inside the directory
    otdel_data = {
        "otdelid": otdel_id,
        "name": name,
        "description": description,
        "color": color,
        "mentor_role": mentor_role,
        "escalation": escalation,
        "head": head,
        "workers": workers or [],
    }
    _save_yaml(otdel_dir / "otdel.yaml", otdel_data)

    # Create subdirectories for future use
    (otdel_dir / "agents").mkdir(exist_ok=True)
    (otdel_dir / "chat").mkdir(exist_ok=True)

    # Add to otdels.yaml config
    config_path = _get_config_dir() / "otdels.yaml"
    data = _load_yaml(config_path)
    otdels = data.get("otdels", [])
    otdels.append(otdel_data)
    data["otdels"] = otdels
    _save_yaml(config_path, data)

    otdel_data["agent_count"] = 0
    return otdel_data


def update_otdel(otdel_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
    """Update an otdel's fields. Returns updated otdel or None if not found."""
    config_path = _get_config_dir() / "otdels.yaml"
    data = _load_yaml(config_path)
    otdels = data.get("otdels", [])

    found = False
    for otdel in otdels:
        if otdel.get("otdelid") == otdel_id:
            otdel.update({k: v for k, v in updates.items() if k != "otdelid"})
            found = True
            break

    if not found:
        return None

    data["otdels"] = otdels
    _save_yaml(config_path, data)

    # Also update otdel.yaml inside directory
    otdels_dir = _get_otdels_dir()
    otdel_dir = otdels_dir / otdel_id
    if otdel_dir.exists():
        _save_yaml(otdel_dir / "otdel.yaml",
                   next(o for o in otdels if o["otdelid"] == otdel_id))

    return get_otdel(otdel_id)


def delete_otdel(otdel_id: str) -> bool:
    """Delete an otdel: remove from config + delete directory recursively."""
    import shutil

    config_path = _get_config_dir() / "otdels.yaml"
    data = _load_yaml(config_path)
    otdels = data.get("otdels", [])

    new_otdels = [o for o in otdels if o.get("otdelid") != otdel_id]
    if len(new_otdels) == len(otdels):
        return False  # Not found

    data["otdels"] = new_otdels
    _save_yaml(config_path, data)

    # Remove otdel directory (otdel.yaml, agents subdir, etc.)
    otdels_dir = _get_otdels_dir()
    otdel_dir = otdels_dir / otdel_id
    if otdel_dir.exists():
        shutil.rmtree(str(otdel_dir))

    # Remove otdel chat history (data/otdels/<id>/chat.json)
    from ..paths import get_data_dir
    data_dir = get_data_dir()
    if data_dir:
        otdel_data_dir = data_dir / "otdels" / otdel_id
        if otdel_data_dir.exists():
            shutil.rmtree(str(otdel_data_dir))

    return True


# ─── Tools ───────────────────────────────────────────────────────

def load_tools() -> dict[str, Any]:
    """Load tools registry from config/tools.yaml."""
    config_path = _get_config_dir() / "tools.yaml"
    data = _load_yaml(config_path)
    return data


def save_tools(data: dict[str, Any]) -> dict[str, Any]:
    """Save tools registry to config/tools.yaml."""
    config_path = _get_config_dir() / "tools.yaml"
    _save_yaml(config_path, data)
    return data


def get_agent_tools(agentid: str) -> list[str]:
    """Get list of enabled tool names for an agent."""
    agent = get_agent(agentid)
    if not agent:
        return []
    return agent.get("tools", [])


def set_agent_tools(agentid: str, tools: list[str]) -> dict[str, Any]:
    """Set list of enabled tool names for an agent."""
    agent_dir = ensure_agent_dir(agentid)
    agent_yaml_path = agent_dir / "agent.yaml"
    agent_data = _load_yaml(agent_yaml_path)
    agent_data["tools"] = tools
    _save_yaml(agent_yaml_path, agent_data)
    return get_agent(agentid) or {}
