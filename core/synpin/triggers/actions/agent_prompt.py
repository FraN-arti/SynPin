"""
Triggers — `agent_prompt` action.

Sends a prompt to an agent in a **background channel** so the user
doesn't see the trigger↔agent conversation in their active chat.

Mechanics:
- Calls `_handle_chat_send` directly with `channel_id="trigger"` and
  `user_id="trigger:{trigger_id}"`. The chat router streams chunks to
  that user_id over WS, but no client is listening, so chunks are
  silently dropped.
- History is persisted to `data/agents/{slug}/sessions/trigger.json`,
  separate from the user's `web.json` conversation.

After the agent responds (when `chat:done` fires for this user_id),
the action optionally:
- delivers a toast to the user (default)
- writes the response to a file
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from ..base import ActionPlugin, Event, TriggerContext

logger = logging.getLogger("synpin.triggers.action.agent_prompt")


class AgentPromptAction(ActionPlugin):
    type = "agent_prompt"

    async def run(self, ctx: TriggerContext, event: Event) -> None:
        # agent_slug resolution order:
        #   1. explicit action_config.agent_slug
        #   2. event.payload.head_slug (idle_head ships this)
        #   3. event.payload.agent_slug (other plugins)
        agent_slug: str = (
            ctx.action_config.get("agent_slug", "")
            or event.payload.get("head_slug", "")
            or event.payload.get("agent_slug", "")
        )

        # prompt: explicit override OR per-event-type default
        prompt: str = ctx.action_config.get("prompt", "")
        if not prompt:
            defaults = {
                "idle_head": (
                    "Ты — глава отдела «{otdel_name}». Прошло {idle_minutes} мин с твоего последнего ответа. "
                    "В отделе {active_tasks} активных задач.\n"
                    "Это автоматическая проверка (health check). Пользователь это НЕ видит. "
                    "Действуй быстро и по делу:\n\n"
                    "1. Проверь активные задачи в канбане отдела. Если есть застрявшие (> N мин без движения) — "
                    "поторопи ответственных workers через otdel_message.\n"
                    "2. Проверь входящие запросы от других отделов (approvals) — если есть ожидающие, ответь.\n"
                    "3. Спроси у своих workers как дела и настроение — коротко, в чат отдела через otdel_message. "
                    "Это проверка что они живы и отзывчивы.\n"
                    "4. Если за время тишины принялися важные решения — запиши их в FACTS (memory_write).\n"
                    "5. Проверь свою память — не осталось ли устаревших записей.\n\n"
                    "ВАЖНО: Если задачи идут штатно, workers отвечают, ничего застряло — просто заверши без действий. "
                    "Пиши в чат отдела ТОЛЬКО когда есть реальная причина (застрявшая задача, долгое ревью, "
                    "нужно поторопить). Молчи — значит порядок."
                ),
                "kanban_stuck": (
                    "Задача «{task_title}» в колонке «{stage}» отдела «{otdel_id}» без движения {idle_minutes} мин. "
                    "Назначена на главу «{assigned_head}».\n\n"
                    "Действуй тихо, без шума. Пользователь это НЕ видит:\n"
                    "1. Посмотри задачу полностью — что в ней, какие были подвижки.\n"
                    "2. Если есть назначенный worker — спроси его через otdel_message как дела, и нужна ли помощь.\n"
                    "3. Если задача реально зависла (нет прогресса и нет видимых причин) — переведи её в другую колонку "
                    "(например в done если работа фактически завершена, или верни в in_progress с пояснением).\n"
                    "4. Если назначенной главы нет (пусто) — посмотри по задаче кто должен, и поторопи его.\n\n"
                    "Если задача в работе и не критично зависла — НЕ ТРОГАЙ колонку, просто молча заверши. "
                    "Пиши в чат отдела ТОЛЬКО если нужна реальная помощь."
                ),
                "kanban_in_review": (
                    "Задача «{task_title}» ждёт твоего ревью уже {idle_minutes} мин (в колонке «review»). "
                    "Ты — глава «{assigned_head}».\n\n"
                    "Ревью — твоя прямая обязанность. Быстро посмотри:\n"
                    "1. Открой задачу, проверь результат.\n"
                    "2. Если всё ок — переведи в done. Если нет — верни в in_progress с понятным комментарием что доделать.\n"
                    "3. Если не уверена — напиши в чат отдела короткий вопрос тому, кто делал.\n\n"
                    "ВАЖНО: Не затягивай. Долгое ревью тормозит весь отдел. Если задача не критична — всё равно реши "
                    "(можно одобрить с пометкой)."
                ),
                "kanban_revision": (
                    "Задача «{task_title}» в доработке уже {idle_minutes} мин. Worker должен был внести правки.\n\n"
                    "Проверь:\n"
                    "1. Свяжись с worker'ом через otdel_message — спроси как дела, что не получается, нужна ли помощь.\n"
                    "2. Если правки внесены (посмотри обновления) — переведи задачу обратно в review.\n"
                    "3. Если worker молчит или застрял долго — реши сама: верни в in_progress или закрой.\n\n"
                    "Долгая доработка = сигнал что что-то не так. Не игнорь."
                ),
            }
            prompt = defaults.get(event.type, f"Trigger {event.type}: {event.payload}")

        if not agent_slug or not prompt:
            logger.warning("agent_prompt: missing agent_slug or prompt for event %s", event.type)
            return

        # Substitute {payload_key} placeholders with event payload values.
        rendered = prompt.format(**event.payload) if "{" in prompt else prompt

        # Stable trigger id for channel isolation.
        trigger_id = getattr(ctx.engine, "_current_trigger_id", None) or event.payload.get(
            "_trigger_id", "anon"
        )
        user_id = f"trigger:{trigger_id}"

        try:
            from synpin.chat.ws_router import _handle_chat_send
        except ImportError as e:
            logger.error("agent_prompt: cannot import chat router: %s", e)
            return

        msg = {
            "agent_slug": agent_slug,
            "message": rendered,
            "channel_id": "trigger",
        }
        logger.info(
            "agent_prompt: firing trigger=%s agent=%s prompt_len=%d",
            trigger_id, agent_slug, len(rendered),
        )
        # Fire-and-forget — chat:done callback (if we add one) handles delivery.
        await _handle_chat_send(user_id, msg)
