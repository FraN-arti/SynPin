"""Kanban Config API — manage columns, labels, widget, and board settings.

All changes auto-save and broadcast via WebSocket for live sync.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import Field
from ._base import BaseRequest
from ..kanban.models import TaskStatus

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

class ColumnRequest(BaseRequest):
    id: str | None = None         # Auto-generated if not provided
    label: str = ""
    description: str = ""
    color: str = "#6b7280"
    order: int = 0
    enabled: bool = True
    status: str | None = None


class ColumnPatchRequest(BaseRequest):
    """Partial update — all fields optional. Includes `status` so
    users can map a column to one of the TaskStatus enum values
    from the Settings UI (otherwise you'd have to edit columns.yaml
    by hand, which is awkward). We validate the string against the
    enum server-side; passing an invalid value returns 400 with a
    helpful list of allowed values.
    """
    label: str | None = None
    description: str | None = None
    color: str | None = None
    order: int | None = None
    enabled: bool | None = None
    status: str | None = None  # Must be a TaskStatus value or None


class LabelRequest(BaseRequest):
    id: str | None = None         # Auto-generated if not provided
    name: str = ""
    color: str = "#6b7280"
    text_color: str = "#ffffff"
    description: str = ""


class LabelPatchRequest(BaseRequest):
    """Partial update — all fields optional."""
    name: str | None = None
    color: str | None = None
    text_color: str | None = None
    description: str | None = None


class WidgetRequest(BaseRequest):
    mode: str | None = None
    max_items: int | None = None
    show_columns: list[str] | None = None
    default_column: str | None = None
    show_deadline: bool | None = None
    show_department: bool | None = None
    compact: bool | None = None


class BoardSettingsRequest(BaseRequest):
    max_active_tasks: int | None = None
    auto_archive_days: int | None = None
    notifications_enabled: bool | None = None
    auto_assign_head: bool | None = None
    auto_summon: bool | None = None
    auto_escalate_overdue: bool | None = None
    notify_human_on_block: bool | None = None
    auto_delete_from_columns: list[str] | None = None
    archive_column: str | None = None
    blocked_column: str | None = None
    deadline_colors: dict[str, str] | None = None


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
            description=c.description or '',
            color=c.color,
            order=c.order if c.order != 0 else i,
            enabled=c.enabled,
            status=c.status,
        ))
    save_columns(cols)
    return [c.model_dump() for c in cols]


@router.post("/columns")
def add_column(col: ColumnRequest) -> dict:
    """Add a new column (auto-generates ID)."""
    cols = load_columns()
    col_id = col.id or generate_id()

    # Auto-assign TaskStatus if not provided.
    # When a user creates a column via the UI, they don't set a status —
    # but the board API groups tasks by TaskStatus enum, so every column
    # MUST have one to display tasks. We pick the first unused status.
    status = col.status
    if not status:
        used = {c.status for c in cols if c.status}
        for ts in TaskStatus:
            if ts.value not in used:
                status = ts.value
                break
        if not status:
            status = TaskStatus.BACKLOG.value

    new_col = ColumnConfig(
        id=col_id,
        label=col.label,
        description=col.description,
        color=col.color,
        order=col.order if col.order != 0 else len(cols),
        enabled=col.enabled,
        status=status,
    )
    cols.append(new_col)
    save_columns(cols)
    return new_col.model_dump()


@router.delete("/columns/{column_id}")
def delete_column(column_id: str) -> dict:
    """Remove a column AND clean up all references.

    Clean delete concept:
    1. Remove from columns.yaml
    2. Remove from widget.yaml → show_columns
    3. Move tasks with that status → backlog (first enabled column)
    """
    cols = load_columns()
    before = len(cols)
    cols = [c for c in cols if c.id != column_id]
    if len(cols) == before:
        raise HTTPException(404, f"Column '{column_id}' not found")
    save_columns(cols)

    # Clean widget references
    widget = load_widget()
    if column_id in widget.show_columns:
        widget.show_columns.remove(column_id)
    if widget.default_column == column_id:
        widget.default_column = None
    save_widget(widget)

    # Clean task references — move orphans to first enabled column
    try:
        from .models import load_all_tasks, save_task, TaskStatus
        from .service import KanbanService
        tasks = load_all_tasks()
        first_col = cols[0] if cols else None
        if first_col and tasks:
            for task in tasks:
                if task.status.value == column_id:
                    # Find a valid status to move to
                    try:
                        new_status = TaskStatus(first_col.id)
                    except ValueError:
                        new_status = TaskStatus.BACKLOG
                    task.status = new_status
                    save_task(task)
    except Exception:
        pass  # Tasks may not exist yet

    return {"status": "ok", "deleted": column_id}


@router.patch("/columns/{column_id}")
def update_column(column_id: str, col: ColumnPatchRequest) -> dict:
    """Update a single column (live sync)."""
    cols = load_columns()
    for i, c in enumerate(cols):
        if c.id == column_id:
            if col.label is not None:
                c.label = col.label
            if col.description is not None:
                c.description = col.description
            if col.color is not None:
                c.color = col.color
            if col.order is not None:
                c.order = col.order
            if col.enabled is not None:
                c.enabled = col.enabled
            if "status" in col.model_fields_set:
                # User explicitly set status. If it's a string, it
                # MUST be a valid TaskStatus enum value; if not, we
                # 400 with the list of allowed values so the user
                # can fix the form, not silently misroute their
                # tasks to /todo.
                from synpin.kanban.models import TaskStatus
                valid = {s.value for s in TaskStatus}
                if col.status is not None and col.status not in valid:
                    raise HTTPException(
                        400,
                        f"Invalid column status '{col.status}'. "
                        f"Allowed: {sorted(valid)} or null to clear.",
                    )
                c.status = col.status
            save_columns(cols)
            return c.model_dump()
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
            description=l.description,
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
        description=label.description,
    )
    lbls.append(new_label)
    save_labels(lbls)
    return new_label.model_dump()


@router.delete("/labels/{label_id}")
def delete_label(label_id: str) -> dict:
    """Remove a label AND clean up all references.

    Clean delete concept:
    1. Remove from labels.yaml
    2. Remove tag from all tasks that reference it
    """
    lbls = load_labels()
    before = len(lbls)
    deleted_label = None
    new_lbls = []
    for l in lbls:
        if l.id == label_id:
            deleted_label = l
        else:
            new_lbls.append(l)
    if deleted_label is None:
        raise HTTPException(404, f"Label '{label_id}' not found")
    save_labels(new_lbls)

    # Clean task references — remove tag from tasks
    try:
        from .models import load_all_tasks, save_task
        tasks = load_all_tasks()
        if tasks and deleted_label:
            tag_name = deleted_label.name.lstrip('#')
            for task in tasks:
                if tag_name in task.tags:
                    task.tags.remove(tag_name)
                    save_task(task)
    except Exception:
        pass  # Tasks may not exist yet

    return {"status": "ok", "deleted": label_id}


@router.patch("/labels/{label_id}")
def update_label(label_id: str, label: LabelPatchRequest) -> dict:
    """Update a single label (live sync)."""
    lbls = load_labels()
    for l in lbls:
        if l.id == label_id:
            if label.name is not None:
                l.name = label.name
            if label.color is not None:
                l.color = label.color
            if label.text_color is not None:
                l.text_color = label.text_color
            if label.description is not None:
                l.description = label.description
            save_labels(lbls)
            return l.model_dump()
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
    if req.default_column is not None:
        widget.default_column = req.default_column
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
    if req.auto_delete_from_columns is not None:
        # Validate: every entry must be a real column id, otherwise
        # we'd be auto-deleting from a column that doesn't exist.
        # This is a soft validation — we don't 400 on unknown ids,
        # we just filter them out and log a warning.
        cols = load_columns()
        valid_ids = {c.id for c in cols}
        filtered = [c for c in req.auto_delete_from_columns if c in valid_ids]
        if len(filtered) != len(req.auto_delete_from_columns):
            import logging
            logging.getLogger("synpin.kanban").warning(
                "[auto-delete] filtered out unknown column ids: %s",
                set(req.auto_delete_from_columns) - valid_ids,
            )
        settings.auto_delete_from_columns = filtered
    if req.notify_human_on_block is not None:
        settings.notify_human_on_block = req.notify_human_on_block
    if req.archive_column is not None:
        # Validate: must be a real column id or empty string to clear
        if req.archive_column == "":
            settings.archive_column = None
        else:
            cols = load_columns()
            valid_ids = {c.id for c in cols}
            if req.archive_column not in valid_ids:
                raise HTTPException(400, f"Unknown column id: {req.archive_column}")
            settings.archive_column = req.archive_column
    if req.blocked_column is not None:
        if req.blocked_column == "":
            settings.blocked_column = None
        else:
            cols = load_columns()
            valid_ids = {c.id for c in cols}
            if req.blocked_column not in valid_ids:
                raise HTTPException(400, f"Unknown column id: {req.blocked_column}")
            settings.blocked_column = req.blocked_column
    if req.deadline_colors is not None:
        settings.deadline_colors = req.deadline_colors if req.deadline_colors else None
    save_settings(settings)
    return {"status": "ok"}
