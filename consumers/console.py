from __future__ import annotations

from models.event import StatusEvent
from consumers.base import EventConsumer


class ConsoleConsumer(EventConsumer):
    """Reactive consumer that prints status events to stdout."""

    async def process(self, event: StatusEvent) -> None:
        ts = event.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        print(
            f"[{ts}] Provider: {event.provider}\n"
            f"  Product: {event.service}\n"
            f"  Status: {event.message}\n",
            flush=True,
        )
