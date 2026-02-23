# Configuration

All configuration is currently done in code via `main.py`.  There is no
external config file -- the system is small enough that wiring in code is
clear and type-safe.

## Configurable Parameters

### Concurrency Limit

Controls the maximum number of providers fetching simultaneously.

```python
scheduler = Scheduler(
    registry=registry,
    dedup=dedup,
    bus=bus,
    concurrency_limit=20,   # max concurrent HTTP requests
)
```

With 200 providers and `concurrency_limit=20`, at most 20 will hit the
network at the same time.  The rest wait on the semaphore.

**Guidelines:**

| Provider Count | Suggested Limit |
|----------------|-----------------|
| 1-10           | 10              |
| 10-50          | 20              |
| 50-200         | 20-30           |
| 200+           | 30-50           |

### Per-Provider Poll Interval

Each provider declares its own polling frequency:

```python
class OpenAIProvider(StatusProvider):

    @property
    def poll_interval_seconds(self) -> int:
        return 300  # 5 minutes
```

The default (from the base class) is 300 seconds.  Override in your
provider subclass to customise.

**Guidelines:**

| Status Page Frequency       | Suggested Interval |
|-----------------------------|--------------------|
| Updates multiple times/hour | 120s (2 min)       |
| Updates a few times/day     | 300s (5 min)       |
| Updates rarely              | 600-900s (10-15 min) |

### HTTP Client Timeout

The shared `httpx.AsyncClient` timeout is set in `main.py`:

```python
async with httpx.AsyncClient(timeout=30.0) as client:
    ...
```

Increase this if providers have slow endpoints.  You can also configure
per-request timeouts inside individual provider adapters.

### Event Bus Queue Size

By default, subscriber queues are unbounded.  To add backpressure:

```python
bus = EventBus(maxsize=1000)
```

When a consumer's queue reaches `maxsize`, the `bus.put()` call will
`await` until the consumer drains some events.

### Logging Level

```python
logging.basicConfig(level=logging.INFO)
```

Options:

| Level    | What You See                                   |
|----------|------------------------------------------------|
| DEBUG    | Every HTTP request, every event processed       |
| INFO     | Worker start/stop, poll summaries, new events   |
| WARNING  | Unexpected HTTP status codes, no providers      |
| ERROR    | Fetch failures, consumer processing errors      |

## Registered Providers

Providers are registered in the `run()` function in `main.py`:

```python
registry = ProviderRegistry()
registry.register(OpenAIProvider(client=client))
registry.register(GitHubProvider(client=client))
registry.register(AWSProvider(client=client))
```

Each call adds a provider that the scheduler will spawn a worker for.

## Registered Consumers

Consumers are wired similarly:

```python
consumers = [
    ConsoleConsumer(queue=bus.subscribe()),
    SlackConsumer(queue=bus.subscribe(), webhook_url="..."),
]
```

Each consumer gets its own queue from the bus.  Add or remove consumers by
editing this list.

## Environment Variables (Optional Pattern)

The system does not read environment variables by default, but you can
easily add this pattern:

```python
import os

CONCURRENCY_LIMIT = int(os.getenv("SM_CONCURRENCY_LIMIT", "20"))
SLACK_WEBHOOK = os.getenv("SM_SLACK_WEBHOOK")

scheduler = Scheduler(..., concurrency_limit=CONCURRENCY_LIMIT)

if SLACK_WEBHOOK:
    consumers.append(SlackConsumer(queue=bus.subscribe(), webhook_url=SLACK_WEBHOOK))
```

This keeps the system configurable without an external config file.
