# Durable platform foundations

Bayanly's jobs, assets, and provider registry are additive platform modules.
Their rollout flags default to compatibility behavior; enabling a read-facing
feature does not silently migrate existing data or delete legacy records.

## Durable jobs

PostgreSQL is authoritative for jobs, attempts, leases, events, the
transactional outbox, consumer inbox, and dead letters. Redis is transport,
not job truth. Redis Streams consumer groups retain deliveries until explicit
acknowledgement; stale pending entries are reclaimed after the bounded
`JOB_QUEUE_VISIBILITY_SECONDS` interval. Delivery is at least once; operation
idempotency, inbox receipts, lease tokens, and revision pins prevent duplicate
or stale effects. When
`DURABLE_JOBS_ENABLED=true`, the container supervisor starts
`python -m modules.jobs.workers.main` after FastAPI is ready. A shared
`JOB_REDIS_URL` (or the security-control Redis URL) is required.

Core rollout flags are `DURABLE_JOBS_ENABLED`,
`DURABLE_JOBS_BY_OPERATION`, `DURABLE_GENERATION_ENABLED`,
`DURABLE_EXPORTS_ENABLED`, and `DURABLE_WEBHOOKS_ENABLED`. All default false.
The operation-specific flags are effective only when the global durable-jobs
flag is enabled, so a rollout cannot accept durable work without a worker.
Queue-class concurrency, `JOB_LEASE_SECONDS`, and visibility are independently
configurable; an unprocessed SQL inbox receipt is never acknowledged merely
because another worker still owns the lease.

## Managed assets

Asset IDs are the durable identity. The local and S3-compatible providers use
the same private storage contract. Direct S3 uploads are scoped and expiring;
downloads use short-lived capabilities. MIME sniffing, checksum verification,
quarantine, and the scanner boundary run before an asset becomes ready.
Malware scanning in development is deterministic test behavior, not a claim of
production antivirus coverage.

`OBJECT_STORAGE_WRITES_ENABLED`, `DIRECT_UPLOADS_ENABLED`, and
`ASSET_LIBRARY_ENABLED` default false. `LEGACY_PATH_READTHROUGH_ENABLED`
defaults true. Legacy import is dry-run-first and does not delete originals.
Uploads, replacements, thumbnails, deletion, and quarantine scanning fail
closed unless the durable worker platform is enabled.

## Provider registry

Provider accounts and safe configuration are workspace-scoped. Secrets use
AES-256-GCM envelope encryption: a random per-secret data key encrypts the
credential and an external 32-byte master key encrypts the data key. The
database stores ciphertext, nonces, and key-version metadata only.
`PROVIDER_MASTER_KEY` must be URL-safe base64 and decode to exactly 32 bytes;
`PROVIDER_MASTER_KEY_VERSION` identifies the active version. Environment keys
are a deployment-secret boundary, not a production KMS claim.

Routing precedence is emergency disable, configured region status, plan/region
rules, health, configured priority, adapter ID, account UUID, then model.
Fallback is disabled unless both policy and `PROVIDER_FALLBACK_ENABLED` allow
it, and is capped at three fallbacks. Provider/model/capability circuit state is
shared in the database. Provider calls have one executor timeout and no nested
adapter retry loop; durable job retry remains the outer budget.

`PROVIDER_REGISTRY_ENABLED`, `ENCRYPTED_PROVIDER_CONFIG_ENABLED`,
`POLICY_ROUTING_ENABLED`, and `PROVIDER_FALLBACK_ENABLED` default false.
`LEGACY_PROVIDER_SWITCHES_ENABLED` defaults true. Regional status is configured
as `ALLOWED`, `BLOCKED`, `UNKNOWN`, or `ADMIN_REVIEW`; the repository makes no
unsupported country/provider availability claim.
`DISABLED_PROVIDER_ADAPTERS` is a comma-separated operator emergency switch;
account and individual capability switches are available through the registry API.

The legacy settings importer is dry-run-only unless `--apply` is supplied:

```text
python scripts/migrate_provider_settings.py --workspace-id <uuid>
python scripts/migrate_provider_settings.py --workspace-id <uuid> --apply
```

The apply run verifies encrypted round-trip access and retains the legacy
`ProviderSettings` row as rollback evidence. It never prints secret values.
