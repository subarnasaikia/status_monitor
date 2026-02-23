# Getting Started

## Prerequisites

- Python 3.11 or later
- [uv](https://docs.astral.sh/uv/) package manager

## Installation

```bash
cd status_monitor/

# uv creates the venv and installs dependencies automatically:
uv sync
```

This reads `pyproject.toml`, creates `.venv/`, and installs `httpx` and
`feedparser` from the lockfile.

## Running

```bash
uv run main.py
```

On first run you will see:

```
2026-02-24 00:58:40 [INFO] core.scheduler: Scheduler starting 1 provider worker(s), concurrency limit=20
2026-02-24 00:58:40 [INFO] consumers.base: ConsoleConsumer started, awaiting events
2026-02-24 00:58:40 [INFO] core.scheduler: Worker started for OpenAI (interval=300s)
2026-02-24 00:58:40 [INFO] core.scheduler: Worker OpenAI: 177 new event(s), 177 total tracked

[2026-02-23 16:09:30] Provider: OpenAI
  Product: Conversations
  Status: Elevated Error Rate for ChatGPT Conversations... -- Resolved
```

The system runs continuously.  Press `Ctrl+C` to shut down.

Subsequent poll cycles only print genuinely new events (deduplication
filters out historical entries already seen).

## What Happens at Startup

1. A shared `httpx.AsyncClient` is created (one connection pool)
2. Providers are registered with the `ProviderRegistry`
3. The `EventBus` is created; each consumer subscribes to its own queue
4. The `Scheduler` spawns one worker task per provider
5. Each consumer is launched as an independent `asyncio.Task`
6. All tasks run concurrently via `asyncio.gather()`

## Logging

Logging level and format are configured in `main.py`:

```python
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
```

Set `level=logging.DEBUG` for verbose output including every HTTP request.

## Dependencies

| Package    | Purpose                    |
|------------|----------------------------|
| httpx      | Async HTTP client          |
| feedparser | Atom/RSS feed parsing      |

All other code uses the Python standard library.
