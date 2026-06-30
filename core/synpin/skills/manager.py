"""Skill manager for SynPin — discovers, parses, and caches skills.

Skills live as ``data/skills/<name>/SKILL.md`` files with YAML
frontmatter.  The frontmatter carries metadata (name, description,
category, triggers); the body is the procedural instruction text
the agent reads on demand via ``skill_view``.

Public API:
    list_skills() -> list[SkillMeta]
    get_skill(name) -> Skill | None
    create_skill(name, description, content, category=...) -> Skill
    patch_skill(name, old_string, new_string) -> Skill
    delete_skill(name) -> bool
    invalidate_cache() -> None

Cache is invalidated on every write operation.  Read operations
re-scan the filesystem only when the cache is cold or invalidated.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ..paths import get_data_dir

# ── data models ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class SkillMeta:
    """Lightweight metadata used for the system-prompt injection list."""

    name: str
    description: str
    category: str


@dataclass
class Skill:
    """Full skill — metadata + body text + reference files."""

    name: str
    description: str
    category: str
    body: str  # markdown body (without frontmatter)
    references: list[str] = field(default_factory=list)  # relative paths
    path: Path = field(default_factory=Path)


# ── frontmatter parser ───────────────────────────────────────────────

_FM_RE = re.compile(
    r"\A---\s*\n(?P<fm>.*?)\n---\s*\n?(?P<body>.*)\Z",
    re.DOTALL,
)


def _parse_skill_md(text: str) -> tuple[dict[str, Any], str]:
    """Split a SKILL.md into (frontmatter dict, body markdown).

    Returns ({}, full_text) if no frontmatter is present.
    """
    m = _FM_RE.match(text)
    if not m:
        return {}, text
    try:
        meta = yaml.safe_load(m.group("fm")) or {}
    except yaml.YAMLError:
        meta = {}
    body = m.group("body").strip()
    return meta, body


# ── path helpers ─────────────────────────────────────────────────────


def _skills_root() -> Path:
    """Return ``data/skills`` directory (creating on first write)."""
    return get_data_dir() / "skills"


# ── manager ──────────────────────────────────────────────────────────

_cache: list[Skill] | None = None


def invalidate_cache() -> None:
    """Force re-scan on next read."""
    global _cache
    _cache = None


def _scan() -> list[Skill]:
    """Scan ``data/skills/*/SKILL.md`` and build the cache."""
    root = _skills_root()
    if not root.exists():
        return []
    skills: list[Skill] = []
    for skill_dir in sorted(root.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue
        try:
            raw = skill_md.read_text(encoding="utf-8")
        except OSError:
            continue
        meta, body = _parse_skill_md(raw)
        name = meta.get("name", skill_dir.name)
        # Collect reference files (non-SKILL.md inside the skill dir)
        refs: list[str] = []
        for child in sorted(skill_dir.rglob("*")):
            if child.is_file() and child.name != "SKILL.md":
                refs.append(str(child.relative_to(skill_dir)).replace("\\", "/"))
        skills.append(
            Skill(
                name=name,
                description=meta.get("description", ""),
                category=meta.get("category", "general"),
                body=body,
                references=refs,
                path=skill_dir,
            )
        )
    return skills


def _ensure_cache() -> list[Skill]:
    global _cache
    if _cache is None:
        _cache = _scan()
    return _cache


# ── public read API ──────────────────────────────────────────────────


def list_skills() -> list[SkillMeta]:
    """Return lightweight metadata for every skill (system-prompt injection)."""
    return [
        SkillMeta(name=s.name, description=s.description, category=s.category)
        for s in _ensure_cache()
    ]


def get_skill(name: str) -> Skill | None:
    """Return the full skill (body + references) or None."""
    for s in _ensure_cache():
        if s.name == name:
            return s
    return None


def get_skill_reference(name: str, file_path: str) -> str | None:
    """Read a reference file inside a skill directory. Returns None if missing."""
    skill = get_skill(name)
    if skill is None:
        return None
    ref_path = skill.path / file_path
    # Security: resolved path must stay inside the skill directory
    try:
        ref_path.resolve().relative_to(skill.path.resolve())
    except ValueError:
        return None
    if not ref_path.is_file():
        return None
    try:
        return ref_path.read_text(encoding="utf-8")
    except OSError:
        return None


# ── public write API (head-only tools) ───────────────────────────────


def create_skill(
    *,
    name: str,
    description: str,
    content: str,
    category: str = "general",
) -> Skill:
    """Create ``data/skills/<name>/SKILL.md`` with frontmatter + body."""
    root = _skills_root()
    root.mkdir(parents=True, exist_ok=True)
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_md = skill_dir / "SKILL.md"
    fm = {
        "name": name,
        "description": description,
        "category": category,
    }
    frontmatter = yaml.safe_dump(fm, allow_unicode=True, sort_keys=False).strip()
    full = f"---\n{frontmatter}\n---\n\n{content}\n"
    skill_md.write_text(full, encoding="utf-8")
    invalidate_cache()
    # Return freshly scanned skill
    result = get_skill(name)
    assert result is not None  # just created — must exist
    return result


def patch_skill(name: str, old_string: str, new_string: str, replace_all: bool = False) -> Skill:
    """Find-and-replace inside a skill's SKILL.md body."""
    skill = get_skill(name)
    if skill is None:
        raise FileNotFoundError(f"Skill '{name}' not found")
    skill_md = skill.path / "SKILL.md"
    raw = skill_md.read_text(encoding="utf-8")
    count = raw.count(old_string) if not replace_all else raw.count(old_string)
    if count == 0:
        raise ValueError(f"old_string not found in skill '{name}'")
    if not replace_all and count > 1:
        raise ValueError(
            f"old_string appears {count} times in skill '{name}'; "
            "pass replace_all=true"
        )
    if replace_all:
        raw = raw.replace(old_string, new_string)
    else:
        raw = raw.replace(old_string, new_string, 1)
    skill_md.write_text(raw, encoding="utf-8")
    invalidate_cache()
    result = get_skill(name)
    assert result is not None
    return result


def delete_skill(name: str) -> bool:
    """Delete an entire skill directory. Returns True if something was deleted."""
    skill = get_skill(name)
    if skill is None:
        return False
    import shutil

    shutil.rmtree(skill.path, ignore_errors=True)
    invalidate_cache()
    return True
