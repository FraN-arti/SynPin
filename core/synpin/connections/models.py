"""Connection models — Pydantic schemas for inter-department relationships.

Each connection is stored in config/connections.yaml.
Escalation history is stored in data/escalation_history.yaml.
Canvas positions are stored in data/canvas/positions.json.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ── Enums ────────────────────────────────────────────────────────────────────

class ConnectionType(str, Enum):
    """Types of connections between departments."""
    PEER = "peer"              # Equal-level, bidirectional cooperation
    ESCALATION = "escalation"  # Upward — child reports to parent
    DELEGATION = "delegation"  # Downward — parent assigns to child


class EscalationStatus(str, Enum):
    """Status of an escalation event."""
    PENDING = "pending"        # Escalation in progress
    COMPLETED = "completed"    # Resolved by target department
    REJECTED = "rejected"      # Rejected / sent back


# ── Connection ───────────────────────────────────────────────────────────────

class AutoTriggerConfig(BaseModel):
    """Auto-escalation trigger configuration."""
    on_status: str = "blocked"     # Task status that triggers escalation
    timeout_s: int = 3600          # Seconds before auto-escalation


class Connection(BaseModel):
    """A structural relationship between two departments."""
    id: str                                    # conn-001, conn-002, etc.
    from_otdel: str                            # Source department slug
    to_otdel: str                              # Target department slug
    type: ConnectionType = ConnectionType.PEER
    label: str = ""                            # Display name
    description: str = ""                      # Details
    active: bool = True
    auto_trigger: AutoTriggerConfig | None = None  # Only for escalation type
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


# ── Escalation History ──────────────────────────────────────────────────────

class EscalationRecord(BaseModel):
    """A single escalation event in the history."""
    id: str                                    # esc-001, esc-002, etc.
    task_id: str                               # Kanban task ID (T-xxx)
    from_otdel: str                            # Source department slug
    to_otdel: str                              # Target department slug
    connection_id: str                         # Connection used
    reason: str = ""                           # Why escalated
    report: str = ""                           # Detailed report
    status: EscalationStatus = EscalationStatus.PENDING
    timestamp: datetime = Field(default_factory=datetime.now)
    resolved_at: datetime | None = None
    resolution: str = ""                       # How it was resolved


# ── Canvas ───────────────────────────────────────────────────────────────────

class NodePosition(BaseModel):
    """Position of a department node on the canvas."""
    x: float = 0.0
    y: float = 0.0


class CanvasData(BaseModel):
    """Canvas state — node positions and viewport."""
    version: int = 1
    nodes: dict[str, NodePosition] = Field(default_factory=dict)
    viewport: dict[str, float] = Field(default_factory=lambda: {"x": 0, "y": 0, "zoom": 1})


# ── Graph (for React Flow) ──────────────────────────────────────────────────

class GraphNode(BaseModel):
    """A node in the connections graph (for React Flow)."""
    id: str
    type: str = "department"
    position: NodePosition = Field(default_factory=NodePosition)
    data: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    """An edge in the connections graph (for React Flow)."""
    id: str
    source: str
    target: str
    type: str = "default"
    label: str = ""
    animated: bool = False
    data: dict[str, Any] = Field(default_factory=dict)


class Graph(BaseModel):
    """Complete graph for React Flow rendering."""
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
