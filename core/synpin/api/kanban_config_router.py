"""Kanban Config API — manage columns, labels, and widget settings."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..kanban.config import (
    KanbanConfig,
    ColumnConfig,
    LabelConfig,
    WidgetConfig,
    load_config,
    save_config,
    get_columns,
    get_all_columns,
    get_labels,
    get_widget_config,
)

router = APIRouter(prefix="/api/kanban/config", tags=["kanban-config"])


# ── Request models ───────────────────────────────────────────────────────────

class ColumnRequest(BaseModel):
    id: str
    label: str
    color: str = "#6b7280"
    order: int = 0
    enabled: bool = True


class LabelRequest(BaseModel):
    id: str
    name: str
    color: str = "#6b7280"
    text_color: str = "#ffffff"


class WidgetRequest(BaseModel):
    mode: str | None = None
    max_items: int | None = None
    show_columns: list[str] | None = None
    show_deadline: bool | None = None
    show_department: bool | None = None
    compact: bool | None = None


class BoardSettingsRequest(BaseModel):
    max_active_tasks: int | None = None
    auto_archive_days: int | None = None
    notifications_enabled: bool | None = None
    auto_assign_head: bool | None = None
    auto_summon: bool | None = None
    auto_escalate_overdue: bool | None = None
    notify_human_on_block: bool | None = None


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/columns")
def list_columns() -> list[dict]:
    """Get all columns (enabled + disabled)."""
    return [c.model_dump() for c in get_all_columns()]


@router.put("/columns")
def set_columns(columns: list[ColumnRequest]) -> list[dict]:
    """Replace all columns."""
    config = load_config()
    config.columns = [ColumnConfig(**c.model_dump()) for c in columns]
    save_config(config)
    return [c.model_dump() for c in config.columns]


@router.post("/columns")
def add_column(col: ColumnRequest) -> dict:
    """Add a new column."""
    config = load_config()
    # Check for duplicate id
    if any(c.id == col.id for c in config.columns):
        raise HTTPException(400, f"Column '{col.id}' already exists")
    config.columns.append(ColumnConfig(**col.model_dump()))
    save_config(config)
    return col.model_dump()


@router.delete("/columns/{column_id}")
def delete_column(column_id: str) -> dict:
    """Remove a column."""
    config = load_config()
    before = len(config.columns)
    config.columns = [c for c in config.columns if c.id != column_id]
    if len(config.columns) == before:
        raise HTTPException(404, f"Column '{column_id}' not found")
    save_config(config)
    return {"status": "ok", "deleted": column_id}


@router.patch("/columns/{column_id}")
def update_column(column_id: str, col: ColumnRequest) -> dict:
    """Update a single column."""
    config = load_config()
    for i, c in enumerate(config.columns):
        if c.id == column_id:
            config.columns[i] = ColumnConfig(**col.model_dump())
            save_config(config)
            return config.columns[i].model_dump()
    raise HTTPException(404, f"Column '{column_id}' not found")


# ── Labels ───────────────────────────────────────────────────────────────────

@router.get("/labels")
def list_labels() -> list[dict]:
    """Get all labels."""
    return [l.model_dump() for l in get_labels()]


@router.put("/labels")
def set_labels(labels: list[LabelRequest]) -> list[dict]:
    """Replace all labels."""
    config = load_config()
    config.labels = [LabelConfig(**l.model_dump()) for l in labels]
    save_config(config)
    return [l.model_dump() for l in config.labels]


@router.post("/labels")
def add_label(label: LabelRequest) -> dict:
    """Add a new label."""
    config = load_config()
    if any(l.id == label.id for l in config.labels):
        raise HTTPException(400, f"Label '{label.id}' already exists")
    config.labels.append(LabelConfig(**label.model_dump()))
    save_config(config)
    return label.model_dump()


@router.delete("/labels/{label_id}")
def delete_label(label_id: str) -> dict:
    """Remove a label."""
    config = load_config()
    before = len(config.labels)
    config.labels = [l for l in config.labels if l.id != label_id]
    if len(config.labels) == before:
        raise HTTPException(404, f"Label '{label_id}' not found")
    save_config(config)
    return {"status": "ok", "deleted": label_id}


@router.patch("/labels/{label_id}")
def update_label(label_id: str, label: LabelRequest) -> dict:
    """Update a single label."""
    config = load_config()
    for i, l in enumerate(config.labels):
        if l.id == label_id:
            config.labels[i] = LabelConfig(**label.model_dump())
            save_config(config)
            return config.labels[i].model_dump()
    raise HTTPException(404, f"Label '{label_id}' not found")


# ── Widget ───────────────────────────────────────────────────────────────────

@router.get("/widget")
def get_widget() -> dict:
    """Get widget configuration."""
    return get_widget_config().model_dump()


@router.put("/widget")
def set_widget(req: WidgetRequest) -> dict:
    """Update widget configuration."""
    config = load_config()
    widget = config.widget
    if req.mode is not None:
        widget.mode = req.mode
    if req.max_items is not None:
        widget.max_items = req.max_items
    if req.show_columns is not None:
        widget.show_columns = req.show_columns
    if req.show_deadline is not None:
        widget.show_deadline = req.show_deadline
    if req.show_department is not None:
        widget.show_department = req.show_department
    if req.compact is not None:
        widget.compact = req.compact
    save_config(config)
    return widget.model_dump()


# ── Board Settings ───────────────────────────────────────────────────────────

@router.get("/settings")
def get_settings() -> dict:
    """Get board settings."""
    config = load_config()
    return {
        "max_active_tasks": config.max_active_tasks,
        "auto_archive_days": config.auto_archive_days,
        "notifications_enabled": config.notifications_enabled,
        "auto_assign_head": config.auto_assign_head,
        "auto_summon": config.auto_summon,
        "auto_escalate_overdue": config.auto_escalate_overdue,
        "notify_human_on_block": config.notify_human_on_block,
    }


@router.put("/settings")
def set_settings(req: BoardSettingsRequest) -> dict:
    """Update board settings."""
    config = load_config()
    if req.max_active_tasks is not None:
        config.max_active_tasks = req.max_active_tasks
    if req.auto_archive_days is not None:
        config.auto_archive_days = req.auto_archive_days
    if req.notifications_enabled is not None:
        config.notifications_enabled = req.notifications_enabled
    if req.auto_assign_head is not None:
        config.auto_assign_head = req.auto_assign_head
    if req.auto_summon is not None:
        config.auto_summon = req.auto_summon
    if req.auto_escalate_overdue is not None:
        config.auto_escalate_overdue = req.auto_escalate_overdue
    if req.notify_human_on_block is not None:
        config.notify_human_on_block = req.notify_human_on_block
    save_config(config)
    return {"status": "ok"}
