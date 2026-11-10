from __future__ import annotations

import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, event, text

from studio_manager.config import PROJECT_ROOT


def sqlite_url(path: Path) -> str:
    return f"sqlite:///{path.as_posix()}"


def create_database_engine(path: Path) -> Engine:
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(sqlite_url(path), connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def apply_sqlite_safety(dbapi_connection: sqlite3.Connection, _connection_record: object) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=FULL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

    return engine


def alembic_config(database_path: Path) -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", sqlite_url(database_path).replace("%", "%%"))
    return config


def upgrade_database(database_path: Path, revision: str = "head") -> None:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    command.upgrade(alembic_config(database_path), revision)


def downgrade_database(database_path: Path, revision: str = "base") -> None:
    command.downgrade(alembic_config(database_path), revision)


def database_health(engine: Engine) -> dict[str, object]:
    with engine.connect() as connection:
        row = connection.execute(
            text(
                "SELECT "
                "(SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%') AS tables, "
                "(SELECT COUNT(*) FROM alembic_version) AS migration_rows"
            )
        ).one()
        pragmas = {
            "foreign_keys": connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one(),
            "journal_mode": connection.exec_driver_sql("PRAGMA journal_mode").scalar_one(),
            "synchronous": connection.exec_driver_sql("PRAGMA synchronous").scalar_one(),
            "busy_timeout": connection.exec_driver_sql("PRAGMA busy_timeout").scalar_one(),
        }
    expected_pragmas = {"foreign_keys": 1, "journal_mode": "wal", "synchronous": 2, "busy_timeout": 5000}
    return {
        "ok": pragmas == expected_pragmas and row.migration_rows == 1,
        "tables": row.tables,
        "migration_rows": row.migration_rows,
        "pragmas": pragmas,
    }
