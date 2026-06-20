"""REST API for external agent detection and management."""
import logging
from fastapi import APIRouter, HTTPException
from ._base import BaseRequest
from ..agents import external

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["external-agents"])


class ExternalAgentUpdate(BaseRequest):
    name: str | None = None
    role: str | None = None
    department: str | None = None
    enabled: bool | None = None
    is_primary: bool | None = None


@router.get("/external-agents/detect")
async def detect_external():
    """Detect available external agents in the system (one-time on page load)."""
    try:
        detections = await external.detect_external_agents()

        for agent_info in detections:
            if agent_info["available"]:
                external.register_external_agent(agent_info)

        agents = external.load_external_agents()

        detection_map = {d["slug"]: d for d in detections}
        for agent in agents:
            if agent["slug"] in detection_map:
                agent["available"] = detection_map[agent["slug"]]["available"]
                agent["models"] = detection_map[agent["slug"]].get("models", [])

        return {"agents": agents}
    except Exception as e:
        logger.error("Failed to detect external agents: %s", e)
        raise HTTPException(500, "Failed to detect external agents")


@router.get("/external-agents")
async def get_external_agents():
    """Get all registered external agents."""
    try:
        agents = external.load_external_agents()
        return {"agents": agents}
    except Exception as e:
        logger.error("Failed to load external agents: %s", e)
        raise HTTPException(500, "Failed to load external agents")


@router.get("/external-agents/{slug}")
async def get_external_agent(slug: str):
    """Get a single external agent."""
    try:
        agent = external.load_external_agent(slug)
        if not agent:
            raise HTTPException(404, f"External agent not found: {slug}")
        return agent
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get external agent %s: %s", slug, e)
        raise HTTPException(500, "Failed to get external agent")


@router.put("/external-agents/{slug}")
async def update_external_agent(slug: str, req: ExternalAgentUpdate):
    """Update an external agent's settings."""
    try:
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
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update external agent %s: %s", slug, e)
        raise HTTPException(500, "Failed to update external agent")
