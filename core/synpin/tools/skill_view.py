"""skill_view — read a skill's full content or a reference file.

Available to ALL agents. The agent calls this when it needs the
full procedural text of a skill, not just the summary from the
system prompt.
"""
from __future__ import annotations

from ._registry import register_tool
from .base import ToolResult, make_success, make_error


@register_tool(
    name="skill_view",
    description=(
        "Прочитать содержимое скилла. "
        "Возвращает полный текст инструкции. "
        "Можно указать file_path для чтения конкретного reference-файла."
    ),
    category="knowledge",
    scope="all",
    dangerous=False,
)
async def skill_view(params: dict) -> ToolResult:
    from ..skills.manager import get_skill, get_skill_reference

    name = params.get("name", "").strip()
    if not name:
        return make_error("Параметр 'name' обязателен.")

    file_path = params.get("file_path", "").strip() or None

    # Read a specific reference file
    if file_path:
        content = get_skill_reference(name, file_path)
        if content is None:
            return make_error(
                f"Reference '{file_path}' не найден в скилле '{name}'."
            )
        return make_success(content)

    # Read the skill body
    skill = get_skill(name)
    if skill is None:
        return make_error(f"Скилл '{name}' не найден.")

    parts = [skill.body]
    if skill.references:
        parts.append("\n\n## Reference files\n")
        for ref in skill.references:
            parts.append(f"- {ref}")
    return make_success("\n".join(parts))
