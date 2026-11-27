# Application schema migrations

Run from the repository root with configured `DATABASE_URL`:

```powershell
uv run --locked alembic upgrade head
uv run --locked alembic current
uv run --locked alembic check
```

Create later changes with `uv run --locked alembic revision --autogenerate -m "describe change"`.
Inspect generated SQL, constraints, indexes and downgrade behavior before committing.
Triggers are explicitly versioned in migration scripts; autogeneration does not manage them.
Never import live ORM models inside an existing revision to construct its schema.

`alembic downgrade base` removes the application schema and its data. It is only used
on disposable test schemas here, not on the developer's populated database.

The initial migration includes the original plan's twelve application tables and
three supporting tables: products, payments and deliveries. Embedding storage is
reserved JSONB only; no RAG, vector extension or agent checkpoints are installed.
