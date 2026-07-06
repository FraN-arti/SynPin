"""
Build a system-prompt fragment describing this agent's connections.

The fragment is included in the agent's `system_prompt` whenever the
agent is the head of an otdel that has structured connections, or is
the primary agent (whose id appears as `agent:primary` in connections).

Only connections where the agent's otdel (or the primary slot) is the
source are listed — that's the side the agent "owns" and needs to act
on. The other side (to) is shown as the destination.
"""
from __future__ import annotations

import logging
from typing import Iterable

from .config import load_connections
from .models import ConnectionType
from .refs import parse_ref, is_primary_agent_ref
from .resolve import resolve_ref

logger = logging.getLogger("synpin.connections.prompt")


def _resolve_endpoint_label(ref: str) -> str:
    """Human label for a connection endpoint, e.g. 'Главный агент' or 'Сайтовики'."""
    try:
        return resolve_ref(ref).display_name
    except Exception:  # noqa: BLE001
        return ref


def _otdel_ids_for_agent(agent_slug: str) -> set[str]:
    """Otdel ids where this agent is head or worker."""
    try:
        from synpin.agents.manager import load_otdels
        otdels = load_otdels() or []
    except Exception as e:  # noqa: BLE001
        logger.debug("could not load otdels: %s", e)
        return set()
    ids: set[str] = set()
    for o in otdels:
        if o.get("head") == agent_slug:
            ids.add(o.get("otdelid", ""))
        workers = o.get("workers") or []
        if isinstance(workers, list) and agent_slug in workers:
            ids.add(o.get("otdelid", ""))
    return ids


def _format_conn(conn) -> str:
    """Format a single connection for the agent's system prompt.

    Format:
        - «{label}» — {description} (если есть) — сотрудничай с {target}.

    Auto-escalation (approval-only): appended as a separate clause so
    the agent knows escalation is automatic, not its job.
    """
    label_part = f"«{conn.label}»" if conn.label else "(без названия)"
    desc_part = f" — {conn.description}" if conn.description else ""
    target_label = _resolve_endpoint_label(conn.to_otdel)
    line = f"- {label_part}{desc_part} — сотрудничай с {target_label}"
    if conn.type == ConnectionType.APPROVAL and conn.auto_trigger:
        line += f"\n  (авто-эскалация: задачи в статусе «{conn.auto_trigger.on_status}» дольше {conn.auto_trigger.timeout_s // 60} мин автоматически переносятся к {target_label})"
    return line


def build_connections_prompt_fragment(agent_slug: str, is_primary: bool) -> str:
    """Return a short text block describing the agent's connections.

    Empty string when nothing relevant — the caller can then skip
    appending the section heading altogether.
    """
    if not agent_slug:
        return ""

    connections = load_connections()
    otdel_ids = _otdel_ids_for_agent(agent_slug)
    sections: list[str] = []

    if is_primary:
        primary_conns = [
            c for c in connections
            if is_primary_agent_ref(c.from_otdel) or is_primary_agent_ref(c.to_otdel)
        ]
        if primary_conns:
            lines = ["## Связи главного агента"]
            lines.append(
                "Ты — главный агент системы. Ниже перечислены отделы, "
                "с которыми у тебя есть связь (по утверждению задач или "
                "по совместной работе). Описание каждой связи объясняет, "
                "в каких случаях её использовать."
            )
            for c in primary_conns:
                lines.append(_format_conn(c))
            sections.append("\n".join(lines))

    if otdel_ids:
        refs_for_my_otdels: set[str] = set()
        for cid in otdel_ids:
            refs_for_my_otdels.add(f"otdel:{cid}")
        otdel_conns = [
            c for c in connections
            if c.from_otdel in refs_for_my_otdels or c.to_otdel in refs_for_my_otdels
        ]
        if otdel_conns:
            lines = ["## Связи отделов, в которых ты работаешь"]
            lines.append(
                "Ты — глава или работник отдела. У каждого отдела, к которому ты "
                "имеешь отношение, могут быть связи с другими отделами. "
                "Когда задача подходит к завершению — посмотри на связи и реши, "
                "нужно ли передать её коллегам (например готов API → передать фронту). "
                "Описание связи объясняет, в каких случаях это делать."
            )
            for c in otdel_conns:
                lines.append(_format_conn(c))
            sections.append("\n".join(lines))

    if not sections:
        return ""
    return "\n\n" + "\n\n---\n\n".join(sections)
