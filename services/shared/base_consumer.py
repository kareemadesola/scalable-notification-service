"""
Shared base consumer — all channel processors inherit from this.
Handles:
  - RabbitMQ connection + queue consumption
  - Exponential backoff retry (up to MAX_RETRIES)
  - Dead Letter Queue (DLQ) on final failure
  - PostgreSQL delivery log (notification_logs)
"""
import asyncio
import json
import os
from abc import ABC, abstractmethod

import aio_pika
import asyncpg
import structlog

logger = structlog.get_logger()

RABBITMQ_URL = os.environ["RABBITMQ_URL"]
DATABASE_URL = os.environ["DATABASE_URL"]   # asyncpg DSN
MAX_RETRIES = 3
BASE_BACKOFF = 2  # seconds — doubles each retry: 2, 4, 8


class BaseConsumer(ABC):
    queue_name: str   # set by subclass
    dlq_name: str     # set by subclass

    def __init__(self):
        self._connection = None
        self._channel = None
        self._db_pool = None

    # ── Lifecycle ──────────────────────────────────────────────

    async def start(self):
        self._db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=5)
        self._connection = await aio_pika.connect_robust(RABBITMQ_URL)
        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=10)

        queue = await self._channel.declare_queue(self.queue_name, durable=True)
        await self._channel.declare_queue(self.dlq_name, durable=True)

        logger.info("Consumer started", queue=self.queue_name)
        await queue.consume(self._on_message)

        # Keep running
        await asyncio.Future()

    async def stop(self):
        if self._connection:
            await self._connection.close()
        if self._db_pool:
            await self._db_pool.close()

    # ── Message handling ───────────────────────────────────────

    async def _on_message(self, message: aio_pika.IncomingMessage):
        async with message.process(requeue=False):
            payload = json.loads(message.body)
            notification_id = payload.get("notification_id")
            attempt = payload.get("_attempt", 1)

            log = logger.bind(
                notification_id=notification_id,
                channel=self.queue_name,
                attempt=attempt,
            )

            try:
                await self.deliver(payload)
                await self._write_log(notification_id, "success", attempt, None)
                await self._update_notification_status(notification_id, "delivered")
                log.info("Delivered successfully")

            except Exception as exc:
                log.warning("Delivery failed", error=str(exc))
                await self._write_log(notification_id, "retrying" if attempt < MAX_RETRIES else "failed", attempt, str(exc))

                if attempt < MAX_RETRIES:
                    await self._retry(payload, attempt)
                else:
                    log.error("Max retries reached, sending to DLQ")
                    await self._send_to_dlq(payload)
                    await self._update_notification_status(notification_id, "failed")

    async def _retry(self, payload: dict, attempt: int):
        delay = BASE_BACKOFF ** attempt   # 2s, 4s, 8s
        logger.info("Retrying after backoff", delay=delay, attempt=attempt + 1)
        await asyncio.sleep(delay)
        payload["_attempt"] = attempt + 1
        message = aio_pika.Message(
            body=json.dumps(payload).encode(),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            content_type="application/json",
        )
        await self._channel.default_exchange.publish(message, routing_key=self.queue_name)

    async def _send_to_dlq(self, payload: dict):
        message = aio_pika.Message(
            body=json.dumps(payload).encode(),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            content_type="application/json",
        )
        await self._channel.default_exchange.publish(message, routing_key=self.dlq_name)

    # ── DB helpers ─────────────────────────────────────────────

    async def _write_log(self, notification_id: int, status: str, attempt: int, provider_response: str | None):
        async with self._db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO notification_logs
                    (notification_id, channel, status, attempt_number, provider_response)
                VALUES ($1, $2, $3, $4, $5)
                """,
                notification_id,
                self.queue_name,
                status,
                attempt,
                provider_response,
            )

    async def _update_notification_status(self, notification_id: int, status: str):
        async with self._db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE notifications SET status = $1 WHERE id = $2",
                status,
                notification_id,
            )

    # ── Subclass implements this ────────────────────────────────

    @abstractmethod
    async def deliver(self, payload: dict):
        """Send the notification via the channel-specific provider."""
