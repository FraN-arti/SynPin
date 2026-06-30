"""SynPin skills — procedural knowledge library for AI agents."""
from .manager import (
    Skill,
    SkillMeta,
    list_skills,
    get_skill,
    get_skill_reference,
    create_skill,
    patch_skill,
    delete_skill,
    invalidate_cache,
)

__all__ = [
    "Skill",
    "SkillMeta",
    "list_skills",
    "get_skill",
    "get_skill_reference",
    "create_skill",
    "patch_skill",
    "delete_skill",
    "invalidate_cache",
]
