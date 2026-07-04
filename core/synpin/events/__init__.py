"""Events module — in-app event bus with WS fan-out.

Public API:
    publish_event(title, body, **kwargs)  — publish an event
    get_bus()                              — access the singleton EventBus
    get_in_app_settings / update_in_app_settings — settings I/O

Why "events" not "notifications": notifications are one possible
delivery channel (in-app today, Telegram/desktop/email tomorrow).
The bus is the umbrella concept — adding new channels later is
just a new transport that consumes the same stream.
"""
from .bus import EventBus, get_bus, publish_event  # noqa: F401
from .settings import (  # noqa: F401
    DEFAULT_IN_APP_SETTINGS,
    DEFAULT_SETTINGS,
    get_in_app_settings,
    update_in_app_settings,
)