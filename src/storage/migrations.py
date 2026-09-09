"""In-place schema migrations for an existing nhl.db.

``Base.metadata.create_all`` creates missing *tables* but never alters an existing
one, so the live database (900k shots, 15k games, built before these columns
existed) needs a small, idempotent migration step when it is opened.

Every step here is safe to run repeatedly and never rewrites row data.
"""

import structlog
from sqlalchemy import Connection, Engine, text

logger = structlog.get_logger()

#: ``table -> column -> SQLite column definition`` for columns added after the
#: original schema shipped.
ADDED_COLUMNS: dict[str, dict[str, str]] = {
    "shots": {
        "moneypuck_game_id": "INTEGER",
        "shot_id": "INTEGER",
    },
    "games": {
        "shifts_checked_at": "DATETIME",
    },
}

#: Indexes that must exist on an already-populated table, as
#: ``(index name, table, columns, unique)``. The unique ones are the idempotency
#: guarantee for ingest, so failing to create one is reported loudly.
INDEXES: list[tuple[str, str, str, bool]] = [
    ("ix_shots_moneypuck_game_id", "shots", "moneypuck_game_id", False),
    ("uq_shots_season_game_shot", "shots", "season, moneypuck_game_id, shot_id", True),
    ("uq_pbp_game_event", "play_by_play", "game_id, event_id", True),
    ("uq_shifts_game_player_shift", "shifts", "game_id, player_id, period, shift_number", True),
]


def _table_exists(conn: Connection, table: str) -> bool:
    row = conn.execute(
        text("SELECT 1 FROM sqlite_master WHERE type='table' AND name=:name"),
        {"name": table},
    ).first()
    return row is not None


def _index_exists(conn: Connection, name: str) -> bool:
    row = conn.execute(
        text("SELECT 1 FROM sqlite_master WHERE type='index' AND name=:name"),
        {"name": name},
    ).first()
    return row is not None


def _existing_columns(conn: Connection, table: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(text(f"PRAGMA table_info({table})"))}


def apply_migrations(engine: Engine) -> list[str]:
    """Bring an existing database up to the current schema.

    Returns the names of the steps that actually changed something, so a routine
    open stays quiet and a real migration is logged.
    """
    applied: list[str] = []

    with engine.begin() as conn:
        for table, columns in ADDED_COLUMNS.items():
            if not _table_exists(conn, table):
                continue  # create_all will build it with the current definition
            present = _existing_columns(conn, table)
            for column, coltype in columns.items():
                if column in present:
                    continue
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}"))
                applied.append(f"add_column:{table}.{column}")

    # Each index gets its own transaction: a unique index over a table that already
    # holds duplicates fails, and that must not abort the other steps.
    for name, table, index_columns, unique in INDEXES:
        kind = "UNIQUE INDEX" if unique else "INDEX"
        try:
            with engine.begin() as conn:
                if not _table_exists(conn, table) or _index_exists(conn, name):
                    continue
                conn.execute(text(f"CREATE {kind} {name} ON {table} ({index_columns})"))
        except Exception as exc:
            # Leave the database usable and let `nhl-stats validate` report the
            # missing guarantee, rather than blocking every command that opens it.
            logger.error(
                "migration_index_failed",
                index=name,
                table=table,
                error=str(exc),
                hint="table already contains duplicate rows for this key",
            )
            continue
        applied.append(f"create_index:{name}")

    if applied:
        logger.info("applied_migrations", steps=applied)
    return applied
