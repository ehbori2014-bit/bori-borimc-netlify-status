from collections.abc import Generator
import sqlite3

from .config import Settings, get_settings


def connect(settings: Settings | None = None) -> sqlite3.Connection:
    settings = settings or get_settings()
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(settings.database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_database(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    schema = settings.schema_path.read_text(encoding="utf-8")
    with connect(settings) as connection:
        connection.executescript(schema)
        _apply_light_migrations(connection)


def _has_column(connection: sqlite3.Connection, table: str, column: str) -> bool:
    rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
    return any(row["name"] == column for row in rows)


def _add_column_if_missing(connection: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    if not _has_column(connection, table, column):
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _apply_light_migrations(connection: sqlite3.Connection) -> None:
    _add_column_if_missing(connection, "registration_attempts", "password_hash", "TEXT")
    _add_column_if_missing(connection, "registration_attempts", "password_alg", "TEXT")
    _add_column_if_missing(connection, "registration_attempts", "auto_approved", "INTEGER NOT NULL DEFAULT 0")
    _add_column_if_missing(connection, "registration_bans", "minecraft_name", "TEXT")
    _add_column_if_missing(connection, "registration_bans", "google_email", "TEXT")
    connection.commit()


def get_db() -> Generator[sqlite3.Connection, None, None]:
    connection = connect()
    try:
        yield connection
    finally:
        connection.close()
