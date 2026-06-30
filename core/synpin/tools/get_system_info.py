"""Tool: get_system_info — returns system info: hostname, IP, version, uptime.

Agents can call this to know about the server environment.
"""
from __future__ import annotations
from typing import Any
from .base import ToolResult, make_success, make_error
from ._registry import register_tool



@register_tool(
    name='get_system_info',
    description='Получить информацию о сервере: hostname, IP, версия, аптайм.',
    category='system',
    scope='builtin',
    dangerous=False,
)
async def get_system_info(params: dict[str, Any]) -> ToolResult:
    """Return system information.

    Params:
        format (str, optional): "full" (default) or "short"
    """
    try:
        from ..time import get_system_info as _sysinfo

        info = _sysinfo()
        fmt = params.get("format", "full")

        if fmt == "short":
            return make_success(
                f"SynPin {info['synpin_version']} | "
                f"{info['platform']} | "
                f"IP: {', '.join(info['ip_addresses'])} | "
                f"Uptime: {info['uptime']}"
            )
        else:
            lines = [
                f"SynPin версия: {info['synpin_version']}",
                f"Хост: {info['hostname']}",
                f"Платформа: {info['platform']}",
                f"Python: {info['python_version']}",
                f"IP адреса: {', '.join(info['ip_addresses'])}",
                f"Аптайм: {info['uptime']}",
            ]
            # Add time info
            t = info.get("time", {})
            if t:
                lines.append(f"Время сервера: {t['datetime']} ({t['timezone']})")
            return make_success("\n".join(lines))
    except Exception as e:
        return make_error(f"get_system_info failed: {e}")
