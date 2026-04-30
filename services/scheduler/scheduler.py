"""
Scheduler Service
- Polls the notifications table every 60 seconds for rows where:
    status = 'scheduled' AND scheduled_at <= NOW()
- Publishes each due notification to the appropriate RabbitMQ queue
- Updates status to 'queued' after publishing
- In-app scheduled notifications are broadcast directly to the in-app service
"""
import asyncio
import json
import os

import aio_pika
import asyncpg
import httpx
import structlog

logger = structlog.get_logger()

DATABASE_URL = os.environ["DATABASE_URL"]
RABBITMQ_URL = os.environ["RABBITMQ_URL"]
INAPP_SERVICE_URL = os.environ.get("INAPP_SERVICE_URL", "http://inapp_service:8001")
POLL_INTERVAL = int(os.environ.get("SCHEDULER_POLL_INTERVAL", "60"))  # seconds


async def fetch_due_notifications(pool: asyncpg.Pool) -> list[asyncpg.Record]:
    return await pool.fetch(
        """
        SELECT id, user_id, channel, type, subject, body, metadata
        FROM notifications
        WHERE status = 'scheduled'
          AND scheduled_at <= NOW()
        ORDER BY scheduled_at ASC
        LIMIT 500
        """
    )


async def mark_queued(pool: asyncpg.Pool, notification_id: int):
    await pool.execute(
        "UPDATE notifications SET status = 'queued' WHERE id = $1",
        notification_id,
    )


async def mark_failed(pool: asyncpg.Pool, notification_id: int):
    await pool.execute(
        "UPDATE notifications SET status = 'failed' WHERE id = $1",
        notification_id,
    )


async def publish_to_rabbitmq(channel, queue: str, payload: dict):
    message = aio_pika.Message(
        body=json.dumps(payload).encode(),
        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        content_type="application/json",
    )
    await channel.default_exchange.publish(message, routing_key=queue)


async def broadcast_inapp(user_id: str, payload: dict):
    async with httpx.AsyncClient() as client:
        await client.post(
            f"{INAPP_SERVICE_URL}/inapp/broadcast/{user_id}",
            json=payload,
            timeout=2.0,
        )


async def run_scheduler():
    db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=5)
    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    mq_channel = await connection.channel()

    # Ensure queues exist
    for queue_name in ["email", "sms", "push", "email.dlq", "sms.dlq", "push.dlq"]:
        await mq_channel.declare_queue(queue_name, durable=True)

    logger.info("Scheduler started", poll_interval=POLL_INTERVAL)

    try:
        while True:
            due = await fetch_due_notifications(db_pool)

            if due:
                logger.info("Processing due notifications", count=len(due))

            for row in due:
                notification_id = row["id"]
                user_id = str(row["user_id"])
                channel = row["channel"]
                payload = {
                    "notification_id": notification_id,
                    "user_id": user_id,
                    "channel": channel,
                    "type": row["type"],
                    "subject": row["subject"],
                    "body": row["body"],
                    "metadata": (json.loads(row["metadata"]) if isinstance(row["metadata"], str) else dict(row["metadata"])) if row["metadata"] else {},
                }

                try:
                    if channel == "inapp":
                        await broadcast_inapp(user_id, payload)
                    else:
                        await publish_to_rabbitmq(mq_channel, channel, payload)

                    await mark_queued(db_pool, notification_id)
                    logger.info("Scheduled notification dispatched", notification_id=notification_id, channel=channel)

                except Exception as exc:
                    logger.error(
                        "Failed to dispatch scheduled notification",
                        notification_id=notification_id,
                        error=str(exc),
                    )
                    # Leave as 'scheduled' — will retry on next poll

            await asyncio.sleep(POLL_INTERVAL)

    finally:
        await connection.close()
        await db_pool.close()


if __name__ == "__main__":
    asyncio.run(run_scheduler())
