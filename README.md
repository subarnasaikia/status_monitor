# Status Monitor

Scalable, event-driven service status monitoring system that tracks incidents
and outages from provider status pages and forwards them to pluggable
consumers.

Ships with an OpenAI status page adapter.  Designed to support 200+
providers without changing core logic.

## Quick Start

```bash
# requires Python 3.11+ and uv
cd status_monitor/
uv sync
uv run python main.py
```

Output:

```
[2026-02-23 16:09:30] Provider: OpenAI
  Product: Conversations
  Status: Elevated Error Rate for ChatGPT Conversations... -- Resolved
```

Press `Ctrl+C` to stop.

## How It Works

Each provider runs as an independent async worker on its own polling
schedule.  New events pass through a deduplication layer and are published
to a fan-out event bus.  Consumers subscribe to the bus and react to events
as they arrive.

```
Provider workers  -->  Dedup  -->  EventBus  -->  Consumer tasks
  (fetch + parse)       (set)     (Queue fan-out)   (print, Slack, ...)
```

- Providers and consumers run as separate `asyncio.Task` instances
- A semaphore caps concurrent HTTP requests (default 20)
- A shared `httpx.AsyncClient` reuses one connection pool
- Each provider declares its own `poll_interval_seconds`
- Slow providers or consumers never block each other

## Project Structure

```
status_monitor/
  models/
    event.py               StatusEvent dataclass
  providers/
    base.py                StatusProvider ABC
    openai_provider.py     OpenAI Atom feed adapter
  core/
    scheduler.py           Per-provider worker coordinator
    event_bus.py           asyncio.Queue fan-out channel
    dedup.py               In-memory deduplication store
    registry.py            Provider registry
  consumers/
    base.py                EventConsumer ABC
    console.py             Terminal output consumer
  docs/
    architecture.md        System design and data flow
    getting-started.md     Installation and running
    adding-a-provider.md   How to integrate a new status page
    adding-a-consumer.md   How to add Slack, Kafka, etc.
    configuration.md       Tunable parameters reference
  main.py                  Entry point
  pyproject.toml           Dependencies and project metadata
```

## Adding a Provider

1. Create `providers/your_provider.py` implementing `StatusProvider`
2. Register it in `main.py`:

```python
from providers.your_provider import YourProvider

registry.register(YourProvider(client=client))
```

See [docs/adding-a-provider.md](docs/adding-a-provider.md) for a full
walkthrough with a GitHub example.

## Adding a Consumer

1. Create `consumers/your_consumer.py` implementing `EventConsumer`
2. Subscribe and launch in `main.py`:

```python
from consumers.your_consumer import YourConsumer

consumers = [
    ConsoleConsumer(queue=bus.subscribe()),
    YourConsumer(queue=bus.subscribe()),
]
```

See [docs/adding-a-consumer.md](docs/adding-a-consumer.md) for a Slack
webhook example.

## Configuration

| Parameter              | Where                    | Default |
|------------------------|--------------------------|---------|
| Concurrency limit      | `Scheduler(concurrency_limit=)` | 20 |
| Per-provider interval  | `provider.poll_interval_seconds` | 300s |
| HTTP timeout           | `httpx.AsyncClient(timeout=)`   | 30s |
| Queue backpressure     | `EventBus(maxsize=)`            | unbounded |
| Log level              | `logging.basicConfig(level=)`   | INFO |

See [docs/configuration.md](docs/configuration.md) for details.

## Dependencies

| Package    | Purpose                |
|------------|------------------------|
| httpx      | Async HTTP client      |
| feedparser | Atom/RSS feed parsing  |

Managed via uv.  No other runtime dependencies.

## Documentation

- [Architecture](docs/architecture.md)
- [Getting Started](docs/getting-started.md)
- [Adding a Provider](docs/adding-a-provider.md)
- [Adding a Consumer](docs/adding-a-consumer.md)
- [Configuration](docs/configuration.md)
