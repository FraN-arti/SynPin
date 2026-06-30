"""skill_manage — create, update, or delete skills.

HEAD-ONLY: only the primary agent can use this tool. Prevents
chaotic skill creation by department agents.

Actions:
  create   — create a new skill from scratch
  patch    — find-and-replace inside an existing skill's body
  delete   — remove a skill entirely
"""
from __future__ import annotations

from ._registry import register_tool
from .base import ToolResult, make_success, make_error


@register_tool(
    name="skill_manage",
    description=(
        "Управление скиллами: создание, правка, удаление. "
        "Действие: action=create|patch|delete. "
        "create: name, description, content, [category]. "
        "patch: name, old_string, new_string, [replace_all]. "
        "delete: name."
    ),
    category="knowledge",
    scope="head",
    dangerous=True,
)
async def skill_manage(params: dict) -> ToolResult:
    from ..skills.manager import (
        create_skill,
        patch_skill,
        delete_skill,
        get_skill,
    )

    action = params.get("action", "").strip().lower()
    name = params.get("name", "").strip()

    if not action:
        return make_error("Параметр 'action' обязателен (create|patch|delete).")
    if not name and action != "list":
        return make_error("Параметр 'name' обязателен.")

    if action == "create":
        description = params.get("description", "").strip()
        content = params.get("content", "").strip()
        category = params.get("category", "general").strip() or "general"
        if not description:
            return make_error("create: параметр 'description' обязателен.")
        if not content:
            return make_error("create: параметр 'content' обязателен.")
        if get_skill(name) is not None:
            return make_error(f"Скилл '{name}' уже существует.")
        skill = create_skill(
            name=name,
            description=description,
            content=content,
            category=category,
        )
        return make_success(
            f"Скилл '{skill.name}' создан. "
            f"Файл: {skill.path / 'SKILL.md'}"
        )

    if action == "patch":
        old_string = params.get("old_string", "")
        new_string = params.get("new_string", "")
        replace_all = params.get("replace_all", False)
        if not old_string:
            return make_error("patch: параметр 'old_string' обязателен.")
        try:
            skill = patch_skill(name, old_string, new_string, replace_all=bool(replace_all))
        except FileNotFoundError as e:
            return make_error(str(e))
        except ValueError as e:
            return make_error(str(e))
        return make_success(f"Скилл '{skill.name}' обновлён.")

    if action == "delete":
        deleted = delete_skill(name)
        if not deleted:
            return make_error(f"Скилл '{name}' не найден.")
        return make_success(f"Скилл '{name}' удалён.")

    return make_error(f"Неизвестное действие: '{action}'. Используй create|patch|delete.")
