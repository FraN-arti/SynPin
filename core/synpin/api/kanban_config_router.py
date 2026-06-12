"""Kanban Config API — manage columns, labels, widget, and board settings.

All changes auto-save and broadcast via WebSocket for live sync.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..kanban.config import (
    ColumnConfig,
    LabelConfig,
    WidgetConfig,
    BoardSettings,
    generate_id,
    load_columns,
    save_columns,
    load_labels,
    save_labels,
    load_widget,
    save_widget,
    load_settings,
    save_settings,
)

router = APIRouter(prefix="/api/kanban/config", tags=["kanban-config"])


# ── Request models ───────────────────────────────────────────────────────────

class ColumnRequest(BaseModel):
    id: str | None = None         # Auto-generated if not provided
    label: str
    color: str = "#6b7280"
    order: int = 0
    enabled: bool = True


class LabelRequest(BaseModel):
    id: str | None = None         # Auto-generated if not provided
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


# ── Columns ──────────────────────────────────────────────────────────────────

@router.get("/columns")
def list_columns() -> list[dict]:
    """Get all columns."""
    return [c.model_dump() for c in load_columns()]


@router.put("/columns")
def set_columns(columns: list[ColumnRequest]) -> list[dict]:
    """Replace all columns."""
    cols = []
    for i, c in enumerate(columns):
        col_id = c.id or generate_id()
        cols.append(ColumnConfig(
            id=col_id,
            label=c.label,
            color=c.color,
            order=c.order if c.order != 0 else i,
            enabled=c.enabled,
        ))
    save_columns(cols)
    return [c.model_dump() for c in cols]


@router.post("/columns")
def add_column(col: ColumnRequest) -> dict:
    """Add a new column (auto-generates ID)."""
    cols = load_columns()
    col_id = col.id or generate_id()
    new_col = ColumnConfig(
        id=col_id,
        label=col.label,
        color=col.color,
        order=col.order if col.order != 0 else len(cols),
        enabled=col.enabled,
    )
    cols.append(new_col)
    save_columns(cols)
    return new_col.model_dump()


@router.delete("/columns/{column_id}")
def delete_column(column_id: str) -> dict:
    """Remove a column."""
    cols = load_columns()
    before = len(cols)
    cols = [c for c in cols if c.id != column_id]
    if len(cols) == before:
        raise HTTPException(404, f"Column '{column_id}' not found")
    save_columns(cols)
    return {"status": "ok", "deleted": column_id}


@router.patch("/columns/{column_id}")
def update_column(column_id: str, col: ColumnRequest) -> dict:
    """Update a single column (live sync)."""
    cols = load_columns()
    for i, c in enumerate(cols):
        if c.id == column_id:
            cols[i] = ColumnConfig(
                id=column_id,
                label=col.label if col.label else c.label,
                color=col.color if col.color != "#6b7280" else c.color,
                order=col.order if col.order != 0 else c.order,
                enabled=col.enabled,
            )
            save_columns(cols)
            return cols[i].model_dump()
    raise HTTPException(404, f"Column '{column_id}' not found")


# ── Labels ───────────────────────────────────────────────────────────────────

@router.get("/labels")
def list_labels() -> list[dict]:
    """Get all labels."""
    return [l.model_dump() for l in load_labels()]


@router.put("/labels")
def set_labels(labels: list[LabelRequest]) -> list[dict]:
    """Replace all labels."""
    lbls = []
    for l in labels:
        lbl_id = l.id or generate_id()
        lbls.append(LabelConfig(
            id=lbl_id,
            name=l.name,
            color=l.color,
            text_color=l.text_color,
        ))
    save_labels(lbls)
    return [l.model_dump() for l in lbls]


@router.post("/labels")
def add_label(label: LabelRequest) -> dict:
    """Add a new label (auto-generates ID)."""
    lbls = load_labels()
    lbl_id = label.id or generate_id()
    new_label = LabelConfig(
        id=lbl_id,
        name=label.name,
        color=label.color,
        text_color=label.text_color,
    )
    lbls.append(new_label)
    save_labels(lbls)
    return new_label.model_dump()


@router.delete("/labels/{label_id}")
def delete_label(label_id: str) -> dict:
    """Remove a label."""
    lbls = load_labels()
    before = len(lbls)
    lbls = [l for l in lbls if l.id != label_id]
    if len(lbls) == before:
        raise HTTPException(404, f"Label '{label_id}' not found")
    save_labels(lbls)
    return {"status": "ok", "deleted": label_id}


@router.patch("/labels/{label_id}")
def update_label(label_id: str, label: LabelRequest) -> dict:
    """Update a single label (live sync)."""
    lbls = load_labels()
    for i, l in enumerate(lbls):
        if l.id == label_id:
            lbls[i] = LabelConfig(
                id=label_id,
                name=label.name if label.name else l.name,
                color=label.color if label.color != "#6b7280" else l.color,
                text_color=label.text_color if label.text_color != "#ffffff" else l.text_color,
            )
            save_labels(lbls)
            return lbls[i].model_dump()
    raise HTTPException(404, f"Label '{label_id}' not found")


# ── Widget ───────────────────────────────────────────────────────────────────

@router.get("/widget")
def get_widget() -> dict:
    """Get widget configuration."""
    return load_widget().model_dump()


@router.put("/widget")
def set_widget(req: WidgetRequest) -> dict:
    """Update widget configuration."""
    widget = load_widget()
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
    save_widget(widget)
    return widget.model_dump()


# ── Board Settings ───────────────────────────────────────────────────────────

@router.get("/settings")
def get_settings() -> dict:
    """Get board settings."""
    return load_settings().model_dump()


@router.put("/settings")
def set_settings(req: BoardSettingsRequest) -> dict:
    """Update board settings."""
    settings = load_settings()
    if req.max_active_tasks is not None:
        settings.max_active_tasks = req.max_active_tasks
    if req.auto_archive_days is not None:
        settings.auto_archive_days = req.auto_archive_days
    if req.notifications_enabled is not None:
        settings.notifications_enabled = req.notifications_enabled
    if req.auto_assign_head is not None:
        settings.auto_assign_head = req.auto_assign_head
    if req.auto_summon is not None:
        settings.auto_summon = req.auto_summon
    if req.auto_escalate_overdue is not None:
        settings.auto_escalate_overdue = req.auto_escalate_overdue
    if req.notify_human_on_block is not None:
        settings.notify_human_on_block = req.notify_human_on_block
    save_settings(settings)
    return {"status": "ok"}
