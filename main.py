"""Status Monitor -- entry point.

Assembles the event-driven pipeline:

    Provider workers (one asyncio task per provider)
        -> dedup
        -> EventBus (asyncio.Queue fan-out)
        -> Consumer tasks (react to queue.get())

A shared httpx.AsyncClient is injected into all providers.
A semaphore inside the scheduler caps concurrent network fetches.
Each provider runs on its own polling cadence.
"""
from __future__ import annotations

import asyncio
import logging

import httpx

from consumers.console import ConsoleConsumer
from core.dedup import DeduplicationStore
from core.event_bus import EventBus
from core.registry import ProviderRegistry
from core.scheduler import Scheduler
from providers.openai_provider import OpenAIProvider


async def run() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    async with httpx.AsyncClient(timeout=30.0) as client:
        bus = EventBus()

        registry = ProviderRegistry()
        registry.register(OpenAIProvider(client=client))

        dedup = DeduplicationStore()

        scheduler = Scheduler(
            registry=registry,
            dedup=dedup,
            bus=bus,
            concurrency_limit=20,
        )

        consumers = [
            ConsoleConsumer(queue=bus.subscribe()),
        ]

        tasks = [
            asyncio.create_task(scheduler.run(), name="scheduler"),
            *(
                asyncio.create_task(c.run(), name=type(c).__name__)
                for c in consumers
            ),
        ]

        await asyncio.gather(*tasks)


def main() -> None:
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("\nShutting down.")


if __name__ == "__main__":
    main()
