from sqlalchemy import Engine, create_engine

from app.config import Settings


def make_engine(settings: Settings) -> Engine:
    return create_engine(
        settings.database_url.get_secret_value(),
        pool_pre_ping=True,
        pool_timeout=settings.database_connect_timeout_seconds,
        connect_args={"connect_timeout": settings.database_connect_timeout_seconds},
        hide_parameters=True,
    )
