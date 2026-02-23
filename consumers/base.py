from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod

from models.event import StatusEvent

log = logging.getLogger(__name__)


class EventConsumer(ABC):
    """Reactive event consumer that runs as an independent asyncio task.

    Each consumer subscribes to an ``asyncio.Queue`` and blocks on
    ``queue.get()``, processing events as they arrive.  This decouples
    consumption from ingestion -- the scheduler never calls consumers
    directly.
    """

    def __init__(self, queue: asyncio.Queue[StatusEvent]) -> None:
        self._queue = queue

    @abstractmethod
    async def process(self, event: StatusEvent) -> None:
        """Handle a single event.  Subclasses implement this."""

    async def run(self) -> None:
        """Main consumer loop -- awaits events from the queue and
        dispatches them to ``process()``.

        Runs indefinitely; designed to be launched via
        ``asyncio.create_task(consumer.run())``.
        """
        log.info("%s started, awaiting events", type(self).__name__)
        while True:
            event = await self._queue.get()
            try:
                await self.process(event)
            except Exception:
                log.exception(
                    "%s failed processing event %s",
                    type(self).__name__,
                    event.id,
                )
            finally:
                self._queue.task_done()
