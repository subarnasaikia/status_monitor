# Architecture

## Overview

Status Monitor is an event-driven system that tracks service incidents from
provider status pages (OpenAI, GitHub, AWS, etc.) and forwards them to
pluggable consumers (terminal, Slack, Kafka, etc.).

The architecture separates concerns into three independent layers connected
by an async event bus:

```
Providers (producers)  -->  EventBus (asyncio.Queue)  -->  Consumers (reactive workers)
```

Producers and consumers never reference each other.  The bus is the only
coupling point.

## Runtime Topology

```
main.py creates
 |
 ├── shared httpx.AsyncClient   (one connection pool for all providers)
 ├── EventBus                   (fan-out queue channel)
 ├── DeduplicationStore         (in-memory set)
 ├── Scheduler
 |     ├── worker-OpenAI        (asyncio task, polls every 300s)
 |     ├── worker-GitHub        (asyncio task, polls every 120s)
 |     └── worker-...           (one task per registered provider)
 |
 └── Consumer tasks
       ├── ConsoleConsumer      (asyncio task, awaits queue.get())
       └── SlackConsumer        (asyncio task, awaits queue.get())
```

Every box above runs as an independent `asyncio.Task`.  No task blocks
another.

## Data Flow

```
Provider.fetch_events()
    |
    v
DeduplicationStore.is_new()   -- drops already-seen (provider, event_id) pairs
    |
    v
EventBus.put()                -- copies event into every subscriber queue
    |
    v
Consumer queue.get()          -- each consumer reacts independently
    |
    v
Consumer.process()            -- print, send to Slack, write to Kafka, etc.
```

## Key Components

### StatusEvent (models/event.py)

Frozen dataclass shared by all providers and consumers:

| Field     | Type     | Description                                  |
|-----------|----------|----------------------------------------------|
| id        | str      | Unique within provider (incident ID or composite) |
| provider  | str      | Human-readable provider name                 |
| service   | str      | Affected product/component                   |
| message   | str      | Incident title + latest status               |
| timestamp | datetime | Last-updated time (UTC)                      |

Every provider normalizes its raw data into this model.  Consumers only
depend on `StatusEvent` -- they never see provider-specific formats.

### StatusProvider (providers/base.py)

Abstract base class.  Every provider adapter implements:

- `name` -- human-readable string (e.g. `"OpenAI"`)
- `poll_interval_seconds` -- how often this provider should be polled
- `fetch_events()` -- async method returning `list[StatusEvent]`

A shared `httpx.AsyncClient` is injected via the constructor so all
providers reuse one connection pool.

### Scheduler (core/scheduler.py)

Spawns one long-lived `asyncio.Task` per registered provider (a "worker").
Each worker loop:

1. Acquires a shared `asyncio.Semaphore` (default limit: 20)
2. Calls `provider.fetch_events()`
3. Releases the semaphore
4. Passes results through `DeduplicationStore`
5. Pushes new events into `EventBus`
6. Sleeps for `provider.poll_interval_seconds`

The semaphore prevents more than N concurrent outbound HTTP requests,
avoiding thundering-herd problems at 200+ providers.

The scheduler never touches consumers.

### EventBus (core/event_bus.py)

Fan-out channel.  Each consumer calls `bus.subscribe()` at startup and
receives its own `asyncio.Queue`.  When a producer calls `bus.put(event)`,
the event is copied into every subscriber queue.

A slow consumer fills its own queue but does not block other consumers or
the ingestion pipeline.

### DeduplicationStore (core/dedup.py)

In-memory `set[tuple[str, str]]` keyed on `(provider, event_id)`.  Returns
`True` once per unique pair, `False` on repeats.  Prevents duplicate
terminal output when feeds return historical entries on every poll.

### EventConsumer (consumers/base.py)

Abstract base for reactive consumers.  Each consumer:

- Receives an `asyncio.Queue` in its constructor
- Runs a `while True: event = await queue.get()` loop
- Calls the abstract `process(event)` method

Consumers are launched as independent `asyncio.Task` instances.

### ProviderRegistry (core/registry.py)

Simple list that holds registered `StatusProvider` instances.  The scheduler
reads from it at startup to spawn workers.  Adding a provider means calling
`registry.register(provider)` -- no code changes to scheduler or core.

## Concurrency Model

- All I/O is `async/await` on a single event loop (no threads)
- Provider workers run independently; a slow provider does not block others
- Semaphore caps concurrent network requests (configurable)
- Consumer tasks process events at their own pace
- `asyncio.Queue` provides natural backpressure

## Project Structure

```
status_monitor/
  models/
    event.py               # StatusEvent dataclass
  providers/
    base.py                # StatusProvider ABC
    openai_provider.py     # OpenAI Atom feed adapter
  core/
    scheduler.py           # Provider worker coordinator
    event_bus.py           # Fan-out async queue
    dedup.py               # Deduplication store
    registry.py            # Provider registry
  consumers/
    base.py                # EventConsumer ABC
    console.py             # Terminal output consumer
  main.py                  # Entry point, wiring
  pyproject.toml           # uv project config
```
