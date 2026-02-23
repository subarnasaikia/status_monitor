from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from html.parser import HTMLParser

import feedparser
import httpx

from models.event import StatusEvent
from providers.base import StatusProvider

_FEED_URL = "https://status.openai.com/feed.atom"
_STATUS_RE = re.compile(r"Status:\s*(.+?)(?:<|$)", re.IGNORECASE)

log = logging.getLogger(__name__)


class _LIExtractor(HTMLParser):
    """Tiny HTML parser that collects text inside <li> tags."""

    def __init__(self) -> None:
        super().__init__()
        self._in_li = False
        self.items: list[str] = []
        self._buf: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "li":
            self._in_li = True
            self._buf = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "li" and self._in_li:
            self._in_li = False
            self.items.append("".join(self._buf).strip())

    def handle_data(self, data: str) -> None:
        if self._in_li:
            self._buf.append(data)


def _extract_status(html: str) -> str:
    """Pull the status string (e.g. 'Resolved') from summary HTML."""
    m = _STATUS_RE.search(html)
    return m.group(1).strip() if m else "Unknown"


def _extract_components(html: str) -> list[str]:
    """Pull component names from <li> tags, stripping the '(Status)' suffix."""
    parser = _LIExtractor()
    parser.feed(html)
    components: list[str] = []
    for raw in parser.items:
        name = re.sub(r"\s*\(.*?\)\s*$", "", raw).strip()
        if name:
            components.append(name)
    return components


def _parse_timestamp(raw: str) -> datetime:
    """Parse ISO 8601 timestamps that may include fractional seconds."""
    cleaned = raw.replace("Z", "+00:00")
    return datetime.fromisoformat(cleaned).astimezone(timezone.utc)


class OpenAIProvider(StatusProvider):
    """Provider adapter for the OpenAI status page Atom feed.

    Uses HTTP conditional requests (ETag / If-None-Match) to skip
    re-parsing when the feed has not changed.
    """

    def __init__(self, client: httpx.AsyncClient) -> None:
        super().__init__(client)
        self._etag: str | None = None

    @property
    def name(self) -> str:
        return "OpenAI"

    @property
    def poll_interval_seconds(self) -> int:
        return 300

    async def fetch_events(self) -> list[StatusEvent]:
        headers: dict[str, str] = {}
        if self._etag:
            headers["If-None-Match"] = self._etag

        try:
            resp = await self._client.get(_FEED_URL, headers=headers)
        except httpx.HTTPError as exc:
            log.error("[%s] HTTP error: %s", self.name, exc)
            return []

        if resp.status_code == 304:
            return []

        if resp.status_code != 200:
            log.warning("[%s] Unexpected status %d", self.name, resp.status_code)
            return []

        self._etag = resp.headers.get("etag")
        feed = feedparser.parse(resp.text)
        events: list[StatusEvent] = []

        for entry in feed.entries:
            incident_id = self._extract_incident_id(entry.get("id", ""))
            if not incident_id:
                continue

            title: str = entry.get("title", "Unknown incident")
            summary_html: str = entry.get("summary", "")
            status_text = _extract_status(summary_html)
            components = _extract_components(summary_html)
            raw_ts: str = entry.get("updated", "")

            try:
                timestamp = _parse_timestamp(raw_ts)
            except (ValueError, TypeError):
                timestamp = datetime.now(timezone.utc)

            message = f"{title} -- {status_text}"

            if components:
                for comp in components:
                    events.append(StatusEvent(
                        id=f"{incident_id}:{comp}",
                        provider=self.name,
                        service=comp,
                        message=message,
                        timestamp=timestamp,
                    ))
            else:
                events.append(StatusEvent(
                    id=incident_id,
                    provider=self.name,
                    service=title,
                    message=message,
                    timestamp=timestamp,
                ))

        return events

    @staticmethod
    def _extract_incident_id(url: str) -> str | None:
        """Extract the incident identifier from the entry URL/ID."""
        marker = "/incidents/"
        idx = url.rfind(marker)
        if idx == -1:
            return None
        return url[idx + len(marker):]
