import asyncio
import os
import sys

import structlog

sys.path.insert(0, "/app/shared")
from base_consumer import BaseConsumer

logger = structlog.get_logger()

MOCK_EMAIL = os.environ.get("MOCK_EMAIL", "true").lower() == "true"
SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "")
SENDGRID_FROM = os.environ.get("SENDGRID_FROM_EMAIL", "no-reply@example.com")


class EmailConsumer(BaseConsumer):
    queue_name = "email"
    dlq_name = "email.dlq"

    async def deliver(self, payload: dict):
        to_email = payload.get("metadata", {}).get("to_email") if payload.get("metadata") else None
        subject = payload.get("subject", "(no subject)")
        body = payload.get("body", "")

        if MOCK_EMAIL:
            logger.info(
                "[MOCK] Email sent",
                to=to_email,
                subject=subject,
                notification_id=payload.get("notification_id"),
            )
            return

        # Real SendGrid delivery
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers={"Authorization": f"Bearer {SENDGRID_API_KEY}"},
                json={
                    "personalizations": [{"to": [{"email": to_email}]}],
                    "from": {"email": SENDGRID_FROM},
                    "subject": subject,
                    "content": [{"type": "text/plain", "value": body}],
                },
            )
            if response.status_code not in (200, 202):
                raise RuntimeError(f"SendGrid error {response.status_code}: {response.text}")


if __name__ == "__main__":
    asyncio.run(EmailConsumer().start())
