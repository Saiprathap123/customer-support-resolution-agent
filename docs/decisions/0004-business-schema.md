# ADR 0004: Tenant-scoped business schema and versioned migrations

Status: implemented for the database feature, 2026-11-25.

## Context

The deterministic workflow needs durable business facts and financial records before
introducing agents. The schema must preserve ownership, approval evidence, operation
identity and audit history even when an application bug attempts an invalid write.

## Decisions

- Use SQLAlchemy typed declarative models with PostgreSQL UUID identifiers, timezone-aware
  timestamps, BIGINT minor-unit amounts and JSONB for structured snapshots/evidence.
- Include `tenant_id` on all 15 application tables. Composite foreign keys include tenant
  identity. Customers are uniquely mapped by tenant and external authentication subject.
- Include the plan's twelve tables plus products, payments and deliveries for required
  catalog/payment/shipping scenarios. Alembic's version table is migration metadata.
- Keep one payment, delivery and whole-order return per order for the initial scope.
- Enforce INR in monetary records, positive paid/proposed/refund amounts, nonnegative
  refunded/reserved counters and `reserved <= paid - refunded`.
- A ticket's customer and order must match. Carry order identity through workflow runs
  and proposals using composite references, preventing a proposal from switching orders.
- Store proposal order, amount, currency and policy reference as explicit columns in
  addition to its JSON payload. A refund operation must match the proposal's tenant,
  order, amount and currency through a composite foreign key.
- Financial action proposals are refunds in this stage. Answer-only results and escalation
  belong in workflow output. New financial action types require explicit schema changes.
- One proposal per workflow run, one approval per proposal and one refund operation per
  proposal. Global uniqueness of stable idempotency keys guards provider request identity.
  A successful operation requires a provider reference, unique within its tenant.
  Rejected, expired or invalidated proposals are replaced by a new proposal/run rather
  than edited in place.
- Approval records bind to the exact stored proposal hash. Pending decisions have no
  reviewer/timestamp; completed decisions require both, within the record's validity period.
- Use text-backed enum checks, not PostgreSQL enum types, for explicit status vocabularies.
- Reserve nullable JSONB embedding storage, with no vector extension, ingestion or RAG.
- Use named constraints and tenant-first lookup indexes so failures and schema changes
  remain understandable.

## Database-enforced evidence protection

The initial migration installs PostgreSQL triggers, independently of ORM behavior:

- Audit events reject ordinary SQL UPDATE, DELETE and TRUNCATE.
- Proposal content is immutable; only status can change.
- Approval binding/lifetime cannot change; a recorded decision cannot be reversed.
- Refund request identity/amount/key cannot change; terminal results cannot reopen.
- Proposals, approvals and refund operations reject DELETE and TRUNCATE.

Triggers are versioned explicitly in migrations. Alembic's model-drift check does not
verify trigger code; integration tests exercise it with direct SQL.

## Migrations and tests

The initial revision is a fixed snapshot, independent of future ORM model changes.
Alembic reads connection settings from the application's validated environment; the
committed INI file contains no credentials. Connections can be supplied by tests.

Integration tests allocate UUID-named schemas inside a separate PostgreSQL test database.
They upgrade, compare model metadata, downgrade and re-upgrade only their own schema.
Other tests use transactions rolled back after each case. No test drops or truncates
the developer's application tables. Connection attempts have bounded timeouts.

Local test connections use IPv4 loopback because this Windows environment can hang on
the `localhost` connection path. Compose remains bound to loopback on host port 55432.

Local verification: 41 tests pass (31 schema cases, 1 connectivity case and 9 foundation
unit cases). Migration upgrade/downgrade/re-upgrade, model-drift checks, ordinary SQL
trigger guards, formatting/lint, offline SQL generation, source/wheel builds and isolated
wheel imports pass. The development database is at `0001_business_schema`. Remote CI
verification remains pending until the database feature PR can be opened.

## Limits of this feature

These are persistence guarantees, not a financial execution service. The schema does
not authenticate users, evaluate the 30-day window/cap, hash/validate proposal contents,
enforce the 24-hour approval policy, call providers, or automatically keep order counters
equal to the sum of refund operations. Future services must perform those checks and
update accounting atomically under order locks before provider calls.

Tenant-scoped references are not full tenant isolation; authenticated scoped queries
and privileges are still required. Production database roles and backup/retention
administration are future deployment work; a privileged database owner can alter or
disable triggers. Policy-version overlap/conflict handling belongs in deterministic
selection and retrieval features; it is not solved by this initial schema.

References:
- https://alembic.sqlalchemy.org/en/latest/tutorial.html
- https://docs.sqlalchemy.org/en/20/core/constraints.html
