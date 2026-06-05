"""REST API for managing AI agents configuration."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from ..agents import manager

router = APIRouter(prefix="/api", tags=["agents"])


class AgentUpdate(BaseModel):
    enabled: bool | None = None
    role: str | None = None
    department: str | None = None
    model: str | None = None
    provider: str | None = None
    skills: list[str] | None = None
    name: str | None = None
    description: str | None = None
    tone: str | None = None
    style: str | None = None
    traits: list[str] | None = None
    system_prompt: str | None = None
    max_iterations: int | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    memory: dict | None = None
    is_primary: bool | None = None


class AgentCreate(BaseModel):
    name: str
    role: str = ""
    department: str = ""
    model: str = ""
    description: str = ""
    system_prompt: str = ""
    tone: str = ""
    style: str = ""
    traits: list[str] = []
    temperature: float = 0.7
    max_tokens: int | None = None


# ─── Agents ───────────────────────────────────────────────────────


@router.get("/agents")
async def get_all_agents():
    """Get all agents with resolved settings (global + per-agent merged)."""
    return manager.load_agents()


@router.post("/agents")
async def create_agent(req: AgentCreate):
    """Create a new agent."""
    return manager.create_agent(
        name=req.name,
        role=req.role,
        department=req.department,
        model=req.model,
        description=req.description,
        system_prompt=req.system_prompt,
        tone=req.tone,
        style=req.style,
        traits=req.traits,
        temperature=req.temperature,
        max_tokens=req.max_tokens,
    )


@router.delete("/agents/{slug}")
async def delete_agent(slug: str):
    """Delete an agent."""
    ok = manager.delete_agent(slug)
    if not ok:
        raise HTTPException(404, f"Agent not found: {slug}")
    return {"ok": True}


@router.get("/agents/{slug}")
async def get_agent(slug: str):
    """Get a single agent by slug."""
    agent = manager.get_agent(slug)
    if not agent:
        raise HTTPException(404, f"Agent not found: {slug}")
    return agent


@router.put("/agents/{slug}")
async def update_agent(slug: str, req: AgentUpdate):
    """Update an agent. Splits operational (agents.yaml) and personalization (agent.yaml)."""
    existing = manager.get_agent(slug)
    if not existing:
        raise HTTPException(404, f"Agent not found: {slug}")

    updates = req.model_dump(exclude_none=True)
    if not updates:
        return existing

    result = manager.save_agent(slug, updates)
    return result


@router.get("/agents/{slug}/avatar")
async def get_agent_avatar(slug: str):
    """Get agent avatar image. Falls back to null if not found."""
    agent_dir = manager.ensure_agent_dir(slug)

    for ext in ("png", "jpg", "jpeg", "svg", "webp", "gif"):
        avatar_path = agent_dir / f"avatar.{ext}"
        if avatar_path.exists():
            return FileResponse(str(avatar_path))

    raise HTTPException(404, f"No avatar found for agent: {slug}")


# ─── Roles ────────────────────────────────────────────────────────

@router.get("/roles")
async def get_roles():
    """Get all roles."""
    return {"roles": manager.load_roles()}


@router.put("/roles")
async def update_roles(req: dict):
    """Replace all roles."""
    roles = req.get("roles", [])
    return {"roles": manager.save_roles(roles)}


# ─── Departments ──────────────────────────────────────────────────

@router.get("/departments")
async def get_departments():
    """Get all departments."""
    return {"departments": manager.load_departments()}


@router.put("/departments")
async def update_departments(req: dict):
    """Replace all departments."""
    departments = req.get("departments", [])
    return {"departments": manager.save_departments(departments)}


# ─── Tools ───────────────────────────────────────────────────────

@router.get("/tools")
async def get_tools():
    """Get tools registry."""
    return manager.load_tools()


@router.get("/tools/{agentid}")
async def get_agent_tools(agentid: str):
    """Get enabled tools for an agent."""
    return {"tools": manager.get_agent_tools(agentid)}


@router.put("/tools/{agentid}")
async def set_agent_tools(agentid: str, req: dict):
    """Set enabled tools for an agent."""
    tools = req.get("tools", [])
    return {"tools": manager.set_agent_tools(agentid, tools)}
