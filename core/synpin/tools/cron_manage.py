"""Cron management tool — for agents to create/manage scheduled tasks."""
from __future__ import annotations

import os
from typing import Any
from .base import ToolResult, make_success, make_error
from ._registry import register_tool
_API_BASE = os.environ.get("SYNPIN_API_BASE", "http://127.0.0.1:2088")


@register_tool(
    name='cron_manage',
    description="Управление запланированными задачами (cron). Создавай, обновляй, удаляй крон-задачи, смотри историю запусков, запускай немедленно. Типы: cron (повторяющиеся), once (одноразовые), interval (интервал). Действия: send_message (в отдел), run_prompt (запустить агента). ПРОАКТИВНЫЙ CRON: когда пользователь говорит про будущее событие («завтра», «через час», «на следующей неделе») — СТАВЬ cron САМОСТОЯТЕЛЬНО через cron_manage(command='create', schedule_type='once' или 'interval'). НЕ СПРАШИВАЙ разрешения — твоя работа замечать такие моменты. Параметр delivery: 'private' (по умолчанию, результат → в чат пользователю) | 'otdel' (в чат отдела) | 'silent' (только лог, без чата — для фоновых проверок).\n\nДЕДУПЛИКАЦИЯ (по умолчанию ВКЛЮЧЕНА): при create если у тебя уже есть активный cron с тем же name — он ОБНОВЛЯЕТСЯ (новый schedule/action заменяют старые), а не создаётся новый. Это лечит спам «напомни про чайник» × 5 за 15 минут. Управление через behavior: 'merge' (default, дедуп) | 'replace' (force update даже paused/completed, переактивирует) | 'new' (всегда создавать новый — обходит лимит). Для обычных напоминаний НЕ указывай behavior — дефолт 'merge' сработает.\n\nЖЁСТКИЕ ПРАВИЛА выбора action_target / action_agent / delivery:\n\n1. Пользователь просит 'напомни мне', 'напиши мне', 'спроси меня позже' →\n   - action_target='private'\n   - delivery='private'\n   - action_agent='main_agent' (или текущий slug)\n   - action_message: прямой текст напоминания\n\n2. Пользователь просит 'попроси главу отдела X сделать Y' / 'напомни отделу Z' / 'через час проверь отдел' →\n   - action_target='otdel:<ID>' (формат otdel:<slug_or_id>)\n   - delivery='otdel'\n   - action_agent='<head_slug_отдела_X>' (НЕ main_agent!)\n   - action_message: 'Сделай Y в контексте своего отдела'\n   Чтобы найти slug/id отдела/head: используй tool otdel_manage(command='list').\n\n3. Пользователь просит 'проверь логи тихо', 'посмотри статус молча', 'просто запиши факт' →\n   - action_target='private'\n   - delivery='silent'\n   - action_agent='main_agent'\n   - action_message: пиши факт в MEMORY через memory_write (НЕ пиши в чат)\n\nЗАПРЕЩЕНО: ставить cron с action_target='private' + action_agent='main_agent' для задач которые должны идти в отдел. Это приведёт к тому что результат попадёт в личный чат пользователя вместо чата отдела. Если сомневаешься — посмотри otdel_manage(command='list') и возьми head slug оттуда.",
    category='other',
    scope='head',
    dangerous=False,
)
async def cron_manage(params: dict[str, Any]) -> ToolResult:
    """
    Управление запланированными задачами (cron).
    Позволяет создавать, обновлять, удалять и просматривать крон-задачи.
    Commands:
      list    — все крон-задачи
      get     — одна задача по ID
      create  — создать задачу
      update  — обновить задачу
      delete  — удалить задачу
      history — история запусков задачи (run_count, last_run_at, next_run_at)
      run_now — немедленный запуск задачи
    """
    import httpx

    command = params.get("command", "")
    if not command:
        return make_error("command required: list, get, create, update, delete, history, run_now")

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            if command == "list":
                res = await client.get(f"{_API_BASE}/api/cron/jobs")
                if res.status_code != 200:
                    return make_error(f"Failed to list jobs: {res.text}")
                data = res.json()
                jobs = data.get("jobs", [])
                # Format for readability
                formatted = []
                for j in jobs:
                    schedule = f"{j.get('schedule_type', '?')}: {j.get('schedule_expr', '?')}"
                    action = f"{j.get('action_type', '?')} -> {j.get('action_target', '?')}"
                    status = j.get("status", "?")
                    runs = j.get("run_count", 0)
                    formatted.append(f"  [{j['id']}] {j['name']} | {schedule} | {action} | {status} | runs:{runs}")
                return make_success({
                    "jobs": jobs,
                    "count": len(jobs),
                    "formatted": formatted,
                })

            elif command == "get":
                job_id = params.get("job_id", "")
                if not job_id:
                    return make_error("job_id required")
                res = await client.get(f"{_API_BASE}/api/cron/jobs/{job_id}")
                if res.status_code != 200:
                    return make_error(f"Job not found: {job_id}")
                return make_success(res.json())

            elif command == "create":
                name = params.get("name", "")
                if not name:
                    return make_error("name required")
                action_type = params.get("action_type", "run_prompt")
                action_target = params.get("action_target", "") or "private"
                action_agent = params.get("action_agent", "") or "main_agent"
                payload = {
                                    "name": name,
                                    "schedule_type": params.get("schedule_type", "cron"),
                                    "schedule_expr": params.get("schedule_expr", ""),
                                    "action_type": action_type,
                                    "action_target": action_target,
                                    "action_message": params.get("action_message", ""),
                                    "action_agent": action_agent,
                                    "description": params.get("description", ""),
                                    "created_by": params.get("created_by", "main_agent"),
                                    "timezone": params.get("timezone", "Europe/Moscow"),
                                    "delivery": params.get("delivery", "private"),
                                    "behavior": params.get("behavior", "merge"),
                                }
                res = await client.post(f"{_API_BASE}/api/cron/jobs", json=payload)
                if res.status_code != 200:
                    return make_error(f"Failed to create job: {res.text}")
                job = res.json()
                return make_success({
                    "status": "created",
                    "job_id": job.get("id"),
                    "name": job.get("name"),
                    "next_run_at": job.get("next_run_at"),
                    "_hint": "Крон создан. НЕ ВЫЗЫВАЙ cron_manage повторно для этой же задачи — "
                             "задача уже стоит. Сразу отвечай пользователю кратко: что запланировано и когда.",
                })

            elif command == "update":
                job_id = params.get("job_id", "")
                if not job_id:
                    return make_error("job_id required")
                payload = {}
                for key in ("name", "schedule_type", "schedule_expr", "action_type",
                             "action_target", "action_message", "action_agent",
                             "description", "status", "timezone"):
                    if key in params:
                        payload[key] = params[key]
                if not payload:
                    return make_error("Nothing to update")
                res = await client.put(f"{_API_BASE}/api/cron/jobs/{job_id}", json=payload)
                if res.status_code != 200:
                    return make_error(f"Failed to update job: {res.text}")
                return make_success({"status": "updated", "job_id": job_id})

            elif command == "delete":
                job_id = params.get("job_id", "")
                if not job_id:
                    return make_error("job_id required")
                res = await client.delete(f"{_API_BASE}/api/cron/jobs/{job_id}")
                if res.status_code != 200:
                    return make_error(f"Failed to delete job: {res.text}")
                return make_success({"status": "deleted", "job_id": job_id})

            elif command == "history":
                job_id = params.get("job_id", "")
                if not job_id:
                    return make_error("job_id required")
                res = await client.get(f"{_API_BASE}/api/cron/jobs/{job_id}")
                if res.status_code != 200:
                    return make_error(f"Job not found: {job_id}")
                job = res.json()
                return make_success({
                    "job_id": job.get("id"),
                    "name": job.get("name"),
                    "status": job.get("status"),
                    "schedule_type": job.get("schedule_type"),
                    "schedule_expr": job.get("schedule_expr"),
                    "run_count": job.get("run_count", 0),
                    "last_run_at": job.get("last_run_at"),
                    "next_run_at": job.get("next_run_at"),
                    "created_at": job.get("created_at"),
                    "updated_at": job.get("updated_at"),
                    "created_by": job.get("created_by"),
                })

            elif command == "run_now":
                job_id = params.get("job_id", "")
                if not job_id:
                    return make_error("job_id required")
                res = await client.post(f"{_API_BASE}/api/cron/jobs/{job_id}/run")
                if res.status_code != 200:
                    return make_error(f"Failed to run job: {res.text}")
                data = res.json()
                return make_success({
                    "status": "triggered",
                    "job_id": job_id,
                    "name": data.get("name", ""),
                    "note": data.get("note", "Job executed immediately"),
                })

            else:
                return make_error(f"Unknown command: {command}")

    except httpx.ConnectError:
        return make_error("Cannot connect to SynPin server")
    except Exception as e:
        return make_error(f"cron_manage error: {e}")
