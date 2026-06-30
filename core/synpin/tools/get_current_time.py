"""Tool: get_current_time — returns current date, time, and timezone.

Agents can call this to know what time it is on the server.
"""
from __future__ import annotations
from typing import Any
from .base import ToolResult, make_success, make_error
from ._registry import register_tool



@register_tool(
    name='get_current_time',
    description='Получить текущую дату, время и таймзону сервера.',
    category='system',
    scope='builtin',
    dangerous=False,
)
async def get_current_time(params: dict[str, Any]) -> ToolResult:
    """Return current server time with optional timezone info.

    Params:
        format (str, optional): "full" (default), "time_only", "date_only"
    """
    try:
        from ..time import now, now_with_tz

        fmt = params.get("format", "full")

        if fmt == "time_only":
            return make_success(now().strftime("%H:%M:%S"))
        elif fmt == "date_only":
            return make_success(now().strftime("%Y-%m-%d"))
        else:
            info = now_with_tz()
            lines = [
                f"Дата: {info['date']}",
                f"Время: {info['time']}",
                f"День недели: {info['weekday']}",
                f"Таймзона: {info['timezone']}",
                f"Timestamp: {info['timestamp']}",
            ]
            return make_success("\n".join(lines))
    except Exception as e:
        return make_error(f"get_current_time failed: {e}")
