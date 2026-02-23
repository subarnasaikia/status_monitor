from __future__ import annotations

import asyncio
import logging

from core.dedup import DeduplicationStore
from core.event_bus import EventBus
from core.registry import ProviderRegistry
from providers.base import StatusProvider

log = logging.getLogger(__name__)

DEFAULT_CONCURRENCY_LIMIT = 20


class Scheduler:
    """Producer coordinator that spawns one independent worker task per
    registered provider.

    Each worker runs on its own schedule (``provider.poll_interval_seconds``)
    and acquires a shared ``asyncio.Semaphore`` before performing a network
    fetch, bounding the maximum number of concurrent outbound requests.

    The scheduler is strictly a *producer* -- it pushes deduplicated events
    onto the ``EventBus`` and has no knowledge of consumers.
    """

    def __init__(
        self,
        registry: ProviderRegistry,
        dedup: DeduplicationStore,
        bus: EventBus,
        concurrency_limit: int = DEFAULT_CONCURRENCY_LIMIT,
    ) -> None:
        self._registry = registry
        self._dedup = dedup
        self._bus = bus
        self._semaphore = asyncio.Semaphore(concurrency_limit)

    async def _provider_worker(self, provider: StatusProvider) -> None:
        """Long-lived worker loop for a single provider.

        Each cycle:
        1. acquire semaphore (bounds concurrent fetches)
        2. fetch events from provider
        3. dedup and publish new events to bus
        4. release semaphore
        5. sleep for provider's poll interval
        """
        log.info(
            "Worker started for %s (interval=%ds)",
            provider.name,
            provider.poll_interval_seconds,
        )

        while True:
            async with self._semaphore:
                try:
                    events = await provider.fetch_events()
                except Exception:
                    log.exception("Worker %s fetch failed", provider.name)
                    events = []

            new_count = 0
            for event in events:
                if self._dedup.is_new(event):
                    await self._bus.put(event)
                    new_count += 1

            if new_count:
                log.info(
                    "Worker %s: %d new event(s), %d total tracked",
                    provider.name,
                    new_count,
                    self._dedup.size,
                )

            await asyncio.sleep(provider.poll_interval_seconds)

    async def run(self) -> None:
        """Spawn one worker task per provider and await them all.

        If no providers are registered the method returns immediately.
        """
        providers = self._registry.providers
        if not providers:
            log.warning("No providers registered")
            return

        log.info(
            "Scheduler starting %d provider worker(s), concurrency limit=%d",
            len(providers),
            self._semaphore._value,
        )

        tasks = [
            asyncio.create_task(
                self._provider_worker(p),
                name=f"worker-{p.name}",
            )
            for p in providers
        ]

        await asyncio.gather(*tasks)
