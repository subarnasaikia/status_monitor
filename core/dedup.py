from __future__ import annotations

from models.event import StatusEvent


class DeduplicationStore:
    """In-memory store that tracks which (provider, event_id) pairs have
    already been processed, preventing duplicate consumer dispatches when
    feeds return historical entries.
    """

    def __init__(self) -> None:
        self._seen: set[tuple[str, str]] = set()

    def is_new(self, event: StatusEvent) -> bool:
        """Return True the first time a given event is seen, False after."""
        key = (event.provider, event.id)
        if key in self._seen:
            return False
        self._seen.add(key)
        return True

    @property
    def size(self) -> int:
        return len(self._seen)
