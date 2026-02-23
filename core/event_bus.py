from __future__ import annotations

import asyncio

from models.event import StatusEvent


class EventBus:
    """Async event channel backed by ``asyncio.Queue``.

    Producers call ``put()`` to publish deduplicated events.
    Each consumer receives its own independent queue so that a slow
    consumer never blocks others or the ingestion pipeline.

    Internally a fan-out model: one inbound ``put()`` copies the event
    into every subscriber queue.
    """

    def __init__(self, maxsize: int = 0) -> None:
        self._subscribers: list[asyncio.Queue[StatusEvent]] = []
        self._maxsize = maxsize

    def subscribe(self) -> asyncio.Queue[StatusEvent]:
        """Create and return a new subscriber queue.

        Each consumer should call this once at startup and then
        ``await queue.get()`` in a loop.
        """
        q: asyncio.Queue[StatusEvent] = asyncio.Queue(maxsize=self._maxsize)
        self._subscribers.append(q)
        return q

    async def put(self, event: StatusEvent) -> None:
        """Publish an event to every subscriber queue."""
        for q in self._subscribers:
            await q.put(event)
