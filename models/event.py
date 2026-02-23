from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class StatusEvent:
    """Canonical event emitted by every provider adapter.

    Fields:
        id:        Unique identifier scoped to the provider (e.g. incident ID
                   or incident-ID:component composite).
        provider:  Human-readable provider name ("OpenAI", "GitHub", ...).
        service:   Affected product or component name.
        message:   Incident title combined with the latest status text.
        timestamp: When the incident/update was last modified (UTC).
    """

    id: str
    provider: str
    service: str
    message: str
    timestamp: datetime
