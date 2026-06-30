"""Schedule intent parser — pure function, no LLM.

Detects scheduling intent in user text and returns a JobSpec ready
for create_job(). Replaces the old "agent uses cron_manage tool"
loop with a deterministic regex parser — the agent never sees
this code, the hook in chat/router.py parses user_text directly.

Returns None if no intent detected. Caller (the chat hook) treats
None as "no cron was set, do nothing" — agent never knows.

Supported patterns (Russian):
  - "через N (сек/мин/час/день/неделю)" → once + relative
  - "завтра в HH:MM" → once + ISO (next day)
  - "в HH:MM" → once + ISO (today if > now, else tomorrow)
  - "каждые N (мин/час)" → interval
  - "каждый день в HH:MM" → cron 'M H * * *'
  - "каждую минуту" → interval '1m'
  - "завтра" → once + next-day 09:00 default

Implicit routing:
  - "проверь/напомни отдел/команде X" → action_target='otdel:...'
  - bare reminder → action_target='private', action_agent='main_agent'

If multiple intents match, returns the FIRST one (leftmost in text).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional


@dataclass
class JobSpec:
    """Parsed schedule intent — ready to feed into create_job()."""
    name: str                       # short label for the cron job
    schedule_type: str              # 'once' | 'interval' | 'cron'
    schedule_expr: str              # '5m' | ISO timestamp | cron expr
    action_type: str = "send_message"  # default: instant ping, 0 LLM
    action_target: str = "private"
    action_message: str = ""
    action_agent: str = ""          # only for run_prompt
    delivery: str = "private"
    # For UI / marker — human-readable when it fires
    fires_at_human: str = ""


# ── Number-word map ────────────────────────────────────────────────────────
# "через пару минут" → 2m, "через полчаса" → 30m, etc.
_NUMBER_WORDS = {
    "пару": 2, "два": 2, "две": 2, "три": 3, "четыре": 4,
    "пять": 5, "шесть": 6, "семь": 7, "восемь": 8, "девять": 9,
    "десять": 10, "полчаса": 30, "полтора": 90,  # 1.5h
}

_UNIT_MINUTES = {"сек", "секунд", "секунды", "секунду", "с"}
_UNIT_MINUTES_LONG = {"мин", "минут", "минуты", "минуту", "м"}
_UNIT_HOURS = {"час", "часа", "часов", "ч"}
_UNIT_DAYS = {"день", "дня", "дней", "д"}
_UNIT_WEEKS = {"неделю", "недели", "недель", "нед"}


def _to_minutes(num: int, unit: str) -> int:
    """Convert (number, unit) → minutes. Used for 'через N UNIT'."""
    if unit in _UNIT_MINUTES:
        return max(0, num // 60) if num >= 60 else 0  # secs → 0 means sub-minute, clamp to 1
    if unit in _UNIT_MINUTES_LONG:
        return num
    if unit in _UNIT_HOURS:
        return num * 60
    if unit in _UNIT_DAYS:
        return num * 60 * 24
    if unit in _UNIT_WEEKS:
        return num * 60 * 24 * 7
    return 0


def _minutes_to_schedule_expr(total_min: int) -> str:
    """Convert minutes → short schedule_expr format that compute_next_run
    understands (jobs.py:_parse_interval_expr). Examples:
        1     → '1m'
        90    → '1h30m'
        1440  → '1d'
    """
    if total_min <= 0:
        return "1m"
    if total_min < 60:
        return f"{total_min}m"
    days, rem = divmod(total_min, 60 * 24)
    hours, rem_min = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if rem_min:
        parts.append(f"{rem_min}m")
    return "".join(parts) or "1m"


# ── Pattern: "через полчаса" / "через полтора часа" (compound words) ────
_RE_THROUGH_HALF = re.compile(
    r"\bчерез\s+(?P<kind>полчаса|полтора\s+часа)\b",
    re.IGNORECASE,
)


# ── Pattern: "через N (unit)" ─────────────────────────────────────────────
# Match "через 5 минут", "через пару часов", "через 2 ч", "через полчаса"
_RE_THROUGH = re.compile(
    r"\bчерез\s+"
    r"(?P<num>\d+|" + "|".join(_NUMBER_WORDS.keys()) + r")\s+"
    r"(?P<unit>" + "|".join(
        _UNIT_MINUTES | _UNIT_MINUTES_LONG | _UNIT_HOURS | _UNIT_DAYS | _UNIT_WEEKS
    ) + r")\b",
    re.IGNORECASE,
)


# ── Pattern: "завтра в HH:MM" / "в HH:MM" / "сегодня в HH:MM" ────────────
_RE_TOMORROW_AT = re.compile(
    r"\bзавтра\s+в\s+(?P<h>\d{1,2})[:.](?P<m>\d{2})\b",
    re.IGNORECASE,
)
_RE_TODAY_AT = re.compile(
    r"\b(?:сегодня\s+в\s+)?в\s+(?P<h>\d{1,2})[:.](?P<m>\d{2})\b",
    re.IGNORECASE,
)


# ── Pattern: "каждые N (мин/час)" / "каждую минуту" ──────────────────────
_RE_EVERY = re.compile(
    r"\bкажд(?:ые|ую|ый)\s+"
    r"(?P<num>\d+|" + "|".join(_NUMBER_WORDS.keys()) + r")?\s*"
    r"(?P<unit>минут(?:ы|у|)?|час(?:а|ов)?|секунд(?:ы|у|)?)\b",
    re.IGNORECASE,
)
_RE_EVERY_MINUTE = re.compile(r"\bкаждую\s+минуту\b", re.IGNORECASE)


# ── Pattern: "каждый день в HH:MM" ────────────────────────────────────────
_RE_DAILY_AT = re.compile(
    r"\bкаждый\s+день\s+в\s+(?P<h>\d{1,2})[:.](?P<m>\d{2})\b",
    re.IGNORECASE,
)


# ── Pattern: bare "завтра" (default 09:00 next day) ──────────────────────
_RE_TOMORROW_BARE = re.compile(r"\bзавтра\b", re.IGNORECASE)


# ── Pattern: "напомни/проверь/спроси ... отдел/команде X" ────────────────
_RE_OTDEL_TARGET = re.compile(
    r"\b(?:отдел(?:у|а|ом)?|команд(?:е|у|ой))\s+[\"«]?(?P<name>[\w\-]+)[\"»]?",
    re.IGNORECASE,
)


def _parse_num(token: str) -> int:
    """Convert digit-string or Russian number-word → int."""
    if token.isdigit():
        return int(token)
    return _NUMBER_WORDS.get(token.lower(), 0)


def _resolve_otdel_slug(otdel_name: str) -> Optional[str]:
    """Look up otdel by name (case-insensitive). Returns None if not found —
    caller treats None as 'couldn't resolve, skip cron creation'."""
    try:
        from ..agents.manager import list_otdels
        for o in list_otdels().get("otdels", []):
            slug = o.get("slug", "")
            name = o.get("name", "").lower()
            short = o.get("short_name", "").lower()
            otdel_id = o.get("id", "")
            for candidate in (slug, otdel_id, name, short):
                if candidate and candidate.lower() == otdel_name.lower():
                    return otdel_id or slug
        return None
    except Exception:
        return None


def _format_time(dt: datetime) -> str:
    """Human-readable HH:MM for the marker line."""
    return dt.strftime("%H:%M")


def parse_schedule_intent(
    user_text: str,
    *,
    now: Optional[datetime] = None,
) -> Optional[JobSpec]:
    """Detect scheduling intent in user text. Returns JobSpec or None.

    Pure function — no DB writes, no LLM. Caller decides what to do
    with the spec (typically: create_job() + append marker to agent reply).

    Args:
        user_text: the raw text the user just sent
        now:       current time (defaults to datetime.now()). Injectable
                   for deterministic tests.

    Returns:
        JobSpec with all fields ready for create_job(), or None if no
        intent was detected (or if intent was ambiguous and unsafe).
    """
    if not user_text or not user_text.strip():
        return None

    text = user_text.strip()
    now = now or datetime.now()

    # ── Detect optional otdel routing (target) ─────────────────────────
    action_target = "private"
    action_agent = ""  # send_message doesn't need an agent
    delivery = "private"

    otdel_match = _RE_OTDEL_TARGET.search(text)
    if otdel_match:
        otdel_name = otdel_match.group("name")
        slug = _resolve_otdel_slug(otdel_name)
        if slug:
            action_target = f"otdel:{slug}"
            # for otdel: route we still use send_message to ping the
            # head of the otdel — that's the cheapest, no-LLM path.
            delivery = "otdel"

    # ── 1. "каждый день в HH:MM" — recurring daily ────────────────────
    m = _RE_DAILY_AT.search(text)
    if m:
        h, mi = int(m.group("h")), int(m.group("m"))
        if 0 <= h < 24 and 0 <= mi < 60:
            name = _extract_short_name(text, fallback="Ежедневно")
            return JobSpec(
                name=name,
                schedule_type="cron",
                schedule_expr=f"{mi} {h} * * *",
                action_type="send_message",
                action_target=action_target,
                action_message=_extract_message(text, fallback=text),
                action_agent=action_agent,
                delivery=delivery,
                fires_at_human=f"каждый день в {h:02d}:{mi:02d}",
            )

    # ── 2. "каждую минуту" — interval 1m ──────────────────────────────
    if _RE_EVERY_MINUTE.search(text):
        name = _extract_short_name(text, fallback="Каждую минуту")
        return JobSpec(
            name=name,
            schedule_type="interval",
            schedule_expr="1m",
            action_type="send_message",
            action_target=action_target,
            action_message=_extract_message(text, fallback=text),
            action_agent=action_agent,
            delivery=delivery,
            fires_at_human="каждую минуту",
        )

    # ── 3. "каждые N (мин/час)" — interval ─────────────────────────────
    m = _RE_EVERY.search(text)
    if m and m.group("num"):
        n = _parse_num(m.group("num"))
        unit_raw = m.group("unit").lower()
        # Normalize unit
        if unit_raw.startswith("мин") or unit_raw.startswith("минут"):
            minutes = n
            unit_short = "m"
        elif unit_raw.startswith("час"):
            minutes = n * 60
            unit_short = "h"
        elif unit_raw.startswith("сек"):
            minutes = max(1, n // 60) if n >= 60 else 0
            unit_short = "m"
            if minutes == 0:
                minutes = 1
        else:
            minutes = 0
        if minutes > 0:
            name = _extract_short_name(text, fallback=f"Каждые {n} {unit_raw}")
            expr = _minutes_to_schedule_expr(minutes)
            return JobSpec(
                name=name,
                schedule_type="interval",
                schedule_expr=expr,
                action_type="send_message",
                action_target=action_target,
                action_message=_extract_message(text, fallback=text),
                action_agent=action_agent,
                delivery=delivery,
                fires_at_human=f"каждые {n} {unit_raw}",
            )

    # ── 4. "завтра в HH:MM" ───────────────────────────────────────────
    m = _RE_TOMORROW_AT.search(text)
    if m:
        h, mi = int(m.group("h")), int(m.group("m"))
        if 0 <= h < 24 and 0 <= mi < 60:
            target = (now + timedelta(days=1)).replace(
                hour=h, minute=mi, second=0, microsecond=0
            )
            name = _extract_short_name(text, fallback="Завтра")
            return JobSpec(
                name=name,
                schedule_type="once",
                schedule_expr=target.isoformat(),
                action_type="send_message",
                action_target=action_target,
                action_message=_extract_message(text, fallback=text),
                action_agent=action_agent,
                delivery=delivery,
                fires_at_human=f"завтра в {h:02d}:{mi:02d}",
            )

    # ── 5. "в HH:MM" / "сегодня в HH:MM" (today or tomorrow) ─────────
    m = _RE_TODAY_AT.search(text)
    if m:
        h, mi = int(m.group("h")), int(m.group("m"))
        if 0 <= h < 24 and 0 <= mi < 60:
            target = now.replace(hour=h, minute=mi, second=0, microsecond=0)
            if target <= now:
                target += timedelta(days=1)
            name = _extract_short_name(text, fallback="Напоминание")
            return JobSpec(
                name=name,
                schedule_type="once",
                schedule_expr=target.isoformat(),
                action_type="send_message",
                action_target=action_target,
                action_message=_extract_message(text, fallback=text),
                action_agent=action_agent,
                delivery=delivery,
                fires_at_human=f"в {h:02d}:{mi:02d}",
            )

    # ── 6a. "через полчаса" / "через полтора часа" (compound) ─────────
    m = _RE_THROUGH_HALF.search(text)
    if m:
        kind = m.group("kind").lower()
        total_min = 30 if kind == "полчаса" else 90
        expr = _minutes_to_schedule_expr(total_min)
        target = now + timedelta(minutes=total_min)
        name = _extract_short_name(text, fallback="Через полчаса")
        return JobSpec(
            name=name,
            schedule_type="once",
            schedule_expr=expr,
            action_type="send_message",
            action_target=action_target,
            action_message=_extract_message(text, fallback=text),
            action_agent=action_agent,
            delivery=delivery,
            fires_at_human=f"{kind} (~{_format_time(target)})",
        )

    # ── 6. "через N (сек/мин/час/день/неделю)" ────────────────────────
    m = _RE_THROUGH.search(text)
    if m:
        n = _parse_num(m.group("num"))
        unit = m.group("unit").lower()
        if n > 0:
            total_min = _to_minutes(n, unit)
            if total_min > 0:
                expr = _minutes_to_schedule_expr(total_min)
                # Compute actual fire time for the marker
                target = now + timedelta(minutes=total_min)
                name = _extract_short_name(text, fallback=f"Через {n} {unit}")
                return JobSpec(
                    name=name,
                    schedule_type="once",
                    schedule_expr=expr,
                    action_type="send_message",
                    action_target=action_target,
                    action_message=_extract_message(text, fallback=text),
                    action_agent=action_agent,
                    delivery=delivery,
                    fires_at_human=f"через {n} {unit} (~{_format_time(target)})",
                )

    # ── 7. bare "завтра" → default 09:00 next day ─────────────────────
    if _RE_TOMORROW_BARE.search(text):
        target = (now + timedelta(days=1)).replace(
            hour=9, minute=0, second=0, microsecond=0
        )
        name = _extract_short_name(text, fallback="Завтра")
        return JobSpec(
            name=name,
            schedule_type="once",
            schedule_expr=target.isoformat(),
            action_type="send_message",
            action_target=action_target,
            action_message=_extract_message(text, fallback=text),
            action_agent=action_agent,
            delivery=delivery,
            fires_at_human="завтра в 09:00",
        )

    # No intent detected — caller treats as "no cron"
    return None


def _extract_short_name(text: str, fallback: str = "Напоминание") -> str:
    """Pull a short label from user text. Used as the cron job name."""
    # Try quoted phrases first
    quoted = re.search(r"[«\"'](.+?)[»\"']", text)
    if quoted:
        snippet = quoted.group(1).strip()
        if len(snippet) <= 60:
            return snippet
    # Take first 5 words, capitalized
    words = re.findall(r"\b\w+\b", text)
    snippet = " ".join(words[:5])
    if len(snippet) > 60:
        snippet = snippet[:57] + "..."
    return snippet or fallback


def _extract_message(text: str, fallback: str = "") -> str:
    """Extract the message body for the cron job. Use quoted text if any,
    else the full user text (minus time-intent keywords)."""
    quoted = re.search(r"[«\"'](.+?)[»\"']", text)
    if quoted:
        return quoted.group(1).strip()
    # Strip time-intent prefix words for cleaner stored message
    cleaned = re.sub(
        r"\b(напомни|поставь|сделай|проверь|через\s+\S+|в\s+\d{1,2}[:.]\d{2}|"
        r"завтра|сегодня|кажд\w*\s+\S+|каждый\s+день)\b",
        "", text, flags=re.IGNORECASE,
    ).strip(" ,.!")
    return cleaned or fallback or text


def create_cron_from_intent(
    spec: JobSpec,
    *,
    created_by: str = "user",
) -> Optional[str]:
    """Wire a parsed JobSpec into the cron system.

    Returns the new job id, or None if creation failed (e.g. per-creator
    cap reached, dedup merged into existing). Dedup merge is treated as
    success — caller should still tell the user 'cron updated'.
    """
    try:
        from .jobs import create_job
        job = create_job(
            name=spec.name,
            schedule_type=spec.schedule_type,
            schedule_expr=spec.schedule_expr,
            action_type=spec.action_type,
            action_target=spec.action_target,
            action_message=spec.action_message,
            action_agent=spec.action_agent,
            created_by=created_by,
            delivery=spec.delivery,
        )
        return job.id
    except Exception:
        return None


def build_intent_marker(spec: JobSpec, job_id: Optional[str] = None) -> str:
    """Build the 📌 marker line appended to the agent's reply.

    This is what makes the user (and UI) see that the cron was set.
    """
    pin = f"📌 Напоминание: {spec.fires_at_human}"
    if spec.action_target and spec.action_target != "private":
        pin += f" → {spec.action_target}"
    if job_id:
        pin += f"  ·  #{job_id}"
    return pin