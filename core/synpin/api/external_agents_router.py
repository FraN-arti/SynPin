"""REST API for external agent detection and management."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ..agents import external

router = APIRouter(prefix="/api", tags=["external-agents"])


class ExternalAgentUpdate(BaseModel):
    name: str | None = None
    role: str | None = None
    department: str | None = None
    enabled: bool | None = None


@router.get("/external-agents/detect")
async def detect_external():
    """Detect available external agents in the system (one-time on page load)."""
    # Detect which external agents are available
    detections = await external.detect_external_agents()

    # Register/update each detected agent
    for agent_info in detections:
        if agent_info["available"]:
            external.register_external_agent(agent_info)

    # Return all registered external agents with current status
    agents = external.load_external_agents()

    # Merge detection results with registered config
    detection_map = {d["slug"]: d for d in detections}
    for agent in agents:
        if agent["slug"] in detection_map:
            agent["available"] = detection_map[agent["slug"]]["available"]
            agent["models"] = detection_map[agent["slug"]].get("models", [])

    return {"agents": agents}


@router.get("/external-agents")
async def get_external_agents():
    """Get all registered external agents."""
    agents = external.load_external_agents()
    return {"agents": agents}


@router.get("/external-agents/{slug}")
async def get_external_agent(slug: str):
    """Get a single external agent."""
    agent = external.load_external_agent(slug)
    if not agent:
        raise HTTPException(404, f"External agent not found: {slug}")
    return agent


@router.put("/external-agents/{slug}")
async def update_external_agent(slug: str, req: ExternalAgentUpdate):
    """Update an external agent's settings."""
    updates = req.model_dump(exclude_none=True)
    if not updates:
        agent = external.load_external_agent(slug)
        if not agent:
            raise HTTPException(404, f"External agent not found: {slug}")
        return agent

    result = external.update_external_agent(slug, updates)
    if not result:
        raise HTTPException(404, f"External agent not found: {slug}")
    return result
