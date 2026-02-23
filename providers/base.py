from __future__ import annotations

from abc import ABC, abstractmethod

import httpx

from models.event import StatusEvent

DEFAULT_POLL_INTERVAL = 300


class StatusProvider(ABC):
    """Abstract base for all status-page provider adapters.

    Each concrete provider is responsible for fetching its own data source
    (Atom feed, JSON API, etc.) and normalizing entries into StatusEvent
    objects.

    A shared ``httpx.AsyncClient`` is injected at construction time so
    that all providers reuse one connection pool.
    """

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider name (e.g. 'OpenAI')."""

    @property
    def poll_interval_seconds(self) -> int:
        """Seconds between fetch cycles for this provider.

        Override in subclasses to customise per-provider cadence.
        """
        return DEFAULT_POLL_INTERVAL

    @abstractmethod
    async def fetch_events(self) -> list[StatusEvent]:
        """Fetch the latest incidents/updates and return normalised events.

        Implementations should handle HTTP errors gracefully and return an
        empty list when no data is available or when the feed has not changed
        since the last poll.
        """
