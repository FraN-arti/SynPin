"""memory_write — write to agent's own memory (MEMORY.md or USER.md).

Built-in tool: always enabled, not shown in agent UI.
Auto-compacts when memory exceeds char limit.
"""
import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger("synpin.memory")

# Character limits
MEMORY_CHAR_LIMIT = 3000
USER_CHAR_LIMIT = 1375

DELIM = "\n§\n"

from ..paths import get_data_dir as _get_data_dir


def _read_entries(path: Path) -> list[str]:
    """Read MEMORY.md/USER.md into a list of entries (separated by §)."""
    if not path.exists():
        return []
    content = path.read_text(encoding="utf-8").strip()
    if not content:
        return []
    return [e.strip() for e in content.split(DELIM) if e.strip()]


def _write_entries(path: Path, entries: list[str]) -> None:
    """Write entries list back to file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    content = DELIM.join(entries) + "\n" if entries else ""
    fd, tmp_path = tempfile.mkstemp(
        dir=str(path.parent), suffix=".tmp", prefix=".memory_"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, str(path))
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _entries_total(entries: list[str]) -> int:
    """Calculate total char count of entries as stored."""
    return len(DELIM.join(entries)) if entries else 0


def _parse_key(entry: str) -> str:
    """Extract key from 'Key: Value' entry, or return '' for free-form."""
    m = re.match(r"^([^:—\-]+)\s*[:—\-]\s*", entry)
    return m.group(1).strip() if m else ""


def _auto_compact(entries: list[str], limit: int) -> list[str]:
    """Auto-compact entries to fit within char limit.

    Strategy (in order):
    1. Remove exact duplicates
    2. Deduplicate by key (keep last occurrence — most up-to-date)
    3. If still over limit, remove oldest entries until it fits
    """
    original_count = len(entries)

    # Step 1: Remove exact duplicates (preserving order, keeping first)
    seen_exact: set[str] = set()
    deduped: list[str] = []
    for e in entries:
        if e not in seen_exact:
            seen_exact.add(e)
            deduped.append(e)
    entries = deduped

    # Step 2: Deduplicate by key (keep last — most recent)
    key_map: dict[int, str] = {}
    for i, e in enumerate(entries):
        k = _parse_key(e)
        if k:
            key_map[i] = k

    if key_map:
        last_seen: dict[str, int] = {}
        for i, k in key_map.items():
            last_seen[k] = i

        deduped_by_key: list[str] = []
        for i, e in enumerate(entries):
            k = key_map.get(i, "")
            if not k or last_seen.get(k) == i:
                deduped_by_key.append(e)
        entries = deduped_by_key

    # Check if we fit now
    if _entries_total(entries) <= limit:
        return entries

    # Step 3: Remove oldest entries (from the beginning) until it fits
    while len(entries) > 1:
        remaining = entries[1:]
        if _entries_total(remaining) <= limit:
            entries = remaining
            break
        entries = remaining
    else:
        # Single entry still over limit — truncate it
        if entries:
            entries = [entries[0][:limit]]

    removed = original_count - len(entries)
    if removed > 0:
        logger.info(
            "Auto-compacted: %d → %d entries (%d chars)",
            original_count, len(entries), _entries_total(entries),
        )

    return entries


async def _summarize_entries(entries: list[str], target_chars: int) -> list[str]:
    """Summarize memory entries using LLM to fit within target char limit.

    Uses the configured summarization model, or falls back to simple compaction.
    """
    try:
        from .summarize import summarize_for_compaction
        # Convert entries to a single text block
        text = "\n".join(entries)
        summary = await summarize_for_compaction([{"role": "user", "content": text}])
        if summary and len(summary) <= target_chars:
            return [summary]
    except Exception as e:
        logger.warning("[memory] LLM summarization failed: %s", e)

    # Fallback to simple compaction
    return _auto_compact(entries, target_chars)


async def memory_write(params: dict[str, Any]) -> dict[str, Any]:
    """Write to agent memory.

    Params:
        action (str): "add", "remove", "replace".
        target (str): "memory" for MEMORY.md, "user" for USER.md.
        agent_id (str): Agent slug/id.
        content (str): New entry text (for add/replace).
        old_text (str): Text to find and replace/remove.
    """
    action = params.get("action", "add")
    target = params.get("target", "memory")
    agent_id = params.get("agent_id", "")
    content = params.get("content", "")
    old_text = params.get("old_text", "")

    if not agent_id:
        return {"success": False, "output": "", "error": "agent_id is required"}

    data_dir = _get_data_dir()
    agent_dir = data_dir / "agents" / agent_id
    agent_dir.mkdir(parents=True, exist_ok=True)

    if target == "memory":
        path = agent_dir / "MEMORY.md"
    elif target == "user":
        path = data_dir / "shared" / "USER.md"
        path.parent.mkdir(parents=True, exist_ok=True)
    else:
        return {"success": False, "output": "", "error": f"Unknown target: {target}"}

    entries = _read_entries(path)
    limit = USER_CHAR_LIMIT if target == "user" else MEMORY_CHAR_LIMIT

    if action == "add":
        if not content.strip():
            return {"success": False, "output": "", "error": "content is required for add"}

        # Check if adding would exceed limit
        test_entries = entries + [content.strip()]
        test_total = _entries_total(test_entries)
        compacted = False

        if test_total > limit:
            # Auto-compact existing entries first (LLM summarize if available)
            before_count = len(entries)
            entries = await _summarize_entries(entries, limit)
            compacted = len(entries) < before_count

            # Check again after compaction
            test_entries = entries + [content.strip()]
            test_total = _entries_total(test_entries)

            if test_total > limit:
                # Still over limit — truncate new entry
                current_chars = _entries_total(entries)
                max_new = limit - current_chars - 2
                if max_new < 50:
                    return {
                        "success": False,
                        "output": "",
                        "error": (
                            f"Memory at {current_chars:,}/{limit:,} chars. "
                            f"Even after compaction, no room for new entry. "
                            f"Remove entries first with memory_write(action='remove')."
                        ),
                    }
                content = content.strip()[:max_new] + "... [обрезано]"

        # Reject exact duplicates
        if content.strip() in entries:
            return {"success": True, "output": "Entry already exists (no duplicate added).", "error": None}

        entries.append(content.strip())
        _write_entries(path, entries)

        written = path.read_text(encoding="utf-8")
        notice = " [Компакция: удалены дубли]" if compacted else ""

        return {
            "success": True,
            "output": f"Added. Total entries: {len(entries)}{notice}",
            "warning": f"Memory ({len(written):,} chars) exceeds limit ({limit:,} chars)." if len(written) > limit else None,
            "error": None,
        }

    elif action == "remove":
        if not old_text.strip():
            return {"success": False, "output": "", "error": "old_text is required for remove"}
        new_entries = [e for e in entries if old_text.strip() not in e]
        if len(new_entries) == len(entries):
            return {"success": False, "output": f"Not found: {old_text[:50]}", "error": None}
        _write_entries(path, new_entries)
        return {"success": True, "output": f"Removed. Total entries: {len(new_entries)}", "error": None}

    elif action == "replace":
        if not old_text.strip():
            return {"success": False, "output": "", "error": "old_text is required for replace"}
        if not content.strip():
            return {"success": False, "output": "", "error": "content is required for replace"}
        found = False
        new_entries = []
        for e in entries:
            if old_text.strip() in e and not found:
                new_entries.append(content.strip())
                found = True
            else:
                new_entries.append(e)
        if not found:
            return {"success": False, "output": f"Not found: {old_text[:50]}", "error": None}

        # Check if replacement would exceed limit
        test_total = _entries_total(new_entries)
        if test_total > limit:
            return {
                "success": False,
                "error": (
                    f"Replacement would put memory at {test_total:,}/{limit:,} chars. "
                    f"Shorten the new content or remove other entries first."
                ),
            }

        _write_entries(path, new_entries)
        return {"success": True, "output": f"Replaced. Total entries: {len(new_entries)}", "error": None}

    return {"success": False, "output": "", "error": f"Unknown action: {action}"}
