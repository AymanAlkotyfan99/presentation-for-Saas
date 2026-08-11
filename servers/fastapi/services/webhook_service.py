import asyncio
import logging
import uuid

from sqlmodel import select

from api.operation_security import operation_guard
from enums.webhook_event import WebhookEvent
from models.sql.webhook_subscription import WebhookSubscription
from services.database import get_async_session
from utils.outbound_http import secure_http_request
from api.v1.auth.context import (
    get_current_owner_id,
    get_current_service_account_id,
)
from utils.architecture_flags import durable_webhooks_enabled


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

            if durable_webhooks_enabled():
                from modules.jobs.application.submit import JobSubmission, submit_job
                from modules.jobs.domain.models import QueueClass

                for subscription in webhook_subscriptions:
                    if subscription.workspace_id is None:
                        LOGGER.warning(
                            "[webhook] durable delivery skipped for unscoped legacy subscription_id=%s",
                            subscription.id,
                        )
                        continue
                    await submit_job(
                        sql_session,
                        JobSubmission(
                            operation="webhook.deliver",
                            queue_class=QueueClass.WEBHOOK,
                            workspace_id=subscription.workspace_id,
                            actor_id=get_current_owner_id(),
                            actor_service_account_id=get_current_service_account_id(),
                            idempotency_scope=f"webhook:{subscription.id}:{event.value}",
                            idempotency_key=uuid.uuid4().hex,
                            payload={
                                "subscription_id": subscription.id,
                                "event": event.value,
                                "data": data,
                            },
                            max_attempts=5,
                            resource_type="webhook_subscription",
                            resource_id=subscription.id,
                        ),
                    )
                await sql_session.commit()
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
        cls, subscription: WebhookSubscription, data: dict, *, raise_for_retry: bool = False
    ):
        headers = {"Content-Type": "application/json"}
        if subscription.secret:
            headers["Authorization"] = f"Bearer {subscription.secret}"

        try:
            async with operation_guard("webhook_delivery"):
                return await secure_http_request(
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
            if raise_for_retry:
                raise
        return None
