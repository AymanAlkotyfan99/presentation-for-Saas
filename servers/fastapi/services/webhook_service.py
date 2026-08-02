import asyncio
import logging

from sqlmodel import select

from api.operation_security import operation_guard
from enums.webhook_event import WebhookEvent
from models.sql.webhook_subscription import WebhookSubscription
from services.database import get_async_session
from utils.outbound_http import secure_http_request


LOGGER = logging.getLogger(__name__)


class WebhookService:
    @classmethod
    async def send_webhook(cls, event: WebhookEvent, data: dict):
        async for sql_session in get_async_session():
            webhook_subscriptions = await sql_session.scalars(
                select(WebhookSubscription).where(
                    WebhookSubscription.event == event.value
                )
            )
            webhook_subscriptions = list(webhook_subscriptions)
            if not webhook_subscriptions:
                return

            await asyncio.gather(
                *(
                    cls.send_request_to_webhook(subscription, data)
                    for subscription in webhook_subscriptions
                )
            )
            break

    @classmethod
    async def send_request_to_webhook(
        cls, subscription: WebhookSubscription, data: dict
    ):
        headers = {"Content-Type": "application/json"}
        if subscription.secret:
            headers["Authorization"] = f"Bearer {subscription.secret}"

        try:
            async with operation_guard("webhook_delivery"):
                await secure_http_request(
                    "POST",
                    subscription.url,
                    json_body=data,
                    headers=headers,
                    max_response_bytes=1024 * 1024,
                )
        except Exception:
            LOGGER.exception(
                "Webhook delivery failed: subscription_id=%s", subscription.id
            )
