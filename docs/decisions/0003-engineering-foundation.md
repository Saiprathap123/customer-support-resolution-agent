# ADR 0003: Establish a reproducible backend foundation

Status: selected for the agreed foundation milestone, 2026-11-24.

## What and why

Provide a small runnable application and repeatable checks before business tables and
refund logic. A fresh checkout should install the same dependency versions, start local
PostgreSQL and distinguish a running API from one ready to use its database.

## How

- Python 3.12 for this milestone; `.python-version` and the project Python range agree.
- uv 0.8.14, matching the installed local tool, with exact resolved dependencies in
  `uv.lock`. Upgrade deliberately rather than re-resolving dependencies in CI.
- FastAPI application factory; lifespan creates/disposes its SQLAlchemy engine.
- Pydantic Settings validates environment configuration at startup. Database and
  Langfuse credentials are represented with secret types. No authentication scheme
  or privileged API is introduced in this feature.
- PostgreSQL 17 in Docker Compose, loopback-bound port, persistent named volume and
  a container health check. PostgreSQL major-version selection is independent of
  application schema migrations.
- A synchronous database connection for the short readiness query, with bounded
  connection/pool waits. No database transaction spans an external service call.
- `/health` for liveness; `/ready` for a real PostgreSQL query. Readiness returns a
  stable, redacted 503 error when the database is unavailable.
- Basic application logging with a server-generated request ID, method, status and
  duration. Provider calls and business audits do not exist yet.
- GitHub Actions on PRs and main; minimum read permissions, pinned action commit
  revisions, locked install, Ruff, pytest, PostgreSQL, Compose validation, package build
  and installed-wheel import. Do not claim deployment before a target is agreed.

The original plan's SQLAlchemy/Alembic direction remains. Add Alembic with the schema
feature, authentication libraries with authentication, and model tooling in Stage 2.
Avoid installing unused future-stage components in the foundation.

## File walkthrough

| File | Responsibility |
| --- | --- |
| pyproject.toml | Package metadata, dependency ranges, development tools and checks |
| uv.lock | Exact dependency resolution for development and CI |
| .env.example | Public local configuration template; `.env` is ignored |
| docker-compose.yml | Local PostgreSQL service and persistent volume |
| app/config.py | Typed startup configuration and credential redaction |
| app/db/session.py | Configured database engine creation |
| app/main.py | App lifecycle, request logs and health endpoints |
| tests/unit | Configuration, liveness and database-outage behavior |
| tests/integration | Readiness against an actual PostgreSQL server |
| .github/workflows/ci.yml | Automated checks for the committed feature |

## Consequences and limitations

This feature is runnable infrastructure, not a completed Stage 1 workflow. There are no
business tables, migrations, seeds, customer authentication, refund services or UI.
Langfuse configuration is present; export and workflow trace association arrive later.

The earlier draft is preserved outside the package in ignored `.draft/initial-backend`.
It must be reviewed against accepted rules before reuse. Unit tests exercise a deliberately
unreachable local database for failure behavior. CI uses its own PostgreSQL instance;
there are no live payment/model calls or external service credentials.

Verification: 9 unit tests and 1 real PostgreSQL integration test pass locally and on
GitHub's Linux runner. Formatting, lint, Compose validation, distribution builds and
isolated wheel import pass. The first successful CI run is
https://github.com/Saiprathap123/customer-support-resolution-agent/actions/runs/45416835889.
The test client emits an upstream httpx deprecation warning. GitHub also reports the
pinned actions' Node 20 declarations being run under Node 24. Neither warning fails a
check; updating these tool integrations remains maintenance work.

Dependency references consulted during implementation:
- https://docs.astral.sh/uv/guides/integration/github/
- https://docs.pydantic.dev/latest/concepts/pydantic_settings/
- https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
- https://hub.docker.com/_/postgres
