"""Kanban configuration — columns, labels, and widget settings.

Stored in kanban/kanban.yaml. Hot-reloaded via ConfigWatcher.
"""
from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class ColumnConfig(BaseModel):
    """A single column on the Kanban board."""
    id: str                       # backlog, todo, in_progress, etc.
    label: str                    # Display name
    color: str = "#6b7280"       # Color for the indicator square
    order: int = 0               # Sort order on the board
    enabled: bool = True         # Show/hide this column


class LabelConfig(BaseModel):
    """A tag/label that can be assigned to tasks."""
    id: str                       # system, service, bug, feature, etc.
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


def _default_columns() -> list[ColumnConfig]:
    return [
        ColumnConfig(id="backlog", label="Backlog", color="#6b7280", order=0),
        ColumnConfig(id="todo", label="TODO", color="#3b82f6", order=1),
        ColumnConfig(id="in_progress", label="In Progress", color="#f97316", order=2),
        ColumnConfig(id="review", label="Review", color="#f59e0b", order=3),
        ColumnConfig(id="revision", label="Revision", color="#ef4444", order=4),
        ColumnConfig(id="blocked", label="Blocked", color="#dc2626", order=5),
        ColumnConfig(id="done", label="Done", color="#22c55e", order=6),
    ]


def _default_labels() -> list[LabelConfig]:
    return [
        LabelConfig(id="system", name="#System", color="#1e3a5f", text_color="#93c5fd"),
        LabelConfig(id="service", name="#Service", color="#166534", text_color="#bbf7d0"),
        LabelConfig(id="bug", name="#Bug", color="#7f1d1d", text_color="#fca5a5"),
        LabelConfig(id="feature", name="#Feature", color="#4c1d95", text_color="#c4b5fd"),
        LabelConfig(id="urgent", name="#Urgent", color="#78350f", text_color="#fcd34d"),
    ]


class KanbanConfig(BaseModel):
    """Full Kanban board configuration."""
    columns: list[ColumnConfig] = Field(default_factory=_default_columns)
    labels: list[LabelConfig] = Field(default_factory=_default_labels)
    widget: WidgetConfig = Field(default_factory=WidgetConfig)

    # Board settings
    max_active_tasks: int = 50
    auto_archive_days: int = 30
    notifications_enabled: bool = True

    # Automation
    auto_assign_head: bool = True
    auto_summon: bool = False
    auto_escalate_overdue: bool = False
    notify_human_on_block: bool = False


# ── Config file I/O ─────────────────────────────────────────────────────────

_config_lock = threading.Lock()


def _get_config_dir() -> Path:
    """Resolve kanban config directory."""
    dev = Path(__file__).resolve().parent.parent / "kanban"
    prod = Path.home() / ".synpin" / "config"

    if os.environ.get("SYNPIN_DEV") == "1":
        return dev

    if prod.exists():
        return prod

    return dev


def _get_config_path() -> Path:
    return _get_config_dir() / "kanban.yaml"


def load_config() -> KanbanConfig:
    """Load kanban config from YAML, or create defaults."""
    path = _get_config_path()
    if path.exists():
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            if data:
                return KanbanConfig.model_validate(data)
        except Exception as e:
            print(f"[kanban] Config load error: {e}, using defaults")
    return KanbanConfig()


def save_config(config: KanbanConfig) -> Path:
    """Save kanban config to YAML."""
    path = _get_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with _config_lock:
        data = config.model_dump(mode="json")
        path.write_text(
            yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False, width=120),
            encoding="utf-8",
        )
    return path


def get_columns() -> list[ColumnConfig]:
    """Get enabled columns, sorted by order."""
    config = load_config()
    return sorted(
        [c for c in config.columns if c.enabled],
        key=lambda c: c.order,
    )


def get_all_columns() -> list[ColumnConfig]:
    """Get all columns (including disabled), sorted by order."""
    config = load_config()
    return sorted(config.columns, key=lambda c: c.order)


def get_labels() -> list[LabelConfig]:
    """Get all labels."""
    config = load_config()
    return config.labels


def get_widget_config() -> WidgetConfig:
    """Get widget settings."""
    config = load_config()
    return config.widget
