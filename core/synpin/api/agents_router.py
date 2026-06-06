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

class DepartmentCreate(BaseModel):
    name: str
    description: str = ""
    color: str = "#f97316"
    mentor_role: str = ""
    escalation: str = ""

class DepartmentUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    color: str | None = None
    mentor_role: str | None = None
    escalation: str | None = None


@router.get("/departments")
async def get_departments():
    """Get all departments with agent counts."""
    return {"departments": manager.get_departments_with_agents()}


@router.get("/departments/{dept_id}")
async def get_department(dept_id: str):
    """Get a single department by ID."""
    dept = manager.get_department(dept_id)
    if not dept:
        raise HTTPException(404, f"Department not found: {dept_id}")
    return dept


@router.post("/departments")
async def create_department(req: DepartmentCreate):
    """Create a new department."""
    return manager.create_department(
        name=req.name,
        description=req.description,
        color=req.color,
        mentor_role=req.mentor_role,
        escalation=req.escalation,
    )


@router.put("/departments/{dept_id}")
async def update_department(dept_id: str, req: DepartmentUpdate):
    """Update a department."""
    updates = req.model_dump(exclude_none=True)
    if not updates:
        dept = manager.get_department(dept_id)
        if not dept:
            raise HTTPException(404, f"Department not found: {dept_id}")
        return dept
    result = manager.update_department(dept_id, updates)
    if not result:
        raise HTTPException(404, f"Department not found: {dept_id}")
    return result


@router.delete("/departments/{dept_id}")
async def delete_department(dept_id: str):
    """Delete a department and its directory."""
    ok = manager.delete_department(dept_id)
    if not ok:
        raise HTTPException(404, f"Department not found: {dept_id}")
    return {"ok": True}


# ─── Otdels (Organizational units with chat channels) ─────────────

class OtdelCreate(BaseModel):
    name: str
    description: str = ""
    color: str = "#f97316"
    mentor_role: str = ""
    escalation: str = ""
    head: str = ""
    workers: list[str] = []


class OtdelUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    color: str | None = None
    mentor_role: str | None = None
    escalation: str | None = None
    head: str | None = None
    workers: list[str] | None = None


@router.get("/otdels")
async def get_otdels():
    """Get all otdels with agent counts."""
    return {"otdels": manager.get_otdels_with_agents()}


@router.get("/otdels/{otdel_id}")
async def get_otdel(otdel_id: str):
    """Get a single otdel by ID."""
    otdel = manager.get_otdel(otdel_id)
    if not otdel:
        raise HTTPException(404, f"Otdel not found: {otdel_id}")
    return otdel


@router.post("/otdels")
async def create_otdel(req: OtdelCreate):
    """Create a new otdel."""
    return manager.create_otdel(
        name=req.name,
        description=req.description,
        color=req.color,
        mentor_role=req.mentor_role,
        escalation=req.escalation,
        head=req.head,
        workers=req.workers,
    )


@router.put("/otdels/{otdel_id}")
async def update_otdel(otdel_id: str, req: OtdelUpdate):
    """Update an otdel."""
    updates = req.model_dump(exclude_none=True)
    if not updates:
        otdel = manager.get_otdel(otdel_id)
        if not otdel:
            raise HTTPException(404, f"Otdel not found: {otdel_id}")
        return otdel
    result = manager.update_otdel(otdel_id, updates)
    if not result:
        raise HTTPException(404, f"Otdel not found: {otdel_id}")
    return result


@router.delete("/otdels/{otdel_id}")
async def delete_otdel(otdel_id: str):
    """Delete an otdel and its directory."""
    ok = manager.delete_otdel(otdel_id)
    if not ok:
        raise HTTPException(404, f"Otdel not found: {otdel_id}")
    return {"ok": True}


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
