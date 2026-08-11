from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CapabilityFamily(str, Enum):
    TEXT = "TEXT"
    IMAGE = "IMAGE"
    SEARCH = "SEARCH"


class RegionPolicyStatus(str, Enum):
    ALLOWED = "ALLOWED"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"
    ADMIN_REVIEW = "ADMIN_REVIEW"


class ProviderHealthStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    UNKNOWN = "UNKNOWN"


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class NormalizedErrorCode(str, Enum):
    TIMEOUT = "TIMEOUT"
    RATE_LIMIT = "RATE_LIMIT"
    AUTHORIZATION = "AUTHORIZATION"
    CAPABILITY_MISMATCH = "CAPABILITY_MISMATCH"
    POLICY_BLOCKED = "POLICY_BLOCKED"
    REGION_UNKNOWN = "REGION_UNKNOWN"
    CIRCUIT_OPEN = "CIRCUIT_OPEN"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    INVALID_RESPONSE = "INVALID_RESPONSE"
    UNKNOWN = "UNKNOWN"


class UsageUnits(BaseModel):
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    images: int | None = Field(default=None, ge=0)
    search_calls: int | None = Field(default=None, ge=0)
    other: dict[str, float] = Field(default_factory=dict)


class CostEstimate(BaseModel):
    amount: float | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, max_length=8)
    pricing_snapshot_id: str | None = None


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TextMessage(StrictRequest):
    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1, max_length=200_000)


class TextAIRequest(StrictRequest):
    messages: list[TextMessage] = Field(min_length=1, max_length=200)
    language: str | None = Field(default=None, max_length=32)
    model: str | None = Field(default=None, max_length=160)
    structured_schema: dict[str, Any] | None = None
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_output_tokens: int | None = Field(default=None, ge=1, le=200_000)
    timeout_seconds: float = Field(default=60, gt=0, le=600)
    # Transitional wire representation for the official llmai compatibility
    # adapter.  Business code still submits a provider-neutral request; only
    # the adapter reconstructs the SDK-specific message/tool objects.
    message_payloads: list[dict[str, Any]] = Field(default_factory=list, max_length=200)
    tools_payload: list[dict[str, Any]] = Field(default_factory=list, max_length=64)
    tool_choice_payload: dict[str, Any] | None = None
    response_format_payload: dict[str, Any] | None = None
    stream_requested: bool = False


class NormalizedToolCall(StrictRequest):
    id: str = Field(min_length=1, max_length=256)
    name: str = Field(min_length=1, max_length=256)
    arguments: str | None = Field(default=None, max_length=200_000)


class TextAIResult(StrictRequest):
    content: str
    structured: dict[str, Any] | None = None
    usage: UsageUnits = Field(default_factory=UsageUnits)
    finish_reason: str | None = None
    model: str
    provider_snapshot_id: UUID | None = None
    cost: CostEstimate = Field(default_factory=CostEstimate)
    tool_calls: list[NormalizedToolCall] = Field(default_factory=list, max_length=64)


class ImageAIRequest(StrictRequest):
    prompt: str = Field(min_length=1, max_length=20_000)
    width: int = Field(default=1024, ge=64, le=4096)
    height: int = Field(default=1024, ge=64, le=4096)
    count: int = Field(default=1, ge=1, le=8)
    quality: str | None = Field(default=None, max_length=64)
    style: str | None = Field(default=None, max_length=64)
    reference_asset_ids: list[UUID] = Field(default_factory=list, max_length=8)
    model: str | None = Field(default=None, max_length=160)
    timeout_seconds: float = Field(default=120, gt=0, le=900)


class ImageAIResult(StrictRequest):
    asset_ids: list[UUID]
    usage: UsageUnits = Field(default_factory=UsageUnits)
    model: str
    provider_snapshot_id: UUID | None = None
    cost: CostEstimate = Field(default_factory=CostEstimate)


class ImageProviderOutput(StrictRequest):
    """Ephemeral adapter output consumed immediately by ProviderExecutor."""

    data: bytes | None = Field(default=None, repr=False)
    url: str | None = Field(default=None, max_length=4096)
    mime_type: str = Field(default="image/png", max_length=128)
    filename: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def exactly_one_source(self):
        if (self.data is None) == (self.url is None):
            raise ValueError("Image provider output requires exactly one byte or URL source")
        return self


class ImageAIAdapterResult(StrictRequest):
    outputs: list[ImageProviderOutput] = Field(min_length=1, max_length=8)
    usage: UsageUnits = Field(default_factory=UsageUnits)
    model: str
    cost: CostEstimate = Field(default_factory=CostEstimate)


class SearchRequest(StrictRequest):
    query: str = Field(min_length=1, max_length=4_000)
    result_count: int = Field(default=8, ge=1, le=30)
    language: str | None = Field(default=None, max_length=32)
    region: str | None = Field(default=None, max_length=32)
    safe_search: bool = True
    timeout_seconds: float = Field(default=30, gt=0, le=120)


class SearchItem(StrictRequest):
    title: str = Field(max_length=512)
    url: str = Field(max_length=4096)
    snippet: str | None = Field(default=None, max_length=10_000)
    published_at: str | None = Field(default=None, max_length=128)


class SearchResult(StrictRequest):
    items: list[SearchItem] = Field(max_length=30)
    usage: UsageUnits = Field(default_factory=lambda: UsageUnits(search_calls=1))
    provider_snapshot_id: UUID | None = None
    cost: CostEstimate = Field(default_factory=CostEstimate)


ProviderRequest = TextAIRequest | ImageAIRequest | SearchRequest
ProviderResult = TextAIResult | ImageAIResult | SearchResult


class ProviderAdapter(Protocol):
    adapter_id: str
    family: CapabilityFamily
    models: tuple[str, ...]
    safe_metadata: dict[str, Any]

    async def execute(self, request: ProviderRequest, *, secret: str | None, safe_config: dict[str, Any]) -> ProviderResult: ...
    async def connection_test(self, *, secret: str | None, safe_config: dict[str, Any], timeout_seconds: float) -> ProviderHealthStatus: ...
