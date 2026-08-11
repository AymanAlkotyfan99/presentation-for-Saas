"""Workspace provider accounts, encrypted secrets, routing, and shared health."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Column, DateTime, Enum as SAEnum, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, event
from sqlalchemy.orm import Mapper
from sqlmodel import Field, SQLModel

from modules.providers.domain.contracts import CapabilityFamily, CircuitState, ProviderHealthStatus, RegionPolicyStatus
from utils.datetime_utils import get_current_utc_datetime


def _enum(enum, name: str):
    return SAEnum(enum, values_callable=lambda values: [item.value for item in values], name=name, native_enum=False, create_constraint=False)


class ProviderAccountModel(SQLModel, table=True):
    __tablename__ = "provider_accounts"
    __table_args__ = (
        UniqueConstraint("workspace_id", "name", name="uq_provider_accounts_workspace_name"),
        Index("ix_provider_accounts_workspace_adapter", "workspace_id", "adapter_id"),
    )
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    workspace_id: UUID = Field(sa_column=Column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False))
    owner_id: UUID | None = Field(default=None, sa_column=Column(ForeignKey("user.id", ondelete="SET NULL"), nullable=True))
    adapter_id: str = Field(sa_column=Column(String(128), nullable=False))
    name: str = Field(sa_column=Column(String(160), nullable=False))
    default_model: str | None = Field(default=None, sa_column=Column(String(160), nullable=True))
    safe_config: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False, default=dict))
    region_policy_status: RegionPolicyStatus = Field(default=RegionPolicyStatus.UNKNOWN, sa_column=Column(_enum(RegionPolicyStatus, "provider_region_status"), nullable=False))
    enabled: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, default=True))
    emergency_disabled: bool = Field(default=False, sa_column=Column(Boolean, nullable=False, default=False))
    created_at: datetime = Field(default_factory=get_current_utc_datetime, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=get_current_utc_datetime, sa_column=Column(DateTime(timezone=True), nullable=False, onupdate=get_current_utc_datetime))


class EncryptedProviderSecretModel(SQLModel, table=True):
    __tablename__ = "encrypted_provider_secrets"
    __table_args__ = (
        UniqueConstraint("provider_account_id", "name", "version", name="uq_provider_secret_version"),
        Index("ix_provider_secrets_active", "provider_account_id", "name", "deleted_at", "version"),
    )
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    provider_account_id: UUID = Field(sa_column=Column(ForeignKey("provider_accounts.id", ondelete="CASCADE"), nullable=False))
    workspace_id: UUID = Field(sa_column=Column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False))
    name: str = Field(sa_column=Column(String(64), nullable=False))
    version: int = Field(sa_column=Column(Integer, nullable=False))
    ciphertext: str = Field(exclude=True, repr=False, sa_column=Column(Text, nullable=False))
    nonce: str = Field(exclude=True, repr=False, sa_column=Column(String(64), nullable=False))
    encrypted_data_key: str = Field(exclude=True, repr=False, sa_column=Column(Text, nullable=False))
    data_key_nonce: str = Field(exclude=True, repr=False, sa_column=Column(String(64), nullable=False))
    master_key_version: str = Field(sa_column=Column(String(64), nullable=False))
    created_at: datetime = Field(default_factory=get_current_utc_datetime, sa_column=Column(DateTime(timezone=True), nullable=False))
    rotated_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    deleted_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))

    def __repr__(self) -> str:
        return f"EncryptedProviderSecretModel(id={self.id!r}, provider_account_id={self.provider_account_id!r}, name={self.name!r}, version={self.version!r}, redacted=True)"


class ProviderCapabilityModel(SQLModel, table=True):
    __tablename__ = "provider_capabilities"
    __table_args__ = (
        UniqueConstraint("provider_account_id", "family", "model", name="uq_provider_capability_model"),
        Index("ix_provider_capabilities_workspace_family", "workspace_id", "family", "enabled"),
    )
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    provider_account_id: UUID = Field(sa_column=Column(ForeignKey("provider_accounts.id", ondelete="CASCADE"), nullable=False))
    workspace_id: UUID = Field(sa_column=Column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False))
    family: CapabilityFamily = Field(sa_column=Column(_enum(CapabilityFamily, "provider_capability_family"), nullable=False))
    model: str = Field(sa_column=Column(String(160), nullable=False))
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False, default=dict))
    enabled: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, default=True))


class ProviderHealthModel(SQLModel, table=True):
    __tablename__ = "provider_health"
    __table_args__ = (UniqueConstraint("provider_account_id", name="uq_provider_health_account"),)
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    provider_account_id: UUID = Field(sa_column=Column(ForeignKey("provider_accounts.id", ondelete="CASCADE"), nullable=False))
    workspace_id: UUID = Field(sa_column=Column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False))
    status: ProviderHealthStatus = Field(default=ProviderHealthStatus.UNKNOWN, sa_column=Column(_enum(ProviderHealthStatus, "provider_health_status"), nullable=False))
    latency_ms: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    safe_error_code: str | None = Field(default=None, sa_column=Column(String(96), nullable=True))
    checked_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class RoutingPolicyModel(SQLModel, table=True):
    __tablename__ = "routing_policies"
    __table_args__ = (UniqueConstraint("workspace_id", "family", name="uq_routing_policy_workspace_family"),)
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    workspace_id: UUID = Field(sa_column=Column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False))
    family: CapabilityFamily = Field(sa_column=Column(_enum(CapabilityFamily, "routing_policy_family"), nullable=False))
    priority_account_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False, default=list))
    allow_fallback: bool = Field(default=False, sa_column=Column(Boolean, nullable=False, default=False))
    max_fallbacks: int = Field(default=0, sa_column=Column(Integer, nullable=False, default=0))
    region_rules: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False, default=dict))
    plan_rules: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False, default=dict))
    version: int = Field(default=1, sa_column=Column(Integer, nullable=False, default=1))
    updated_by: UUID | None = Field(default=None, sa_column=Column(ForeignKey("user.id", ondelete="SET NULL"), nullable=True))
    updated_at: datetime = Field(default_factory=get_current_utc_datetime, sa_column=Column(DateTime(timezone=True), nullable=False, onupdate=get_current_utc_datetime))


class ProviderSnapshotModel(SQLModel, table=True):
    __tablename__ = "provider_snapshots"
    __table_args__ = (Index("ix_provider_snapshots_workspace_created", "workspace_id", "created_at"),)
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    workspace_id: UUID = Field(sa_column=Column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False))
    job_id: UUID | None = Field(default=None, sa_column=Column(ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True))
    provider_account_id: UUID = Field(sa_column=Column(ForeignKey("provider_accounts.id", ondelete="RESTRICT"), nullable=False))
    adapter_id: str = Field(sa_column=Column(String(128), nullable=False))
    family: CapabilityFamily = Field(sa_column=Column(_enum(CapabilityFamily, "provider_snapshot_family"), nullable=False))
    model: str = Field(sa_column=Column(String(160), nullable=False))
    routing_policy_id: UUID | None = Field(default=None, sa_column=Column(ForeignKey("routing_policies.id", ondelete="SET NULL"), nullable=True))
    routing_policy_version: int = Field(default=0, sa_column=Column(Integer, nullable=False, default=0))
    safe_config: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False, default=dict))
    region_decision: RegionPolicyStatus = Field(sa_column=Column(_enum(RegionPolicyStatus, "provider_snapshot_region"), nullable=False))
    fallback_reason: str | None = Field(default=None, sa_column=Column(String(96), nullable=True))
    created_at: datetime = Field(default_factory=get_current_utc_datetime, sa_column=Column(DateTime(timezone=True), nullable=False))


class ProviderCircuitModel(SQLModel, table=True):
    __tablename__ = "provider_circuits"
    __table_args__ = (
        UniqueConstraint("provider_account_id", "family", "model", name="uq_provider_circuit_scope"),
        Index("ix_provider_circuits_workspace_state", "workspace_id", "state"),
    )
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    provider_account_id: UUID = Field(sa_column=Column(ForeignKey("provider_accounts.id", ondelete="CASCADE"), nullable=False))
    workspace_id: UUID = Field(sa_column=Column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False))
    family: CapabilityFamily = Field(sa_column=Column(_enum(CapabilityFamily, "provider_circuit_family"), nullable=False))
    model: str = Field(sa_column=Column(String(160), nullable=False))
    state: CircuitState = Field(default=CircuitState.CLOSED, sa_column=Column(_enum(CircuitState, "provider_circuit_state"), nullable=False))
    failure_count: int = Field(default=0, sa_column=Column(Integer, nullable=False, default=0))
    window_started_at: datetime = Field(default_factory=get_current_utc_datetime, sa_column=Column(DateTime(timezone=True), nullable=False))
    opened_until: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    half_open_probe_until: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    updated_at: datetime = Field(default_factory=get_current_utc_datetime, sa_column=Column(DateTime(timezone=True), nullable=False, onupdate=get_current_utc_datetime))


class ProviderUsageModel(SQLModel, table=True):
    """Append-only, content-free usage/cost hook for later accounting."""

    __tablename__ = "provider_usage_events"
    __table_args__ = (
        Index("ix_provider_usage_workspace_created", "workspace_id", "created_at"),
        Index("ix_provider_usage_account_created", "provider_account_id", "created_at"),
    )
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    workspace_id: UUID = Field(sa_column=Column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False))
    provider_account_id: UUID = Field(sa_column=Column(ForeignKey("provider_accounts.id", ondelete="RESTRICT"), nullable=False))
    provider_snapshot_id: UUID = Field(sa_column=Column(ForeignKey("provider_snapshots.id", ondelete="RESTRICT"), nullable=False))
    job_id: UUID | None = Field(default=None, sa_column=Column(ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True))
    adapter_id: str = Field(sa_column=Column(String(128), nullable=False))
    family: CapabilityFamily = Field(sa_column=Column(_enum(CapabilityFamily, "provider_usage_family"), nullable=False))
    model: str = Field(sa_column=Column(String(160), nullable=False))
    operation: str = Field(sa_column=Column(String(128), nullable=False))
    status: str = Field(sa_column=Column(String(32), nullable=False))
    safe_error_code: str | None = Field(default=None, sa_column=Column(String(96), nullable=True))
    input_tokens: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    output_tokens: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    image_count: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    search_count: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    latency_ms: int = Field(sa_column=Column(Integer, nullable=False))
    estimated_cost: float | None = Field(default=None, sa_column=Column(Float, nullable=True))
    currency: str | None = Field(default=None, sa_column=Column(String(8), nullable=True))
    pricing_snapshot_id: str | None = Field(default=None, sa_column=Column(String(128), nullable=True))
    created_at: datetime = Field(default_factory=get_current_utc_datetime, sa_column=Column(DateTime(timezone=True), nullable=False))


def _immutable(_mapper: Mapper, _connection, target: object) -> None:
    raise ValueError(f"{type(target).__name__} rows are immutable")


event.listen(ProviderSnapshotModel, "before_update", _immutable)
event.listen(ProviderSnapshotModel, "before_delete", _immutable)
event.listen(ProviderUsageModel, "before_update", _immutable)
event.listen(ProviderUsageModel, "before_delete", _immutable)
