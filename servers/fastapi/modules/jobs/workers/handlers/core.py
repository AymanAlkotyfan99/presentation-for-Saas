"""Trusted adapters from durable operations to existing business services."""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from enums.async_task_status import AsyncTaskStatus
from modules.jobs.domain.models import QueueClass, RetryClass
from modules.jobs.workers.registry import JobRegistry, OperationDefinition
from modules.jobs.workers.runtime import JobExecutionContext, JobHandlerError
from modules.workspaces.domain.models import Permission


class StrictPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PresentationGenerationPayload(StrictPayload):
    presentation_id: UUID
    legacy_task_id: str = Field(max_length=160)
    request: dict[str, Any]


class TemplateCreationPayload(StrictPayload):
    legacy_task_id: str = Field(max_length=160)
    request: dict[str, Any]


class PresentationExportPayload(StrictPayload):
    presentation_id: UUID
    source_revision: int = Field(ge=0)
    title: str = Field(min_length=1, max_length=256)
    export_as: Literal["pdf", "pptx"]


class WebhookDeliveryPayload(StrictPayload):
    subscription_id: str = Field(min_length=1, max_length=160)
    event: str = Field(min_length=1, max_length=96)
    data: dict[str, Any]


async def presentation_generation_handler(
    context: JobExecutionContext, payload: PresentationGenerationPayload
) -> dict:
    from api.v1.ppt.endpoints.presentation import (
        GeneratePresentationRequest,
        _run_generate_presentation_task,
    )
    from models.sql.async_task import AsyncTaskModel

    await context.heartbeat(2, "Starting presentation generation")
    request = GeneratePresentationRequest.model_validate(payload.request)
    await _run_generate_presentation_task(
        request,
        payload.presentation_id,
        payload.legacy_task_id,
        None,  # Session cookies and bearer credentials never enter durable payloads.
    )
    async with context.worker.session_factory() as session:
        task = await session.get(AsyncTaskModel, payload.legacy_task_id)
        if task is None:
            raise JobHandlerError(
                RetryClass.NON_RETRYABLE_VALIDATION,
                "LEGACY_TASK_NOT_FOUND",
                "Presentation generation compatibility task was not found",
            )
        if task.status == AsyncTaskStatus.ERROR:
            code = str((task.error or {}).get("code") or "PRESENTATION_GENERATION_FAILED")
            raise JobHandlerError(RetryClass.UNKNOWN, code[:96], "Presentation generation failed")
    await context.heartbeat(98, "Presentation generation completed")
    return {"presentationId": str(payload.presentation_id), "legacyTaskId": payload.legacy_task_id}


async def template_creation_handler(
    context: JobExecutionContext, payload: TemplateCreationPayload
) -> dict:
    from api.v1.ppt.endpoints.template import CreateTemplateRequest, _run_create_template_task
    from models.sql.async_task import AsyncTaskModel

    await context.heartbeat(2, "Starting template creation")
    request = CreateTemplateRequest.model_validate(payload.request)
    await _run_create_template_task(payload.legacy_task_id, request)
    async with context.worker.session_factory() as session:
        task = await session.get(AsyncTaskModel, payload.legacy_task_id)
        if task is None:
            raise JobHandlerError(
                RetryClass.NON_RETRYABLE_VALIDATION,
                "LEGACY_TASK_NOT_FOUND",
                "Template compatibility task was not found",
            )
        if task.status == AsyncTaskStatus.ERROR:
            code = str((task.error or {}).get("code") or "TEMPLATE_CREATION_FAILED")
            raise JobHandlerError(RetryClass.UNKNOWN, code[:96], "Template creation failed")
    return {"legacyTaskId": payload.legacy_task_id}


async def presentation_export_handler(
    context: JobExecutionContext, payload: PresentationExportPayload
) -> dict:
    from models.sql.presentation import PresentationModel
    from modules.presentations.revision_service import RevisionConflictError
    from utils.export_utils import export_presentation

    async with context.worker.session_factory() as session:
        presentation = await session.get(PresentationModel, payload.presentation_id)
        if presentation is None or presentation.workspace_id != context.claim.workspace_id:
            raise JobHandlerError(
                RetryClass.NON_RETRYABLE_AUTHORIZATION,
                "PRESENTATION_NOT_FOUND",
                "Presentation was not found",
            )
        if presentation.current_revision != payload.source_revision:
            raise JobHandlerError(
                RetryClass.NON_RETRYABLE_VALIDATION,
                "STALE_SOURCE_REVISION",
                "Export source revision is stale",
            )
    await context.heartbeat(10, "Exporting presentation")
    result = await export_presentation(
        payload.presentation_id,
        payload.title,
        payload.export_as,
        cookie_header=None,
    )
    await context.checkpoint()
    from utils.architecture_flags import object_storage_writes_enabled
    if object_storage_writes_enabled():
        from modules.assets.application.service import add_reference, ingest_file
        from modules.assets.domain.models import RetentionClass

        declared = (
            "application/pdf"
            if payload.export_as == "pdf"
            else "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        )
        async with context.worker.session_factory() as session:
            asset = await ingest_file(
                session,
                path=result.path,
                declared_mime=declared,
                workspace_id=context.claim.workspace_id,
                actor_id=presentation.owner_id,
                actor_service_account_id=None,
                retention_class=RetentionClass.EXPORT,
            )
            await add_reference(
                session,
                asset=asset,
                workspace_id=context.claim.workspace_id,
                resource_type="presentation",
                resource_id=str(payload.presentation_id),
                reference_type="export",
                created_by=presentation.owner_id,
            )
            await session.commit()
        return {"assetId": str(asset.id)}
    return result.model_dump(mode="json")


async def webhook_delivery_handler(
    context: JobExecutionContext, payload: WebhookDeliveryPayload
) -> dict:
    from models.sql.webhook_subscription import WebhookSubscription
    from services.webhook_service import WebhookService

    async with context.worker.session_factory() as session:
        subscription = await session.get(WebhookSubscription, payload.subscription_id)
        if subscription is None or subscription.workspace_id != context.claim.workspace_id:
            raise JobHandlerError(
                RetryClass.NON_RETRYABLE_AUTHORIZATION,
                "WEBHOOK_SUBSCRIPTION_NOT_FOUND",
                "Webhook subscription was not found",
            )
        response = await WebhookService.send_request_to_webhook(subscription, payload.data, raise_for_retry=True)
        if response.status == 429:
            raise JobHandlerError(RetryClass.RATE_LIMIT, "WEBHOOK_RATE_LIMITED", "Webhook endpoint rate limited delivery")
        if response.status >= 500:
            raise JobHandlerError(RetryClass.DEPENDENCY_UNAVAILABLE, "WEBHOOK_SERVER_ERROR", "Webhook endpoint was unavailable")
        if response.status >= 400:
            raise JobHandlerError(RetryClass.NON_RETRYABLE_VALIDATION, "WEBHOOK_REJECTED", "Webhook endpoint rejected delivery")
    return {"subscriptionId": str(payload.subscription_id), "delivered": True}


def register_core_handlers(registry: JobRegistry) -> None:
    definitions = (
        OperationDefinition(
            "presentation.generate", QueueClass.GENERATION,
            PresentationGenerationPayload, presentation_generation_handler, max_attempts=3,
            required_permissions=(Permission.PRESENTATIONS_WRITE,),
        ),
        OperationDefinition(
            "template.create", QueueClass.GENERATION,
            TemplateCreationPayload, template_creation_handler, max_attempts=3,
            required_permissions=(Permission.TEMPLATES_WRITE,),
        ),
        OperationDefinition(
            "presentation.export", QueueClass.EXPORT,
            PresentationExportPayload, presentation_export_handler, max_attempts=3,
            required_permissions=(Permission.PRESENTATIONS_READ,),
        ),
        OperationDefinition(
            "webhook.deliver", QueueClass.WEBHOOK,
            WebhookDeliveryPayload, webhook_delivery_handler, max_attempts=5,
            required_permissions=(Permission.JOBS_WRITE,),
        ),
    )
    for definition in definitions:
        if registry.get(definition.operation) is None:
            registry.register(definition)
