"""Kanban configuration — columns, labels, and widget settings.

Structured storage: each section in its own YAML file under config/.
Hot-reloaded via ConfigWatcher. WebSocket broadcast on every change.
"""
from __future__ import annotations

import os
import random
import string
import threading
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


# ── ID Generation ────────────────────────────────────────────────────────────

def generate_id(length: int = 14) -> str:
    """Generate unique alphanumeric ID (14 chars by default)."""
    chars = string.ascii_lowercase + string.digits
    return ''.join(random.choices(chars, k=length))


# ── Models ───────────────────────────────────────────────────────────────────

class ColumnConfig(BaseModel):
    """A single column on the Kanban board."""
    id: str                       # 14-char alphanumeric
    label: str                    # Display name
    color: str = "#6b7280"       # Color for the indicator square
    order: int = 0               # Sort order on the board
    enabled: bool = True         # Show/hide this column


class LabelConfig(BaseModel):
    """A tag/label that can be assigned to tasks."""
    id: str                       # 14-char alphanumeric
    name: str                     # Display name: #System, #Service
    color: str = "#6b7280"       # Background color
    text_color: str = "#ffffff"  # Text color


class WidgetConfig(BaseModel):
    """Settings for the Kanban widget on the dashboard."""
    mode: str = "active"          # active | all | my | blocked
    max_items: int = 5            # Max items to show
    show_columns: list[str] = Field(default_factory=lambda: ["in_progress", "review", "blocked"])
    show_deadline: bool = True
    show_department: bool = True
    compact: bool = True          # Compact vs detailed view


class BoardSettings(BaseModel):
    """Board settings and automation."""
    max_active_tasks: int = 50
    auto_archive_days: int = 30
    notifications_enabled: bool = True
    auto_assign_head: bool = True
    auto_summon: bool = False
    auto_escalate_overdue: bool = False
    notify_human_on_block: bool = False


# ── Defaults ─────────────────────────────────────────────────────────────────

def _default_columns() -> list[ColumnConfig]:
    return [
        ColumnConfig(id=generate_id(), label="Backlog", color="#6b7280", order=0),
        ColumnConfig(id=generate_id(), label="TODO", color="#3b82f6", order=1),
        ColumnConfig(id=generate_id(), label="In Progress", color="#f97316", order=2),
        ColumnConfig(id=generate_id(), label="Review", color="#f59e0b", order=3),
        ColumnConfig(id=generate_id(), label="Revision", color="#ef4444", order=4),
        ColumnConfig(id=generate_id(), label="Blocked", color="#dc2626", order=5),
        ColumnConfig(id=generate_id(), label="Done", color="#22c55e", order=6),
    ]


def _default_labels() -> list[LabelConfig]:
    return [
        LabelConfig(id=generate_id(), name="#System", color="#1e3a5f", text_color="#93c5fd"),
        LabelConfig(id=generate_id(), name="#Service", color="#166534", text_color="#bbf7d0"),
        LabelConfig(id=generate_id(), name="#Bug", color="#7f1d1d", text_color="#fca5a5"),
        LabelConfig(id=generate_id(), name="#Feature", color="#4c1d95", text_color="#c4b5fd"),
        LabelConfig(id=generate_id(), name="#Urgent", color="#78350f", text_color="#fcd34d"),
    ]


# ── Config directory ─────────────────────────────────────────────────────────

_config_lock = threading.Lock()


def _get_config_dir() -> Path:
    """Resolve kanban config directory."""
    dev = Path(__file__).resolve().parent / "config"
    prod = Path.home() / ".synpin" / "config" / "kanban"

    if os.environ.get("SYNPIN_DEV") == "1":
        dev.mkdir(parents=True, exist_ok=True)
        return dev

    if prod.exists():
        return prod

    dev.mkdir(parents=True, exist_ok=True)
    return dev


def _yaml_path(name: str) -> Path:
    """Get path for a specific config file."""
    return _get_config_dir() / f"{name}.yaml"


# ── Broadcast helper ─────────────────────────────────────────────────────────

_config_broadcast = None  # Set by server.py on startup


def set_config_broadcast(fn) -> None:
    """Set the broadcast function for config changes."""
    global _config_broadcast
    _config_broadcast = fn


def _broadcast_config(event_type: str, data: dict) -> None:
    """Broadcast config change to all connected clients."""
    if _config_broadcast:
        try:
            _config_broadcast({"type": event_type, **data})
        except Exception:
            pass


# ── File I/O ─────────────────────────────────────────────────────────────────

def _load_yaml(name: str) -> dict | list | None:
    """Load a YAML file."""
    path = _yaml_path(name)
    if path.exists():
        try:
            return yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[kanban] Config load error ({name}): {e}")
    return None


def _save_yaml(name: str, data) -> None:
    """Save data to a YAML file."""
    with _config_lock:
        path = _yaml_path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False, width=120),
            encoding="utf-8",
        )


# ── Columns ──────────────────────────────────────────────────────────────────

def load_columns() -> list[ColumnConfig]:
    """Load columns from config."""
    data = _load_yaml("columns")
    if data and isinstance(data, list):
        return [ColumnConfig(**c) for c in data]
    cols = _default_columns()
    save_columns(cols)
    return cols


def save_columns(columns: list[ColumnConfig]) -> None:
    """Save columns and broadcast update."""
    _save_yaml("columns", [c.model_dump() for c in columns])
    _broadcast_config("kanban:columns_updated", {
        "columns": [c.model_dump() for c in columns]
    })


def get_enabled_columns() -> list[ColumnConfig]:
    """Get enabled columns sorted by order."""
    return sorted(
        [c for c in load_columns() if c.enabled],
        key=lambda c: c.order,
    )


# ── Labels ───────────────────────────────────────────────────────────────────

def load_labels() -> list[LabelConfig]:
    """Load labels from config."""
    data = _load_yaml("labels")
    if data and isinstance(data, list):
        return [LabelConfig(**l) for l in data]
    labels = _default_labels()
    save_labels(labels)
    return labels


def save_labels(labels: list[LabelConfig]) -> None:
    """Save labels and broadcast update."""
    _save_yaml("labels", [l.model_dump() for l in labels])
    _broadcast_config("kanban:labels_updated", {
        "labels": [l.model_dump() for l in labels]
    })


# ── Widget ───────────────────────────────────────────────────────────────────

def load_widget() -> WidgetConfig:
    """Load widget config."""
    data = _load_yaml("widget")
    if data and isinstance(data, dict):
        return WidgetConfig(**data)
    widget = WidgetConfig()
    save_widget(widget)
    return widget


def save_widget(widget: WidgetConfig) -> None:
    """Save widget config and broadcast update."""
    _save_yaml("widget", widget.model_dump())
    _broadcast_config("kanban:widget_updated", {
        "widget": widget.model_dump()
    })


# ── Board Settings ───────────────────────────────────────────────────────────

def load_settings() -> BoardSettings:
    """Load board settings."""
    data = _load_yaml("settings")
    if data and isinstance(data, dict):
        return BoardSettings(**data)
    settings = BoardSettings()
    save_settings(settings)
    return settings


def save_settings(settings: BoardSettings) -> None:
    """Save board settings and broadcast update."""
    _save_yaml("settings", settings.model_dump())
    _broadcast_config("kanban:settings_updated", {
        "settings": settings.model_dump()
    })


# ── Legacy compatibility ────────────────────────────────────────────────────

class KanbanConfig(BaseModel):
    """Full config for backward compat (used by service.py)."""
    columns: list[ColumnConfig] = Field(default_factory=load_columns)
    labels: list[LabelConfig] = Field(default_factory=load_labels)
    widget: WidgetConfig = Field(default_factory=load_widget)
    settings: BoardSettings = Field(default_factory=load_settings)


def load_config() -> KanbanConfig:
    """Load full config (legacy compat)."""
    return KanbanConfig()


def save_config(config: KanbanConfig) -> None:
    """Save full config (legacy compat)."""
    save_columns(config.columns)
    save_labels(config.labels)
    save_widget(config.widget)
    save_settings(config.settings)
