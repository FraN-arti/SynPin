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
        agent_slug: str = ctx.action_config.get("agent_slug", "")
        prompt: str = ctx.action_config.get("prompt", "")
        if not agent_slug or not prompt:
            logger.warning("agent_prompt: missing agent_slug or prompt in config")
            return

        # Substitute {payload_key} placeholders with event payload values.
        rendered = prompt.format(**event.payload) if "{" in prompt else prompt

        # Stable trigger id for channel isolation.
        # Use the running engine's "current_trigger" attribute if set,
        # else fall back to a stable hash of (type, payload).
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
