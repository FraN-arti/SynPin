"""REST API for managing AI agents configuration."""
import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from ._base import BaseRequest
from ..agents import manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["agents"])


class AgentUpdate(BaseRequest):
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


class AgentCreate(BaseRequest):
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
    try:
        return manager.load_agents()
    except Exception as e:
        logger.error("Failed to load agents: %s", e)
        raise HTTPException(500, "Failed to load agents")


@router.post("/agents")
async def create_agent(req: AgentCreate):
    """Create a new agent."""
    try:
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
    except Exception as e:
        logger.error("Failed to create agent: %s", e)
        raise HTTPException(500, "Failed to create agent")


@router.delete("/agents/{slug}")
async def delete_agent(slug: str):
    """Delete an agent."""
    try:
        ok = manager.delete_agent(slug)
        if not ok:
            raise HTTPException(404, f"Agent not found: {slug}")
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete agent %s: %s", slug, e)
        raise HTTPException(500, "Failed to delete agent")


@router.get("/agents/{slug}")
async def get_agent(slug: str):
    """Get a single agent by slug."""
    try:
        agent = manager.get_agent(slug)
        if not agent:
            raise HTTPException(404, f"Agent not found: {slug}")
        return agent
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get agent %s: %s", slug, e)
        raise HTTPException(500, "Failed to get agent")


@router.put("/agents/{slug}")
async def update_agent(slug: str, req: AgentUpdate):
    """Update an agent. Splits operational (agents.yaml) and personalization (agent.yaml)."""
    try:
        existing = manager.get_agent(slug)
        if not existing:
            raise HTTPException(404, f"Agent not found: {slug}")

        updates = req.model_dump(exclude_none=True)
        if not updates:
            return existing

        result = manager.save_agent(slug, updates)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update agent %s: %s", slug, e)
        raise HTTPException(500, "Failed to update agent")


@router.get("/agents/{slug}/avatar")
async def get_agent_avatar(slug: str):
    """Get agent avatar image. Falls back to null if not found."""
    try:
        agent_dir = manager.ensure_agent_dir(slug)

        for ext in ("png", "jpg", "jpeg", "svg", "webp", "gif"):
            avatar_path = agent_dir / f"avatar.{ext}"
            if avatar_path.exists():
                return FileResponse(str(avatar_path))

        raise HTTPException(404, f"No avatar found for agent: {slug}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get avatar for %s: %s", slug, e)
        raise HTTPException(500, "Failed to get avatar")


# ─── Roles ────────────────────────────────────────────────────────


@router.get("/roles")
async def get_roles():
    """Get all roles."""
    try:
        return manager.load_roles()
    except Exception as e:
        logger.error("Failed to load roles: %s", e)
        raise HTTPException(500, "Failed to load roles")


@router.put("/roles")
async def update_roles(req: dict):
    """Replace all roles."""
    try:
        roles = req.get("roles", [])
        is_default = req.get("is_default")
        return {"roles": manager.save_roles(roles, is_default)}
    except Exception as e:
        logger.error("Failed to update roles: %s", e)
        raise HTTPException(500, "Failed to update roles")


# ─── Departments ──────────────────────────────────────────────────

class DepartmentCreate(BaseRequest):
    name: str
    description: str = ""
    color: str = "#f97316"
    mentor_role: str = ""
    escalation: str = ""

class DepartmentUpdate(BaseRequest):
    name: str | None = None
    description: str | None = None
    color: str | None = None
    mentor_role: str | None = None
    escalation: str | None = None


@router.get("/departments")
async def get_departments():
    """Get all departments with agent counts."""
    try:
        return manager.load_departments()
    except Exception as e:
        logger.error("Failed to load departments: %s", e)
        raise HTTPException(500, "Failed to load departments")


@router.put("/departments")
async def update_departments(req: dict):
    """Replace all departments."""
    try:
        departments = req.get("departments", [])
        is_default = req.get("is_default")
        return {"departments": manager.save_departments(departments, is_default)}
    except Exception as e:
        logger.error("Failed to update departments: %s", e)
        raise HTTPException(500, "Failed to update departments")


@router.get("/departments/{dept_id}")
async def get_department(dept_id: str):
    """Get a single department by ID."""
    try:
        dept = manager.get_department(dept_id)
        if not dept:
            raise HTTPException(404, f"Department not found: {dept_id}")
        return dept
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get department %s: %s", dept_id, e)
        raise HTTPException(500, "Failed to get department")


@router.post("/departments")
async def create_department(req: DepartmentCreate):
    """Create a new department."""
    try:
        return manager.create_department(
            name=req.name,
            description=req.description,
            color=req.color,
            mentor_role=req.mentor_role,
            escalation=req.escalation,
        )
    except Exception as e:
        logger.error("Failed to create department: %s", e)
        raise HTTPException(500, "Failed to create department")


@router.put("/departments/{dept_id}")
async def update_department(dept_id: str, req: DepartmentUpdate):
    """Update a department."""
    try:
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
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update department %s: %s", dept_id, e)
        raise HTTPException(500, "Failed to update department")


@router.delete("/departments/{dept_id}")
async def delete_department(dept_id: str):
    """Delete a department and its directory."""
    try:
        ok = manager.delete_department(dept_id)
        if not ok:
            raise HTTPException(404, f"Department not found: {dept_id}")
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete department %s: %s", dept_id, e)
        raise HTTPException(500, "Failed to delete department")


# ─── Otdels (Organizational units with chat channels) ─────────────

class OtdelCreate(BaseRequest):
    name: str
    description: str = ""
    color: str = "#f97316"
    mentor_role: str = ""
    escalation: str = ""
    head: str = ""
    workers: list[str] = []


class OtdelUpdate(BaseRequest):
    name: str | None = None
    description: str | None = None
    color: str | None = None
    mentor_role: str | None = None
    escalation: str | None = None
    head: str | None = None
    workers: list[str] | None = None
    compaction_limit: int | None = None
    keep_recent: int | None = None


@router.get("/otdels")
async def get_otdels():
    """Get all otdels with agent counts."""
    try:
        return {"otdels": manager.get_otdels_with_agents()}
    except Exception as e:
        logger.error("Failed to load otdels: %s", e)
        raise HTTPException(500, "Failed to load otdels")


@router.get("/otdels/{otdel_id}")
async def get_otdel(otdel_id: str):
    """Get a single otdel by ID."""
    try:
        otdel = manager.get_otdel(otdel_id)
        if not otdel:
            raise HTTPException(404, f"Otdel not found: {otdel_id}")
        return otdel
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get otdel %s: %s", otdel_id, e)
        raise HTTPException(500, "Failed to get otdel")


@router.post("/otdels")
async def create_otdel(req: OtdelCreate):
    """Create a new otdel."""
    try:
        return manager.create_otdel(
            name=req.name,
            description=req.description,
            color=req.color,
            mentor_role=req.mentor_role,
            escalation=req.escalation,
            head=req.head,
            workers=req.workers,
        )
    except Exception as e:
        logger.error("Failed to create otdel: %s", e)
        raise HTTPException(500, "Failed to create otdel")


@router.put("/otdels/{otdel_id}")
async def update_otdel(otdel_id: str, req: OtdelUpdate):
    """Update an otdel."""
    try:
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
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update otdel %s: %s", otdel_id, e)
        raise HTTPException(500, "Failed to update otdel")


@router.delete("/otdels/{otdel_id}")
async def delete_otdel(otdel_id: str):
    """Delete an otdel and its directory."""
    try:
        ok = manager.delete_otdel(otdel_id)
        if not ok:
            raise HTTPException(404, f"Otdel not found: {otdel_id}")
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete otdel %s: %s", otdel_id, e)
        raise HTTPException(500, "Failed to delete otdel")


# ─── Tools ───────────────────────────────────────────────────────

@router.get("/tools")
async def get_tools():
    """Get tools registry."""
    try:
        return manager.load_tools()
    except Exception as e:
        logger.error("Failed to load tools: %s", e)
        raise HTTPException(500, "Failed to load tools")


@router.get("/tools/{agentid}")
async def get_agent_tools(agentid: str):
    """Get enabled tools for an agent."""
    try:
        return {"tools": manager.get_agent_tools(agentid)}
    except Exception as e:
        logger.error("Failed to get tools for %s: %s", agentid, e)
        raise HTTPException(500, "Failed to get agent tools")


@router.put("/tools/{agentid}")
async def set_agent_tools(agentid: str, req: dict):
    """Set enabled tools for an agent."""
    try:
        tools = req.get("tools", [])
        return {"tools": manager.set_agent_tools(agentid, tools)}
    except Exception as e:
        logger.error("Failed to set tools for %s: %s", agentid, e)
        raise HTTPException(500, "Failed to set agent tools")
