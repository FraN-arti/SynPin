"""
Triggers — `log` action.

Debug-only: prints event to logger. Used during trigger development
to verify the engine is firing without side effects.
"""
from __future__ import annotations

import logging
from ..base import ActionPlugin, Event, TriggerContext

logger = logging.getLogger("synpin.triggers.action.log")


class LogAction(ActionPlugin):
    type = "log"

    async def run(self, ctx: TriggerContext, event: Event) -> None:
        logger.info(
            "trigger fired: type=%s payload=%s config=%s",
            event.type,
            event.payload,
            ctx.config,
        )
