# Adding a New Consumer

Consumers are reactive workers that process events from the event bus.
The built-in `ConsoleConsumer` prints to stdout; you can add consumers for
Slack, Kafka, databases, webhooks, or anything else.

## Step 1: Create the Consumer

Create a new file in `consumers/`, e.g. `consumers/slack_consumer.py`:

```python
from __future__ import annotations

import httpx

from models.event import StatusEvent
from consumers.base import EventConsumer


class SlackConsumer(EventConsumer):

    def __init__(self, queue, webhook_url: str) -> None:
        super().__init__(queue)
        self._webhook_url = webhook_url
        self._client = httpx.AsyncClient()

    async def process(self, event: StatusEvent) -> None:
        ts = event.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        text = (
            f"*[{ts}]* Provider: {event.provider}\n"
            f"Product: {event.service}\n"
            f"Status: {event.message}"
        )
        await self._client.post(
            self._webhook_url,
            json={"text": text},
        )
```

### Requirements

Your consumer **must**:

- Inherit from `EventConsumer`
- Call `super().__init__(queue)` with its subscriber queue
- Implement the `process(event)` async method

The base class handles the `while True: await queue.get()` loop, error
logging, and `task_done()` bookkeeping.  You only implement `process()`.

## Step 2: Register in main.py

Subscribe to the bus and launch the consumer as a task:

```python
from consumers.slack_consumer import SlackConsumer

# inside async def run():
consumers = [
    ConsoleConsumer(queue=bus.subscribe()),
    SlackConsumer(queue=bus.subscribe(), webhook_url="https://hooks.slack.com/..."),
]
```

Each consumer gets its own independent queue from `bus.subscribe()`.
A slow Slack webhook does not block the console consumer.

## How It Works

```
EventBus.put(event)
    |
    +--> ConsoleConsumer queue  -->  queue.get()  -->  print()
    |
    +--> SlackConsumer queue    -->  queue.get()  -->  POST to webhook
    |
    +--> KafkaConsumer queue    -->  queue.get()  -->  produce to topic
```

Every consumer runs as an independent `asyncio.Task`.  They process events
at their own speed.  If one consumer crashes on a particular event, the
exception is logged and the consumer continues processing the next event.
