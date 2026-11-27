from pathlib import Path

from alembic.config import Config
from sqlalchemy import Connection


def migration_config(connection: Connection) -> Config:
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.attributes["connection"] = connection
    return config
