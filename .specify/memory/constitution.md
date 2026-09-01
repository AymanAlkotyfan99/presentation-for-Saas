<!--
Sync Impact Report
- Version change: unratified Spec Kit scaffold -> 1.0.0
- Modified principles:
  - Placeholder Principle 1 -> I. Brownfield Truth and Preservation
  - Placeholder Principle 2 -> II. Canonical Architecture and Domain Integrity
  - Placeholder Principle 3 -> III. Backend Security and Tenant Authority
  - Placeholder Principle 4 -> IV. Controlled External and Durable Effects
  - Placeholder Principle 5 -> V. Reversible State and Contract Evolution
  - Added VI. Bilingual Product Integrity
  - Added VII. Evidence and Honest Quality Gates
  - Added VIII. Repository and Supply-Chain Stewardship
- Added sections: Engineering Authority and State; Delivery and Evidence
- Removed sections: template examples and placeholder content
- Follow-up TODOs: none
-->

# Bayanly Engineering Constitution

## Core Principles

### I. Brownfield Truth and Preservation

Every specification, plan, task set, implementation, and convergence pass MUST begin from
repository evidence: current code, tests, migrations, configuration, feature flags, branch state,
and relevant diffs. Existing user work and supported compatibility behavior MUST be preserved;
unrelated cleanup, reformatting, or scope expansion MUST NOT be folded into a change.

Current implementation, feature-flagged foundations, legacy compatibility, and roadmap-only work
MUST be identified separately. `Sprint_exeuteive.md` supplies sequencing context, never proof that
planned behavior exists. The detailed read-before-write procedure is defined by `AGENTS.md`.

### II. Canonical Architecture and Domain Integrity

Changes MUST extend Bayanly's existing module, persistence, job, storage, provider, renderer, and
API boundaries rather than create competing abstractions. Transport and UI layers MUST NOT become
owners of domain behavior or authorization. Public APIs, schemas, persistence formats, subsystem
names, compatibility facades, and rollout defaults MUST change only through explicit approved
scope with migration and rollback evidence.

Presentation behavior MUST preserve the versioned presentation document, command, revision, and
renderer boundaries. Renderer state, resolved or signed URLs, local paths, provider payloads, and
executable content MUST NOT become canonical presentation truth.

### III. Backend Security and Tenant Authority

FastAPI MUST remain authoritative for authentication, authorization, ownership, workspace
membership, RBAC, service-account scopes, and administrator access. Every protected read, write,
export, asset, job, and provider action MUST enforce the applicable owner or workspace predicate
at the backend boundary. Frontend guards, hidden controls, client identifiers, and signed URLs
MUST NOT be treated as authorization; cross-tenant failures MUST remain enumeration-resistant.

Administrator capabilities MUST remain separate from normal-user and non-browser authority.
Secrets, credentials, prompts, presentation or uploaded content, provider responses, signed URLs,
and local paths MUST NOT enter logs, analytics, durable payloads, or public errors. Detailed trust
boundaries and accepted gaps are governed by `SECURITY.md`. Existing outbound-request,
safe-rendering, path-containment, Electron IPC-sender, operation-control, and security-header
protections MUST NOT be weakened; known gaps MUST remain documented until they are implemented.

### IV. Controlled External and Durable Effects

New or migrated AI execution MUST use `modules/providers`; user- or configuration-influenced
outbound URLs MUST use `utils/outbound_http.py` or an explicitly reviewed equivalent; durable work
MUST use `modules/jobs` and its canonical job/outbox model when enabled; managed files MUST use
asset IDs and `modules/assets`. A second provider executor, outbound security client, queue, durable
status system, or object-store abstraction MUST NOT be introduced.

Retries, fallback, concurrency, payloads, responses, and resource use MUST be finite and bounded.
At-least-once handlers MUST be idempotent, revalidate current authority and source revision, and
keep payloads secret-free. Provider fallback MUST NOT multiply job retries, and transport or
storage adapter retries MUST NOT compete with the owning application retry policy.

### V. Reversible State and Contract Evolution

Persistent schema evolution MUST use the single Alembic graph, preserve existing data, and include
supported-database migration evidence; startup `create_all` MUST NOT substitute for a migration.
Cutovers MUST retain safe defaults, compatibility windows, reconciliation, observable rollback,
and delayed destructive cleanup. Feature flags MUST fail safely and MUST NOT be bypassed by direct
calls into staged implementations.

Versioned schemas, generated contracts, product metadata, and other generated artifacts MUST be
changed through their owning source and generator, then verified with the repository check mode.
Breaking API, document, persistence, or operator-contract changes MUST be intentional, documented,
and accompanied by a migration or compatibility plan.

### VI. Bilingual Product Integrity

English LTR and Arabic RTL behavior are product invariants. User-facing changes MUST use the
canonical catalogs with matching keys and interpolation variables, correct `lang` and `dir`,
logical-direction UI behavior, safe plain-text rendering, and equivalent loading, empty, failure,
keyboard, accessibility, and responsive states in both locales.

Application-shell direction and presentation-content direction MUST remain independent. Arabic UI
MUST NOT mirror physical slide geometry, element order, or canvas coordinates. Localization and
RTL/LTR validation MUST be included whenever a change can affect visible copy, routing, layout,
rendering, editing, or export.

### VII. Evidence and Honest Quality Gates

A defect fix MUST start with a reproducible failing case or concrete root-cause evidence, change
the narrowest responsible boundary, and add or update regression validation. Specifications and
plans MUST define observable acceptance evidence; implementation claims MUST be supported by the
deterministic checks required by `TESTING.md` for the affected scope.

Mandatory failures MUST remain visible. Work MUST NOT weaken assertions, add unjustified skips or
xfails, conceal failures with continue-on-error, or claim a gate is green when it is not. Skipped,
blocked, or environment-limited checks MUST be reported with the exact reason. Validation MUST NOT
invoke real paid providers, production secrets, or destructive production resources.

### VIII. Repository and Supply-Chain Stewardship

Dependencies MUST be added only to the owning manifest, justified against existing capability,
locked through the established toolchain, and reviewed for provenance, license, vulnerability,
transitive, platform, and maintenance risk. External actions and runtime artifacts MUST retain
the repository's pinning, checksum, least-permission, and provenance controls. Standard-library
governance checks MUST be preferred when practical.

The maintained branches are exactly `dev`, `staging`, and `production`; there is no `main` branch,
and sprint or feature branches MUST NOT become policy. Agents MUST NOT create or switch branches,
reset, restore, stash, clean, rebase, merge, commit, push, force-push, tag, or otherwise mutate Git
history unless the user explicitly requests that exact action. Documentation, specifications,
tests, configuration, and generated contracts MUST remain synchronized with the behavior changed.

## Engineering Authority and State

Within Bayanly repository governance, after applicable system and explicit user instructions, the
authority hierarchy is:

1. This constitution: the highest-level, durable engineering law.
2. `AGENTS.md` and applicable nested `AGENTS.md` files: mandatory agent operating rules that may
   add scope-specific constraints but MUST NOT weaken higher rules.
3. `ARCHITECTURE.md`, `SECURITY.md`, `CODESTYLE.md`, and `TESTING.md`: the detailed engineering
   sources of truth for current boundaries, protections and gaps, conventions, and quality gates.
4. A feature's specification, plan, and tasks: change-specific execution artifacts constrained by
   every level above.
5. `Sprint_exeuteive.md`: product roadmap and sequencing context, not implementation evidence or
   authority to bypass an engineering invariant.

A feature specification or implementation MUST NOT silently override this constitution or the
detailed engineering sources of truth. When sources disagree with roadmap language, current code,
tests, migrations, configuration, and the detailed sources control. Every change artifact MUST
label relevant claims as CURRENT IMPLEMENTATION, FEATURE-FLAGGED FOUNDATION, LEGACY COMPATIBILITY,
or ROADMAP-ONLY so planned cutovers are not represented as production authority.

## Delivery and Evidence

Specifications MUST define scope and exclusions, repository evidence, the owning architecture,
security and tenant effects, persistent-data and rollback implications, bilingual product impact,
and measurable acceptance criteria. Plans MUST include a constitution check before research or
design and again after design. Tasks MUST carry the required tests, generators, documentation,
migration, and rollout work rather than defer mandatory quality to an unspecified later change.

Implementation and convergence MUST preserve existing work, keep changes narrow, run the checks
required by `TESTING.md`, review `git diff --check`, the final diff, and exact final Git status, and
report every unexecuted or failing gate. A check is evidence only for the state and environment in
which it ran; mocked or unit evidence MUST NOT be presented as proof of a production cutover.

At ratification on 2026-08-30, `TESTING.md` records a targeted FastAPI platform/security result of
147 passed, 1 skipped, and 3 failed, and records `servers/fastapi/openai_spec.json` as stale. These
are known remediation blockers, not constitutional violations that prevent adoption and not
permission to weaken a gate. Until separately remediated, they MUST remain active, be reported
accurately, and prevent claims that the complete CI or OpenAPI baseline is green.

## Governance

Every Spec Kit specification, plan, task set, implementation, analysis, and convergence review
MUST demonstrate compliance with this constitution and cite the detailed source that governs each
material boundary. A conflict MUST be resolved by changing the lower-level artifact or by an
explicit constitution amendment; schedules, feature text, and implementation convenience cannot
waive an invariant.

Amendments MUST modify this file explicitly, state the rationale and compatibility impact, update
the Sync Impact Report, identify affected engineering sources and execution artifacts, and include
any required migration, rollout, or remediation plan. An amendment requires explicit approval from
the repository owner through the requested change; it MUST NOT be inferred from roadmap wording.

Constitution versions use semantic versioning:

- MAJOR: a breaking governance change, removal, or incompatible redefinition of a principle.
- MINOR: a new principle or materially expanded governance requirement.
- PATCH: a clarification or correction that does not alter required meaning.

The ratification date records initial adoption. The last-amended date changes only when the
constitution changes. Compliance review MUST use the current version and MUST never hide a known
exception; unresolved exceptions require an owner and explicit remediation evidence in the
appropriate detailed source or change artifact.

**Version**: 1.0.0 | **Ratified**: 2026-08-30 | **Last Amended**: 2026-08-30
