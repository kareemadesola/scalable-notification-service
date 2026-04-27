import json

import aio_pika
import structlog

from config import settings

logger = structlog.get_logger()

QUEUES = ["email", "sms", "push", "email.dlq", "sms.dlq", "push.dlq"]


class RabbitMQPublisher:
    def __init__(self):
        self._connection = None
        self._channel = None

    async def connect(self):
        self._connection = await aio_pika.connect_robust(settings.rabbitmq_url)
        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=10)

        # Declare all queues (idempotent)
        for queue_name in QUEUES:
            await self._channel.declare_queue(queue_name, durable=True)

        logger.info("RabbitMQ queues declared", queues=QUEUES)

    async def publish(self, queue: str, payload: dict):
        if self._channel is None:
            raise RuntimeError("RabbitMQ publisher is not connected")

        message = aio_pika.Message(
            body=json.dumps(payload).encode(),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,  # survives broker restart
            content_type="application/json",
        )
        await self._channel.default_exchange.publish(message, routing_key=queue)
        logger.info("Message published", queue=queue, notification_id=payload.get("notification_id"))

    async def close(self):
        if self._connection:
            await self._connection.close()
            logger.info("RabbitMQ connection closed")
