# Customer Support Resolution Agent

A planned support resolution product for an electronics retailer: investigate a case,
establish policy and transaction facts, propose a resolution, obtain human approval,
execute safely, and verify the outcome.

## Current status and scope

Engineering foundation plus database schema: typed configuration, a minimal FastAPI
application, PostgreSQL connection/readiness, 15 tenant-scoped application tables,
Alembic migrations, local Compose, locked dependencies and CI. Synthetic seed data,
authentication, ticket endpoints and refund execution are the next features.

The complete prototype targets one electronics retailer and INR, with synthetic records
and mock payment, shipping and ticketing providers. It will handle order status,
returned-item refunds and damaged-item escalation. All refunds require human approval.
The main interface will be a support-team console with a small customer form.

Exclude complex partial returns, chargebacks, fraud adjudication, voice/WhatsApp,
Shopify, MCP, real customer data and live financial operations. Real integrations and
deployment follow prototype validation. Stage 1 has no LLM, RAG, LangGraph, harness or
OpenTelemetry instrumentation. No external provider keys are needed for the foundation.

The earlier untested implementation is preserved locally under ignored `.draft/initial-backend/`.
It is excluded from version control and build artifacts; adoption requires review/tests.

## Architecture

FastAPI validates requests; deterministic services will enforce ownership, business
rules and execution. PostgreSQL will store business facts, approvals, refund operations
and audit events. Provider adapters will initially use mocks. LangGraph, policy retrieval
and model assistance arrive in Stage 2 and cannot replace financial enforcement.

Amounts use integer minor units. The agreed synthetic policy is full-order INR refunds,
return requested within 30 days of delivery, received and inspection passed, a INR 10,000
execution cap and 24-hour human approval. See the decision record for complete conditions.

## Local setup

Prerequisites: Git, uv 0.8.14 (the CI tool version), and Docker with a running Linux
container engine. uv installs Python 3.12 using `.python-version` when necessary.

```powershell
git clone https://github.com/Saiprathap123/customer-support-resolution-agent.git
cd customer-support-resolution-agent
Copy-Item .env.example .env
uv sync --locked
docker compose up -d --wait postgres
uv run --locked alembic upgrade head
uv run --locked uvicorn app.main:create_app --factory --reload --host 127.0.0.1
```

On macOS/Linux, use `cp .env.example .env`; the remaining commands are the same.
Keep the sample database credentials local. If changing the database name, port or
credentials, update both Compose variables and `DATABASE_URL` in `.env`. PostgreSQL
initialization variables apply only when the data volume is first initialized.
The default host port is 55432 to avoid a Windows restriction encountered on 5432;
the container still uses PostgreSQL's port 5432 internally.

API documentation: <http://127.0.0.1:8000/docs>.

- `GET /health`: process liveness; succeeds even if PostgreSQL is unavailable.
- `GET /ready`: executes a database query; returns 503 with `DATABASE_UNAVAILABLE` if
  PostgreSQL cannot be reached. It does not yet validate schema/migration readiness.
- Both endpoints are intentionally unauthenticated and reveal no business data.

Stop PostgreSQL with `docker compose stop postgres`; data is retained in its named volume.

Configuration comes from environment variables and `.env`. Database and Langfuse secrets
are redacted in settings representations. Langfuse variables are reserved configuration;
trace export comes in a later Stage 1 feature. Request logs include generated request
IDs, HTTP method, status and timing, not request bodies or authorization headers. Use
`--no-access-log` with Uvicorn if request URLs/query strings should also be excluded
from its separate access log.

## Checks and tests

```powershell
uv run --locked ruff format --check app tests migrations pyproject.toml
uv run --locked ruff check app tests migrations pyproject.toml
uv run --locked pytest tests/unit -q
# Once only: create the separate test database, not the application database.
docker compose exec -T postgres createdb -U support support_test
$env:TEST_DATABASE_URL = "postgresql+psycopg://support:support-local-only@127.0.0.1:55432/support_test"
uv run --locked pytest tests/integration -m postgres -q
docker compose --env-file .env.example config --quiet
uv build --no-sources
```

For macOS/Linux, set `TEST_DATABASE_URL` using `export TEST_DATABASE_URL='...'`.
Database tests create isolated UUID-named schemas within the separate test database,
exercise migration round trips/constraints and remove only those schemas afterward.
Integration tests skip locally when `TEST_DATABASE_URL` is unset; CI supplies it and
starts its own PostgreSQL service. Unit tests require no running database or model calls.

The workflow runs formatting, lint, unit tests, migrations/model-drift checks, real
PostgreSQL constraint tests, Compose validation, builds and a wheel import on pull requests
and pushes to `main`. This is CI; there is no deployment target or CD rollout yet.

## Migrations and seed data

```powershell
uv run --locked alembic upgrade head
uv run --locked alembic current
uv run --locked alembic check
```

See the [database walkthrough](docs/database-walkthrough.md) for tables, constraints,
test isolation and command explanations. Migration files ship in the repository and
source distribution; run them from the repository/source root. Downgrading to `base`
removes application tables and their data; round-trip tests use isolated schemas only.
Seed data is the next feature; no seed command exists yet.

## Planning documents

- [Original project plan](customer-support-resolution-agent-plan.md)
- [Product blueprint and acceptance scenarios](docs/product-blueprint.md)
- [Architecture proposal and database walkthrough](docs/architecture.md)
- [Milestone backlog and collaboration process](docs/backlog.md)
- [Confirmed interface decision](docs/decisions/0001-support-console.md)
- [Accepted synthetic refund policy](docs/decisions/0002-synthetic-refund-policy.md)
- [Foundation choices and walkthrough](docs/decisions/0003-engineering-foundation.md)
- [Database schema decisions](docs/decisions/0004-business-schema.md)

The original plan is preserved. The blueprint records subsequent scope decisions and
explicit Stage 1 instructions. Architecture items marked proposed remain open for
discussion; writing them down does not establish approval.

No model provider key is needed to build or test the deterministic Stage 1 workflow.
