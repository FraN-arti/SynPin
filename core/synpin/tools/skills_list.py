"""skills_list — list all available skills (metadata only).

Available to ALL agents. Returns name + description + category for
each skill. The system prompt already injects this list as text,
but the tool lets an agent re-fetch it programmatically.
"""
from __future__ import annotations

from ._registry import register_tool
from .base import ToolResult, make_success


@register_tool(
    name="skills_list",
    description="Получить список всех доступных скиллов (имя, описание, категория).",
    category="knowledge",
    scope="all",
    dangerous=False,
)
async def skills_list(params: dict) -> ToolResult:
    from ..skills.manager import list_skills

    items = list_skills()
    if not items:
        return make_success("Зарегистрированных скиллов нет.")

    lines = []
    for s in items:
        lines.append(f"**{s.name}** ({s.category})\n  {s.description}")
    return make_success("\n".join(lines))
