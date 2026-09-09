"""Data-integrity checks and the play-by-play corpus assertion.

The 2026-08-17 audit found four defects that had been silently true for the whole
life of the database -- every shot had an empty situation, every game had a NULL
season, no shot joined to a game, and play-by-play held a single season. None of
them raised anything, because nothing ever checked.

``run_integrity_checks`` turns each of those into a check that fails loudly, and
``assert_pbp_corpus`` aborts a run outright when a season the corpus is supposed
to contain is missing or truncated.
"""

from dataclasses import dataclass

import structlog
from sqlalchemy import text

from .database import Database
from .migrations import INDEXES

logger = structlog.get_logger()

#: First season backfilled from the NHL api-web play-by-play endpoint. Coordinates
#: exist from 2010-11, but MoneyPuck shot data (what play-by-play is joined
#: against) starts at 2018-19, so that is where the corpus begins.
EARLIEST_PBP_START_YEAR = 2018

#: A full NHL regular season is 1,271-1,312 games. 2019-20 and 2020-21 were cut
#: short (1,082 and 868), so the floor sits below those.
MIN_GAMES_PER_PBP_SEASON = 800

#: Fraction of a season's played games that must have play-by-play. A handful of
#: games legitimately fail to fetch; half a season is a broken backfill.
MIN_PBP_COVERAGE = 0.95


@dataclass(frozen=True)
class CheckResult:
    """Outcome of a single integrity check."""

    name: str
    passed: bool
    detail: str


class CorpusError(RuntimeError):
    """Raised when the stored corpus is missing seasons it is required to have."""


def expected_pbp_seasons(
    current_season: str,
    earliest_start_year: int = EARLIEST_PBP_START_YEAR,
) -> list[str]:
    """Every 8-digit season id from ``earliest_start_year`` through ``current_season``."""
    last_start_year = int(current_season[:4])
    return [f"{year}{year + 1}" for year in range(earliest_start_year, last_start_year + 1)]


def seasons_requiring_pbp(
    db: Database,
    earliest_start_year: int = EARLIEST_PBP_START_YEAR,
    min_games: int = MIN_GAMES_PER_PBP_SEASON,
) -> list[str]:
    """Seasons whose schedule is complete enough to demand full play-by-play.

    Derived from the stored schedule rather than the calendar: a season still
    being played simply has too few finished games to appear here yet, so the
    October season boundary cannot make the nightly run abort.
    """
    with db.engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT season, COUNT(*) FROM games "
                "WHERE game_type IN ('2', '3') AND game_state IN ('OFF', 'FINAL') "
                "AND season IS NOT NULL AND season != '' "
                "GROUP BY season"
            )
        ).fetchall()

    return sorted(
        str(season)
        for season, played in rows
        if played >= min_games and int(str(season)[:4]) >= earliest_start_year
    )


def _scalar(db: Database, sql: str) -> int:
    with db.engine.connect() as conn:
        return int(conn.execute(text(sql)).scalar() or 0)


def _missing_indexes(db: Database) -> list[str]:
    expected = {name for name, _table, _cols, unique in INDEXES if unique}
    with db.engine.connect() as conn:
        present = {
            row[0]
            for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='index'"))
        }
    return sorted(expected - present)


def run_integrity_checks(db: Database) -> list[CheckResult]:
    """Run every data-integrity check and return one result per check."""
    results: list[CheckResult] = []

    null_seasons = _scalar(db, "SELECT COUNT(*) FROM games WHERE season IS NULL OR season = ''")
    results.append(
        CheckResult(
            "games_season_populated",
            null_seasons == 0,
            f"{null_seasons} games with no season",
        )
    )

    null_dates = _scalar(db, "SELECT COUNT(*) FROM games WHERE game_date IS NULL OR game_date = ''")
    results.append(
        CheckResult(
            "games_date_populated",
            null_dates == 0,
            f"{null_dates} games with no date",
        )
    )

    empty_situations = _scalar(
        db, "SELECT COUNT(*) FROM shots WHERE situation IS NULL OR situation = ''"
    )
    results.append(
        CheckResult(
            "shots_situation_populated",
            empty_situations == 0,
            f"{empty_situations} shots with no situation",
        )
    )

    orphan_shots = _scalar(
        db,
        "SELECT COUNT(*) FROM shots s LEFT JOIN games g ON g.id = s.game_id WHERE g.id IS NULL",
    )
    results.append(
        CheckResult(
            "shots_join_games",
            orphan_shots == 0,
            f"{orphan_shots} shots whose game_id matches no game",
        )
    )

    joined_games = _scalar(
        db,
        "SELECT COUNT(DISTINCT s.game_id) FROM shots s "
        "JOIN games g ON g.id = s.game_id "
        "JOIN play_by_play p ON p.game_id = s.game_id",
    )
    results.append(
        CheckResult(
            "shots_join_play_by_play",
            joined_games > 0,
            f"{joined_games} games join across shots, games and play_by_play",
        )
    )

    missing = _missing_indexes(db)
    results.append(
        CheckResult(
            "unique_ingest_keys",
            not missing,
            f"missing unique indexes: {', '.join(missing)}" if missing else "all present",
        )
    )

    return results


def assert_pbp_corpus(
    db: Database,
    required_seasons: list[str],
    min_games_per_season: int = MIN_GAMES_PER_PBP_SEASON,
    min_coverage: float = MIN_PBP_COVERAGE,
) -> dict[str, int]:
    """Abort the run unless every required season is present in play-by-play.

    A partially-collected corpus is worse than an obviously empty one: analysis
    silently reads whatever happens to be there. Raises ``CorpusError`` naming
    every offending season, and returns the per-season game counts on success.
    """
    with db.engine.connect() as conn:
        counts = {
            str(row[0]): int(row[1])
            for row in conn.execute(
                text(
                    "SELECT g.season, COUNT(DISTINCT p.game_id) "
                    "FROM play_by_play p JOIN games g ON g.id = p.game_id "
                    "GROUP BY g.season"
                )
            )
        }
        played = {
            str(row[0]): int(row[1])
            for row in conn.execute(
                text(
                    "SELECT season, COUNT(*) FROM games "
                    "WHERE game_type IN ('2', '3') AND game_state IN ('OFF', 'FINAL') "
                    "GROUP BY season"
                )
            )
        }

    problems = []
    for season in required_seasons:
        found = counts.get(season, 0)
        scheduled = played.get(season, 0)
        if found == 0:
            problems.append(f"{season}: missing")
        elif found < min_games_per_season:
            problems.append(f"{season}: only {found} games (expected >= {min_games_per_season})")
        elif scheduled and found / scheduled < min_coverage:
            problems.append(
                f"{season}: covers {found} of {scheduled} played games "
                f"({found / scheduled:.0%}, expected >= {min_coverage:.0%})"
            )

    if problems:
        raise CorpusError("play-by-play corpus is incomplete -- " + "; ".join(problems))

    logger.info("pbp_corpus_ok", seasons=len(required_seasons))
    return counts
