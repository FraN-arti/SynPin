"""Kanban configuration — columns, labels, and widget settings.

Structured storage: each section in its own YAML file under config/.
Hot-reloaded via ConfigWatcher. WebSocket broadcast on every change.
"""
from __future__ import annotations

import logging
import os
import random
import string
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

from ..paths import get_config_dir as _main_config_dir
from .models import TaskStatus


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
    description: str = ""         # Purpose description (for agent prompts)
    color: str = "#6b7280"       # Color for the indicator square
    order: int = 0               # Sort order on the board
    enabled: bool = True         # Show/hide this column
    status: str | None = None     # Maps to TaskStatus enum (backlog, todo, in_progress, etc.)


class LabelConfig(BaseModel):
    """A tag/label that can be assigned to tasks."""
    id: str                       # 14-char alphanumeric
    name: str                     # Display name: #System, #Service
    color: str = "#6b7280"       # Background color
    text_color: str = "#ffffff"  # Text color
    description: str = ""         # Purpose description (for agent prompts)


class WidgetConfig(BaseModel):
    """Settings for the Kanban widget on the dashboard."""
    mode: str = "active"          # active | all | my | blocked
    max_items: int = 5            # Max items to show
    show_columns: list[str] = Field(default_factory=lambda: ["in_progress", "review", "blocked"])
    default_column: str | None = None
    show_deadline: bool = True
    show_department: bool = True
    compact: bool = True          # Compact vs detailed view


class BoardSettings(BaseModel):
    """Board settings and automation."""
    max_active_tasks: int = 50
    # auto_archive_days: tasks in DONE status older than this are
    # auto-deleted. 0 disables. Default 30 days.
    auto_archive_days: int = 30
    notifications_enabled: bool = True
    auto_assign_head: bool = True
    auto_summon: bool = False
    auto_escalate_overdue: bool = False
    notify_human_on_block: bool = False
    # List of column IDs whose tasks should be auto-deleted when
    # their last update is older than auto_archive_days. Empty
    # means no auto-deletion. The default is the standard 'done'
    # column; the user can configure any column(s).
    auto_delete_from_columns: list[str] = Field(default_factory=list)
    # Column ID to move tasks to when archiving (instead of file move).
    # If empty, archive moves the YAML file to tasks/archive/.
    archive_column: str | None = None
    # Column ID to move tasks to when head_block is called.
    # If empty, blocked tasks stay in their current column with blocked status.
    blocked_column: str | None = None
    # Custom colors for deadline categories on the deadlines page
    deadline_colors: dict[str, str] | None = None


# ── Defaults ─────────────────────────────────────────────────────────────────

def _default_columns() -> list[ColumnConfig]:
    """Seed defaults: 8 columns matching the standard SynPin kanban layout.

    These are used when no columns.yaml exists yet (fresh install).
    Each column maps to a TaskStatus enum value so the backend can
    correctly group tasks by status.
    """
    return [
        ColumnConfig(
            id=generate_id(), label="Бэклог", status="backlog",
            color="#9ca3af", order=0,
            description="Идеи и заявки, которые ещё не прошли приоритизацию. Не обещаем сроки.",
        ),
        ColumnConfig(
            id=generate_id(), label="К работе", status="todo",
            color="#60a5fa", order=1,
            description="Одобренные задачи, готовые к взятию в работу. Назначен исполнитель, понятен первый шаг.",
        ),
        ColumnConfig(
            id=generate_id(), label="В работе", status="in_progress",
            color="#fb923c", order=2,
            description="Активная работа одного агента. Не больше 1-2 задач на отдел одновременно.",
        ),
        ColumnConfig(
            id=generate_id(), label="На проверке", status="review",
            color="#fbbf24", order=3,
            description="Результат готов, ждёт проверки главы отдела или заказчика. Ожидаемое время ревью — 1-2 дня.",
        ),
        ColumnConfig(
            id=generate_id(), label="Доработка", status="revision",
            color="#f472b6", order=4,
            description="Проверяющий вернул на доработку. Конкретные правки в комментариях.",
        ),
        ColumnConfig(
            id=generate_id(), label="Заблокировано", status="blocked",
            color="#f87171", order=5,
            description="Работа остановлена внешней причиной. Укажи блокер в комментариях.",
        ),
        ColumnConfig(
            id=generate_id(), label="Готово", status="done",
            color="#22c55e", order=6,
            description="Завершено и принято.",
        ),
        ColumnConfig(
            id=generate_id(), label="В архиве", status="archived",
            color="#6b7280", order=7,
            description="Устаревшие выполненные задачи. Скрыты с доски по умолчанию.",
        ),
    ]


DEFAULT_AUTO_TRANSITIONS: dict[str, str] = {
    # When kanban transitions happen automatically (cron watchers,
    # head tools, manual moves), map to the column this status
    # belongs to.
    "backlog": "Бэклог",
    "todo": "К работе",
    "in_progress": "В работе",
    "review": "На проверке",
    "revision": "Доработка",
    "blocked": "Заблокировано",
    "done": "Готово",
    "archived": "В архиве",
}


def _default_labels() -> list[LabelConfig]:
    """Seed defaults: standard label set for SynPin kanban tasks."""
    return [
        LabelConfig(
            id=generate_id(), name="#Service",
            color="#166534", text_color="#bbf7d0",
            description="Сервисные задачи: деплой, настройка, обслуживание инфраструктуры",
        ),
        LabelConfig(
            id=generate_id(), name="#Bug",
            color="#7f1d1d", text_color="#fca5a5",
            description="Ошибки и баги в коде, требующие исправления",
        ),
        LabelConfig(
            id=generate_id(), name="#Feature",
            color="#4c1d95", text_color="#c4b5fd",
            description="Новые функции и возможности платформы",
        ),
        LabelConfig(
            id=generate_id(), name="#Urgent",
            color="#78350f", text_color="#fcd34d",
            description="Срочные задачи, требующие немедленного внимания",
        ),
    ]


# ── Config directory ─────────────────────────────────────────────────────────


def _get_config_dir() -> Path:
    """Resolve kanban config directory.

    Kanban uses its own subdirectory (`kanban/`) under the main config
    dir so kanban configs don't pollute the top-level config. In dev
    mode it sits at core/synpin/kanban/config/ to keep the project's
    kanban config in version control; in prod it's ~/.synpin/config/kanban/.
    """
    prod = _main_config_dir() / "kanban"
    dev = Path(__file__).resolve().parent / "config"

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

def _broadcast_config(event_type: str, data: dict) -> None:
    """Broadcast config change to all connected clients."""
    from ..ws_broadcast import broadcast
    broadcast({"type": event_type, **data})


# ── File I/O ─────────────────────────────────────────────────────────────────

def _load_yaml(name: str) -> dict | list | None:
    """Load a YAML file."""
    path = _yaml_path(name)
    if path.exists():
        try:
            return yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning("[kanban] Config load error (%s): %s", name, e)
    return None


def _save_yaml(name: str, data) -> None:
    """Save data to a YAML file."""
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
        cols = [ColumnConfig(**c) for c in data]
        return cols
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
    """Load widget config.

    On load we also run a one-shot migration of the legacy
    show_columns format. The original schema stored TaskStatus
    strings here ('in_progress', 'review', 'blocked'), but
    user-added columns have arbitrary status values that don't
    match any TaskStatus enum entry — so the widget silently
    failed to render them. We now store column.id instead and
    map status -> id at load time, transparently upgrading any
    existing widget.yaml in the user's repo. After migration
    the file is rewritten so subsequent loads are no-ops.
    """
    data = _load_yaml("widget")
    if data and isinstance(data, dict):
        widget = WidgetConfig(**data)
        # Migration: if show_columns entries look like TaskStatus
        # values (rather than column ids), remap them to the
        # matching column id. We detect legacy entries by
        # checking whether any of them matches a known column
        # status — if NO match at all, treat them all as ids
        # (already-migrated); if SOME match, all are status
        # strings (legacy). Mixed-state we leave alone since
        # the lookup is best-effort.
        if widget.show_columns:
            cols = load_columns()
            by_status = {c.status: c.id for c in cols if c.status}
            known_statuses = set(by_status.keys())
            legacy_entries = [s for s in widget.show_columns if s in known_statuses]
            if legacy_entries:
                # Whole list (or most of it) looks like legacy
                # TaskStatus values — translate to column ids.
                new_show = [by_status.get(s, s) for s in widget.show_columns]
                if new_show != widget.show_columns:
                    widget.show_columns = new_show
                    save_widget(widget)
        return widget
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
