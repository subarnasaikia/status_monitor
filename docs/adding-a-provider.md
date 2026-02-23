# Adding a New Provider

Adding a new status page requires two steps:

1. Create a provider adapter class
2. Register it in `main.py`

No changes to the scheduler, event bus, dedup, or consumers are needed.

## Step 1: Create the Adapter

Create a new file in `providers/`, e.g. `providers/github_provider.py`:

```python
from __future__ import annotations

import httpx

from models.event import StatusEvent
from providers.base import StatusProvider


class GitHubProvider(StatusProvider):

    _API_URL = "https://www.githubstatus.com/api/v2/incidents.json"

    def __init__(self, client: httpx.AsyncClient) -> None:
        super().__init__(client)

    @property
    def name(self) -> str:
        return "GitHub"

    @property
    def poll_interval_seconds(self) -> int:
        # GitHub updates less frequently -- poll every 10 minutes
        return 600

    async def fetch_events(self) -> list[StatusEvent]:
        try:
            resp = await self._client.get(self._API_URL)
        except httpx.HTTPError:
            return []

        if resp.status_code != 200:
            return []

        data = resp.json()
        events: list[StatusEvent] = []

        for incident in data.get("incidents", []):
            events.append(StatusEvent(
                id=incident["id"],
                provider=self.name,
                service=incident["name"],
                message=f"{incident['name']} -- {incident['status']}",
                timestamp=datetime.fromisoformat(
                    incident["updated_at"].replace("Z", "+00:00")
                ),
            ))

        return events
```

### Requirements

Your adapter **must**:

- Inherit from `StatusProvider`
- Call `super().__init__(client)` to receive the shared HTTP client
- Implement the `name` property (unique string)
- Implement `fetch_events()` returning `list[StatusEvent]`
- Handle HTTP errors gracefully (return `[]` on failure)

Your adapter **may**:

- Override `poll_interval_seconds` (default is 300s)
- Use HTTP conditional requests (ETag / If-None-Match) for efficiency
- Use any parsing library appropriate for the feed format

### Data Normalisation

Every event must be converted to a `StatusEvent`:

```python
StatusEvent(
    id="...",           # unique within this provider
    provider="GitHub",  # matches self.name
    service="...",      # affected product/component
    message="...",      # human-readable summary
    timestamp=...,      # datetime (UTC)
)
```

The `id` field must be unique within the provider.  If one incident affects
multiple components, use a composite ID like `f"{incident_id}:{component}"`
to generate one event per component.

## Step 2: Register in main.py

Import and register your provider:

```python
from providers.github_provider import GitHubProvider

# inside async def run():
registry.register(GitHubProvider(client=client))
```

That's it.  The scheduler will automatically spawn a dedicated worker task
for the new provider, polling at whatever interval it declares.

## Feed Format Reference

Common status page platforms and their machine-readable endpoints:

| Platform            | Feed Type  | Example URL                                          |
|---------------------|------------|------------------------------------------------------|
| Atlassian Statuspage | Atom      | `https://status.openai.com/feed.atom`                |
| Atlassian Statuspage | RSS       | `https://status.openai.com/feed.rss`                 |
| Atlassian Statuspage | JSON      | `https://status.openai.com/api/v2/incidents.json`    |
| incident.io          | Atom      | (same pattern as above)                              |
| Instatus             | JSON API  | `https://<slug>.instatus.com/summary.json`           |
| Cachet               | JSON API  | `https://<host>/api/v1/incidents`                    |
| Custom               | Any       | Implement whatever HTTP+parsing is needed            |

For Atom/RSS feeds, use `feedparser`.  For JSON APIs, parse `resp.json()`
directly.

## Testing Your Provider

Run the system and watch for your provider's output:

```bash
uv run python main.py
```

Look for:

```
Worker started for GitHub (interval=600s)
Worker GitHub: 12 new event(s), 189 total tracked

[2026-02-24 10:15:00] Provider: GitHub
  Product: GitHub Actions
  Status: Degraded performance -- investigating
```

If the provider fails, the worker logs the exception and retries on the
next interval -- it does not crash other providers.
