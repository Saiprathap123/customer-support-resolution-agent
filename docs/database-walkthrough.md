# Database feature walkthrough

## What changed

The project can now create and version its business tables. It still has no ticket or
refund business endpoint. This milestone creates the storage that those services will use.

| File | Purpose | When it is used |
| --- | --- | --- |
| app/db/models.py | Typed descriptions of tables, statuses, keys and constraints | Application database access and Alembic model comparison |
| alembic.ini | Migration directory location, without passwords | Every Alembic command |
| migrations/env.py | Connects migrations to our validated database configuration | Migration execution and model-drift checks |
| migrations/versions/0001_business_schema.py | Fixed initial schema and protection triggers | Applying/reversing the initial schema version |
| migrations/script.py.mako | Template for later migration revisions | Creating a new migration file |
| tests/integration/conftest.py | Isolated schemas, transactions and synthetic test records | PostgreSQL tests |
| tests/integration/test_schema.py | Real database assertions for constraints and migrations | Local tests and CI |

SQLAlchemy models describe the current desired shape. An Alembic revision describes
a particular change to reach that shape. PostgreSQL stores the actual tables and an
`alembic_version` record. Editing a model alone does not update a running database.

## Relationships using the headphones case

```mermaid
flowchart TD
    Customer[Customer] --> Order[Order and items]
    Order --> Facts[Payment, delivery and return]
    Customer --> Ticket[Support ticket]
    Order --> Ticket
    Ticket --> Run[Workflow run]
    Run --> Proposal[Immutable refund proposal]
    Policy[Versioned policy and chunks] --> Proposal
    Proposal --> Approval[Reviewer decision and expiry]
    Proposal --> Refund[Refund operation and stable key]
    Run --> Audit[Append-only audit events]
```

The proposal stores what we want to do. Approval records who authorized that proposal.
The refund operation tracks what we attempted and what the provider confirmed. They
remain separate because approval, attempt and successful completion are different facts.

## Four constraints worth understanding

1. **Foreign key:** an order must reference an existing customer. Including `tenant_id`
   means it must reference a customer in the same store's scope.
2. **Composite ownership reference:** a ticket includes tenant, order and customer; the
   database rejects a combination that disagrees with the order's owner.
3. **Unique key:** an idempotency key cannot identify two refund operations. This is
   necessary but still needs the provider's own idempotency contract.
4. **Check constraint:** a paid amount of 249900 paise cannot have 249901 paise reserved,
   nor can successful refunds plus reservations exceed the paid amount.

A **trigger** runs inside PostgreSQL when a write occurs. Our evidence-protection
triggers reject changes even when someone bypasses Python and issues ordinary SQL.
They complement application validation; they do not authenticate a reviewer.

## Safe commands

After local setup and `docker compose up -d --wait postgres`:

```powershell
uv run --locked alembic upgrade head
uv run --locked alembic current
uv run --locked alembic check
```

`upgrade head` applies missing migrations. `current` reports the database revision.
`check` asks whether current model metadata would generate additional schema changes.

For tests, create `support_test` once, independently of the application database:

```powershell
docker compose exec -T postgres createdb -U support support_test
$env:TEST_DATABASE_URL = "postgresql+psycopg://support:support-local-only@127.0.0.1:55432/support_test"
uv run --locked pytest -q
```

Tests create and remove only generated `test_schema_<uuid>` schemas within that database.
Do not use downgrade commands on a populated application database to try the round-trip;
the integration test already performs that experiment in an isolated schema.

The next feature will populate realistic synthetic customers, products, orders, payments,
deliveries, returns, policies and tickets so we can inspect these relationships together.
