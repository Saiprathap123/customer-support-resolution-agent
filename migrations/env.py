"""Use the same validated connection settings as the application."""

from alembic import context

from app.config import get_settings
from app.db.models import Base
from app.db.session import make_engine

config = context.config
target_metadata = Base.metadata


def migrate(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_online() -> None:
    supplied_connection = config.attributes.get("connection")
    if supplied_connection is not None:
        migrate(supplied_connection)
        return
    engine = make_engine(get_settings())
    try:
        with engine.connect() as connection:
            migrate(connection)
    finally:
        engine.dispose()


if context.is_offline_mode():
    context.configure(
        url=get_settings().database_url.get_secret_value(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    run_online()
