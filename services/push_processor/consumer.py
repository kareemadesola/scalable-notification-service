import asyncio
import os
import sys

import structlog

sys.path.insert(0, "/app/shared")
from base_consumer import BaseConsumer

logger = structlog.get_logger()

MOCK_PUSH = os.environ.get("MOCK_PUSH", "true").lower() == "true"
FCM_SERVER_KEY = os.environ.get("FCM_SERVER_KEY", "")


class PushConsumer(BaseConsumer):
    queue_name = "push"
    dlq_name = "push.dlq"

    async def deliver(self, payload: dict):
        device_token = payload.get("metadata", {}).get("device_token") if payload.get("metadata") else None
        title = payload.get("subject", "Notification")
        body = payload.get("body", "")

        if MOCK_PUSH:
            logger.info(
                "[MOCK] Push notification sent",
                device_token=device_token,
                title=title,
                notification_id=payload.get("notification_id"),
            )
            return

        # Real FCM delivery
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://fcm.googleapis.com/fcm/send",
                headers={
                    "Authorization": f"key={FCM_SERVER_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "to": device_token,
                    "notification": {"title": title, "body": body},
                    "data": payload.get("metadata", {}),
                },
            )
            if response.status_code != 200:
                raise RuntimeError(f"FCM error {response.status_code}: {response.text}")
            result = response.json()
            if result.get("failure", 0) > 0:
                raise RuntimeError(f"FCM delivery failure: {result}")


if __name__ == "__main__":
    asyncio.run(PushConsumer().start())
