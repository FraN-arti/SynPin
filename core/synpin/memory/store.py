"""MemoryStore — bounded curated memory with file persistence.

Two stores per agent:
  - MEMORY.md: agent's personal notes (patterns, conventions, anti-patterns)
  - USER.md: what the agent knows about the user

Plus dated facts:
  - facts/YYYY-MM-DD_topic.md: specific situational decisions with timestamps

Design inspired by Hermes memory_tool.py:
- Entry delimiter: § (section sign)
- Char limits (not tokens) — model-independent
- File locking for concurrent access
- Atomic writes via temp file + rename
"""

import json
import logging
import os
import re
import tempfile
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

ENTRY_DELIMITER = "\n§\n"

# Character limits
MEMORY_CHAR_LIMIT = 2200
USER_CHAR_LIMIT = 1375


class MemoryStore:
    """Bounded curated memory with file persistence. One instance per agent.

    Maintains two parallel states:
      - _system_prompt_snapshot: frozen at load time, used for system prompt injection.
        Never mutated mid-session. Keeps prefix cache stable.
      - memory_entries / user_entries: live state, mutated by tool calls, persisted to disk.
        Tool responses always reflect this live state.
    """

    def __init__(
        self,
        agent_id: str,
        data_dir: Path,
        memory_char_limit: int = MEMORY_CHAR_LIMIT,
        user_char_limit: int = USER_CHAR_LIMIT,
    ):
        self.agent_id = agent_id
        self.data_dir = Path(data_dir)
        self.memory_dir = self.data_dir / "agents" / agent_id
        self.facts_dir = self.memory_dir / "facts"

        self.memory_char_limit = memory_char_limit
        self.user_char_limit = user_char_limit

        self.memory_entries: List[str] = []
        self.user_entries: List[str] = []

        # Frozen snapshot for system prompt — set once at load_from_disk()
        self._system_prompt_snapshot: Dict[str, str] = {"memory": "", "user": ""}

        # Ensure directories exist
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.facts_dir.mkdir(parents=True, exist_ok=True)

    # ── Load / Save ──────────────────────────────────────────────────────

    def load_from_disk(self):
        """Load entries from MEMORY.md and USER.md, capture system prompt snapshot."""
        self.memory_entries = self._read_file(self.memory_dir / "MEMORY.md")
        self.user_entries = self._read_file(self.data_dir / "shared" / "USER.md")

        # Deduplicate entries (preserves order, keeps first occurrence)
        self.memory_entries = list(dict.fromkeys(self.memory_entries))
        self.user_entries = list(dict.fromkeys(self.user_entries))

        # Capture frozen snapshot for system prompt injection
        self._system_prompt_snapshot = {
            "memory": self._render_block("memory", self.memory_entries),
            "user": self._render_block("user", self.user_entries),
        }

        logger.info(
            "Memory loaded for %s: %d memory entries, %d user entries",
            self.agent_id,
            len(self.memory_entries),
            len(self.user_entries),
        )

    def save_to_disk(self, target: str):
        """Persist entries to the appropriate file. Called after every mutation."""
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self._write_file(self._path_for(target), self._entries_for(target))

    # ── CRUD Operations ──────────────────────────────────────────────────

    def add(self, target: str, content: str) -> Dict[str, Any]:
        """Append a new entry. Returns error if it would exceed the char limit."""
        content = content.strip()
        if not content:
            return {"success": False, "error": "Content cannot be empty."}

        with self._file_lock(self._path_for(target)):
            # Re-read from disk under lock to pick up writes from other sessions
            self._reload_target(target)

            entries = self._entries_for(target)
            limit = self._char_limit(target)

            # Reject exact duplicates
            if content in entries:
                return self._success_response(target, "Entry already exists (no duplicate added).")

            # Calculate what the new total would be
            new_entries = entries + [content]
            new_total = len(ENTRY_DELIMITER.join(new_entries))

            if new_total > limit:
                current = self._char_count(target)
                return {
                    "success": False,
                    "error": (
                        f"Memory at {current:,}/{limit:,} chars. "
                        f"Adding this entry ({len(content)} chars) would exceed the limit. "
                        f"Replace or remove existing entries first."
                    ),
                    "current_entries": entries,
                    "usage": f"{current:,}/{limit:,}",
                }

            entries.append(content)
            self._set_entries(target, entries)
            self.save_to_disk(target)

        return self._success_response(target, "Entry added.")

    def replace(self, target: str, old_text: str, new_content: str) -> Dict[str, Any]:
        """Find entry containing old_text substring, replace it with new_content."""
        old_text = old_text.strip()
        new_content = new_content.strip()
        if not old_text:
            return {"success": False, "error": "old_text cannot be empty."}
        if not new_content:
            return {
                "success": False,
                "error": "new_content cannot be empty. Use 'remove' to delete entries.",
            }

        with self._file_lock(self._path_for(target)):
            self._reload_target(target)

            entries = self._entries_for(target)
            matches = [(i, e) for i, e in enumerate(entries) if old_text in e]

            if not matches:
                return {"success": False, "error": f"No entry matched '{old_text}'."}

            if len(matches) > 1:
                # If all matches are identical, operate on the first one
                unique_texts = {e for _, e in matches}
                if len(unique_texts) > 1:
                    previews = []
                    for _, e in matches:
                        preview = e[:80] + ("..." if len(e) > 80 else "")
                        previews.append(preview)
                    return {
                        "success": False,
                        "error": f"Multiple entries matched '{old_text}'. Be more specific.",
                        "matches": previews,
                    }

            idx = matches[0][0]
            limit = self._char_limit(target)

            # Check that replacement doesn't blow the budget
            test_entries = entries.copy()
            test_entries[idx] = new_content
            new_total = len(ENTRY_DELIMITER.join(test_entries))

            if new_total > limit:
                return {
                    "success": False,
                    "error": (
                        f"Replacement would put memory at {new_total:,}/{limit:,} chars. "
                        f"Shorten the new content or remove other entries first."
                    ),
                }

            entries[idx] = new_content
            self._set_entries(target, entries)
            self.save_to_disk(target)

        return self._success_response(target, "Entry replaced.")

    def remove(self, target: str, old_text: str) -> Dict[str, Any]:
        """Remove the entry containing old_text substring."""
        old_text = old_text.strip()
        if not old_text:
            return {"success": False, "error": "old_text cannot be empty."}

        with self._file_lock(self._path_for(target)):
            self._reload_target(target)

            entries = self._entries_for(target)
            matches = [(i, e) for i, e in enumerate(entries) if old_text in e]

            if not matches:
                return {"success": False, "error": f"No entry matched '{old_text}'."}

            if len(matches) > 1:
                unique_texts = {e for _, e in matches}
                if len(unique_texts) > 1:
                    previews = []
                    for _, e in matches:
                        preview = e[:80] + ("..." if len(e) > 80 else "")
                        previews.append(preview)
                    return {
                        "success": False,
                        "error": f"Multiple entries matched '{old_text}'. Be more specific.",
                        "matches": previews,
                    }

            idx = matches[0][0]
            entries.pop(idx)
            self._set_entries(target, entries)
            self.save_to_disk(target)

        return self._success_response(target, "Entry removed.")

    def read(self, target: str) -> Dict[str, Any]:
        """Read all entries for a target."""
        entries = self._entries_for(target)
        current = self._char_count(target)
        limit = self._char_limit(target)
        pct = min(100, int((current / limit) * 100)) if limit > 0 else 0

        return {
            "success": True,
            "target": target,
            "entries": entries,
            "usage": f"{pct}% — {current:,}/{limit:,} chars",
            "entry_count": len(entries),
        }

    # ── Facts (dated entries) ────────────────────────────────────────────

    def add_fact(self, topic: str, content: str, date: Optional[str] = None) -> Dict[str, Any]:
        """Add a dated fact entry."""
        content = content.strip()
        if not content:
            return {"success": False, "error": "Content cannot be empty."}

        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        # Sanitize topic for filename
        safe_topic = re.sub(r"[^\w\-]", "_", topic.lower())[:50]
        filename = f"{date}_{safe_topic}.md"
        filepath = self.facts_dir / filename

        # Build fact file content
        fact_content = f"# {date}_{safe_topic}\n\n{content}\n"

        try:
            filepath.write_text(fact_content, encoding="utf-8")
            logger.info("Fact added: %s", filename)
            return {
                "success": True,
                "filename": filename,
                "path": str(filepath),
                "message": f"Fact saved as {filename}",
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to write fact: {e}"}

    def list_facts(self, limit: int = 50) -> Dict[str, Any]:
        """List fact files sorted by date (newest first)."""
        if not self.facts_dir.exists():
            return {"success": True, "facts": [], "count": 0}

        fact_files = sorted(self.facts_dir.glob("*.md"), reverse=True)[:limit]
        facts = []
        for f in fact_files:
            facts.append({
                "filename": f.name,
                "path": str(f),
                "size": f.stat().st_size,
                "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
            })

        return {"success": True, "facts": facts, "count": len(facts)}

    def read_fact(self, filename: str) -> Dict[str, Any]:
        """Read a specific fact file."""
        filepath = self.facts_dir / filename
        if not filepath.exists():
            return {"success": False, "error": f"Fact not found: {filename}"}

        try:
            content = filepath.read_text(encoding="utf-8")
            return {
                "success": True,
                "filename": filename,
                "content": content,
                "size": filepath.stat().st_size,
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to read fact: {e}"}

    def remove_fact(self, filename: str) -> Dict[str, Any]:
        """Remove a fact file."""
        filepath = self.facts_dir / filename
        if not filepath.exists():
            return {"success": False, "error": f"Fact not found: {filename}"}

        try:
            filepath.unlink()
            logger.info("Fact removed: %s", filename)
            return {"success": True, "message": f"Fact removed: {filename}"}
        except Exception as e:
            return {"success": False, "error": f"Failed to remove fact: {e}"}

    # ── Frozen Snapshot ──────────────────────────────────────────────────

    def format_for_system_prompt(self, target: str) -> Optional[str]:
        """Return the frozen snapshot for system prompt injection.

        This returns the state captured at load_from_disk() time, NOT the live
        state. Mid-session writes do not affect this. This keeps the system
        prompt stable across all turns, preserving the prefix cache.
        """
        block = self._system_prompt_snapshot.get(target, "")
        return block if block else None

    # ── Internal Helpers ─────────────────────────────────────────────────

    def _success_response(self, target: str, message: Optional[str] = None) -> Dict[str, Any]:
        entries = self._entries_for(target)
        current = self._char_count(target)
        limit = self._char_limit(target)
        pct = min(100, int((current / limit) * 100)) if limit > 0 else 0

        resp = {
            "success": True,
            "target": target,
            "entries": entries,
            "usage": f"{pct}% — {current:,}/{limit:,} chars",
            "entry_count": len(entries),
        }
        if message:
            resp["message"] = message
        return resp

    def _render_block(self, target: str, entries: List[str]) -> str:
        """Render a system prompt block with header and usage indicator."""
        limit = self._char_limit(target)

        # For user block, always show instructions even if empty
        if target == "user" and not entries:
            return (
                "════════════════════════════════════════════════\n"
                "USER PROFILE (who the user is) [0% — 0/1,375 chars]\n"
                "════════════════════════════════════════════════\n"
                "ВАЖНО: USER PROFILE пуст! Ты ОБЯЗАН:\n"
                "1. Познакомься: представься коротко (1-2 предложения), спроси имя и роль\n"
                "2. После ответа пользователя — ОБЯЗАТЕЛЬНО вызови memory_write(action='add', target='user', content='...')\n"
                "3. Не называй себя «ассистентом». Не более 3 предложений.\n"
                "БЕЗ ВЫЗОВА memory_write ИНФОРМАЦИЯ ПОТЕРЯЕТСЯ при следующем чате!"
            )

        if not entries:
            return ""

        content = ENTRY_DELIMITER.join(entries)
        current = len(content)
        pct = min(100, int((current / limit) * 100)) if limit > 0 else 0

        if target == "user":
            header = (
                f"USER PROFILE (who the user is) [{pct}% — {current:,}/{limit:,} chars]\n"
                f"Факты о пользователе. Используй эту информацию в диалоге. Дополняй через memory_write если узнал новое."
            )
        else:
            header = f"MEMORY (your personal notes) [{pct}% — {current:,}/{limit:,} chars]"

        separator = "═" * 46
        return f"{separator}\n{header}\n{separator}\n{content}"

    def _path_for(self, target: str) -> Path:
        if target == "user":
            # Global USER.md — shared across all agents
            shared_dir = self.data_dir / "shared"
            shared_dir.mkdir(parents=True, exist_ok=True)
            return shared_dir / "USER.md"
        return self.memory_dir / "MEMORY.md"

    def _entries_for(self, target: str) -> List[str]:
        if target == "user":
            return self.user_entries
        return self.memory_entries

    def _set_entries(self, target: str, entries: List[str]):
        if target == "user":
            self.user_entries = entries
        else:
            self.memory_entries = entries

    def _char_count(self, target: str) -> int:
        entries = self._entries_for(target)
        if not entries:
            return 0
        return len(ENTRY_DELIMITER.join(entries))

    def _char_limit(self, target: str) -> int:
        if target == "user":
            return self.user_char_limit
        return self.memory_char_limit

    def _reload_target(self, target: str):
        """Re-read entries from disk into in-memory state."""
        path = self._path_for(target)
        fresh = self._read_file(path)
        fresh = list(dict.fromkeys(fresh))  # deduplicate
        self._set_entries(target, fresh)

    @staticmethod
    def _read_file(path: Path) -> List[str]:
        """Read a memory file and split into entries."""
        if not path.exists():
            return []
        try:
            content = path.read_text(encoding="utf-8")
            entries = content.split(ENTRY_DELIMITER)
            return [e.strip() for e in entries if e.strip()]
        except Exception as e:
            logger.error("Failed to read %s: %s", path, e)
            return []

    @staticmethod
    def _write_file(path: Path, entries: List[str]):
        """Write entries to a file atomically."""
        content = ENTRY_DELIMITER.join(entries)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Atomic write: temp file + rename
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

    @staticmethod
    def _file_lock(path: Path):
        """Context manager for file locking."""
        return FileLock(path)


class FileLock:
    """Simple file-based lock for concurrent access."""

    def __init__(self, path: Path):
        self.lock_path = path.with_suffix(path.suffix + ".lock")
        self._fd = None

    def __enter__(self):
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._fd = open(self.lock_path, "a+", encoding="utf-8")
        try:
            import fcntl
            fcntl.flock(self._fd, fcntl.LOCK_EX)
        except ImportError:
            try:
                import msvcrt
                self._fd.seek(0)
                msvcrt.locking(self._fd.fileno(), msvcrt.LK_LOCK, 1)
            except ImportError:
                pass  # No locking available (Windows without msvcrt)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            try:
                import fcntl
                fcntl.flock(self._fd, fcntl.LOCK_UN)
            except ImportError:
                try:
                    import msvcrt
                    self._fd.seek(0)
                    msvcrt.locking(self._fd.fileno(), msvcrt.LK_UNLCK, 1)
                except ImportError:
                    pass
        finally:
            self._fd.close()
        return False
