import asyncio
import os
import sys

import structlog

sys.path.insert(0, "/app/shared")
from base_consumer import BaseConsumer

logger = structlog.get_logger()

MOCK_SMS = os.environ.get("MOCK_SMS", "true").lower() == "true"
TWILIO_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM = os.environ.get("TWILIO_FROM_NUMBER", "")


class SMSConsumer(BaseConsumer):
    queue_name = "sms"
    dlq_name = "sms.dlq"

    async def deliver(self, payload: dict):
        to_number = payload.get("metadata", {}).get("to_phone") if payload.get("metadata") else None
        body = payload.get("body", "")

        if MOCK_SMS:
            logger.info(
                "[MOCK] SMS sent",
                to=to_number,
                body=body[:50],
                notification_id=payload.get("notification_id"),
            )
            return

        # Real Twilio delivery
        import httpx
        import base64
        credentials = base64.b64encode(f"{TWILIO_SID}:{TWILIO_TOKEN}".encode()).decode()
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_SID}/Messages.json",
                headers={"Authorization": f"Basic {credentials}"},
                data={"From": TWILIO_FROM, "To": to_number, "Body": body},
            )
            if response.status_code != 201:
                raise RuntimeError(f"Twilio error {response.status_code}: {response.text}")


if __name__ == "__main__":
    asyncio.run(SMSConsumer().start())
