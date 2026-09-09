"""Idempotent backfills for the data-integrity fixes.

Fixing the parsers only helps rows collected from now on. These backfills repair
what is already stored, and every one of them is safe to re-run: seasons are
derived only where one is missing, a re-ingest replaces a season or a game rather
than appending to it, and play-by-play collection skips games it already has.

Fetching is injected rather than imported so the backfills can be tested without
touching the network; ``src/cli.py`` wires in the real scrapers.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import structlog
from sqlalchemy import text

from .scrapers.nhl_api import season_from_game_id
from .storage.database import Database

logger = structlog.get_logger()

#: Game types that carry play-by-play worth collecting: regular season and playoffs.
COLLECTABLE_GAME_TYPES = ("2", "3")

#: Game states the NHL API uses for a game that has been played.
FINISHED_GAME_STATES = ("OFF", "FINAL")

FetchSeason = Callable[[str], Awaitable[list[dict[str, Any]]]]
FetchGame = Callable[[int], Awaitable[list[dict[str, Any]]]]


@dataclass
class PlayByPlayReport:
    games_collected: int = 0
    games_empty: int = 0
    games_failed: int = 0
    events_written: int = 0
    shifts_written: int = 0
    failures: list[int] = field(default_factory=list)


@dataclass
class ShotsReport:
    seasons_collected: int = 0
    seasons_failed: int = 0
    shots_written: int = 0
    failures: list[str] = field(default_factory=list)


@dataclass
class GamesReport:
    games_written: int = 0
    seasons_failed: int = 0
    games_repaired_from_ids: int = 0
    failures: list[str] = field(default_factory=list)


def repair_game_seasons_from_ids(db: Database) -> int:
    """Fill in ``games.season`` from the game id wherever it is missing.

    NHL game ids encode the season, so this repairs rows without any network call.
    It only touches rows that have no season, which makes it a no-op on a second
    run and keeps it from overwriting a season the API actually reported.
    """
    with db.engine.begin() as conn:
        rows = conn.execute(
            text("SELECT id FROM games WHERE season IS NULL OR season = ''")
        ).fetchall()

        repaired = 0
        for (game_id,) in rows:
            season = season_from_game_id(game_id)
            if season is None:
                continue
            conn.execute(
                text("UPDATE games SET season = :season WHERE id = :id"),
                {"season": season, "id": game_id},
            )
            repaired += 1

    if repaired:
        logger.info("repaired_game_seasons", count=repaired)
    return repaired


def games_needing_play_by_play(
    db: Database,
    seasons: list[str],
    skip_existing: bool = True,
    require_shifts: bool = False,
) -> list[int]:
    """Finished regular-season and playoff games in ``seasons``, oldest first.

    With ``skip_existing`` (the default) games that already have events are left
    out, which is what makes an interrupted backfill resumable and a completed one
    free to re-run.

    ``require_shifts`` also returns games that have events but no shifts. Events
    and shifts are fetched together but stored separately, so a run interrupted
    between the two -- or one made before shifts were collected at all -- would
    otherwise leave those games without shifts permanently. Re-fetching their
    events costs a request and changes nothing, since storage replaces a game.
    """
    if not seasons:
        return []

    season_params = {f"s{i}": s for i, s in enumerate(seasons)}
    type_params = {f"t{i}": t for i, t in enumerate(COLLECTABLE_GAME_TYPES)}
    state_params = {f"g{i}": g for i, g in enumerate(FINISHED_GAME_STATES)}

    sql = (
        "SELECT id FROM games WHERE"
        f" season IN ({', '.join(':' + k for k in season_params)})"
        f" AND game_type IN ({', '.join(':' + k for k in type_params)})"
        f" AND game_state IN ({', '.join(':' + k for k in state_params)})"
    )
    if skip_existing:
        predicates = ["id NOT IN (SELECT DISTINCT game_id FROM play_by_play)"]
        if require_shifts:
            # shifts_checked_at, not the presence of shift rows: some games have
            # no shift chart at all, and those must not be retried forever.
            predicates.append("shifts_checked_at IS NULL")
        sql += " AND (" + " OR ".join(predicates) + ")"
    sql += " ORDER BY id"

    with db.engine.connect() as conn:
        rows = conn.execute(text(sql), {**season_params, **type_params, **state_params}).fetchall()

    return [int(row[0]) for row in rows]


async def backfill_play_by_play(
    db: Database,
    game_ids: list[int],
    fetch_events: FetchGame,
    fetch_shifts: FetchGame | None = None,
    progress_every: int = 100,
) -> PlayByPlayReport:
    """Collect play-by-play (and optionally shifts) for each game.

    Storage replaces a game's rows rather than appending, so re-running over a
    game already collected leaves the same number of rows behind. A game that
    fails is recorded and the run continues -- one 404 in a ten-thousand-game
    backfill must not cost the other 9,999.
    """
    report = PlayByPlayReport()

    for index, game_id in enumerate(game_ids, start=1):
        try:
            events = await fetch_events(game_id)
        except Exception as exc:
            report.games_failed += 1
            report.failures.append(game_id)
            logger.warning("pbp_backfill_game_failed", game_id=game_id, error=str(exc))
            continue

        if not events:
            # Storing zero events would delete anything already collected and make
            # the game look done on the next resumable pass.
            report.games_empty += 1
            logger.warning("pbp_backfill_game_empty", game_id=game_id)
            continue

        report.events_written += db.insert_play_by_play(game_id, events)
        report.games_collected += 1

        if fetch_shifts is not None:
            # Storing shifts is best-effort: the events for this game are already
            # committed, and one unexpected shift payload must not end the run.
            try:
                shifts = await fetch_shifts(game_id)
                # Stored even when empty: that records the attempt, so a game with
                # no shift chart is not re-fetched on every future run.
                report.shifts_written += db.insert_shifts(game_id, shifts)
            except Exception as exc:
                logger.warning("shift_backfill_game_failed", game_id=game_id, error=str(exc))

        if progress_every and index % progress_every == 0:
            logger.info(
                "pbp_backfill_progress",
                done=index,
                total=len(game_ids),
                events=report.events_written,
            )

    return report


async def backfill_shots(
    db: Database,
    seasons: list[str],
    fetch_season_shots: FetchSeason,
) -> ShotsReport:
    """Re-ingest MoneyPuck shot data for each season with the fixed parser.

    This is what actually repairs the 899,651 stored shots: situation, is_home and
    the joinable game id all come from re-parsing the source files. Storage clears
    a season before inserting it, so a re-run replaces rather than duplicates.
    """
    report = ShotsReport()

    for season in seasons:
        try:
            shots = await fetch_season_shots(season)
        except Exception as exc:
            report.seasons_failed += 1
            report.failures.append(season)
            logger.error("shot_backfill_season_failed", season=season, error=str(exc))
            continue

        if not shots:
            # Inserting an empty season would clear the rows we already have.
            report.seasons_failed += 1
            report.failures.append(season)
            logger.error("shot_backfill_season_empty", season=season)
            continue

        report.shots_written += db.insert_shots(shots)
        report.seasons_collected += 1
        logger.info("shot_backfill_season_done", season=season, shots=len(shots))

    return report


async def backfill_games(
    db: Database,
    seasons: list[str],
    fetch_season_games: FetchSeason,
) -> GamesReport:
    """Re-scrape schedules so stored games regain their season and date.

    The date only exists in the schedule payload, so it needs the API. The season
    does not, so anything the API could not supply is repaired from the game id
    afterwards -- that covers seasons older than the ones being scraped.
    """
    report = GamesReport()

    for season in seasons:
        try:
            games = await fetch_season_games(season)
        except Exception as exc:
            report.seasons_failed += 1
            report.failures.append(season)
            logger.error("game_backfill_season_failed", season=season, error=str(exc))
            continue

        if not games:
            report.seasons_failed += 1
            report.failures.append(season)
            logger.warning("game_backfill_season_empty", season=season)
            continue

        report.games_written += db.upsert_games(games)
        logger.info("game_backfill_season_done", season=season, games=len(games))

    report.games_repaired_from_ids = repair_game_seasons_from_ids(db)
    return report
