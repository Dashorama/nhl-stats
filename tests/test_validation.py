"""Tests for the data-integrity checks and the corpus assertion.

These are the guards that stop the four audit findings from silently coming back:
a run must fail if situations go empty, if a season goes NULL, if shots stop
joining to games, or if a whole season disappears from play-by-play.
"""

import sqlite3

import pytest

from src.storage.database import Database
from src.storage.validation import (
    CorpusError,
    assert_pbp_corpus,
    run_integrity_checks,
    seasons_requiring_pbp,
)

GAME = {
    "id": 2024020001,
    "season": "20242025",
    "date": "2024-10-04",
    "game_type": 2,
    "home_team": "BUF",
    "away_team": "NJD",
    "home_score": 3,
    "away_score": 4,
    "game_state": "OFF",
}

SHOT = {
    "season": "2024",
    "game_id": 2024020001,
    "moneypuck_game_id": 20001,
    "shot_id": 0,
    "team": "NJD",
    "situation": "5v5",
    "is_home": False,
    "goal": 0,
}

EVENT = {"event_id": 51, "event_type": "faceoff", "period": 1}


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "test.db")


@pytest.fixture
def healthy_db(db):
    db.upsert_games([GAME])
    db.insert_shots([SHOT])
    db.insert_play_by_play(2024020001, [EVENT])
    return db


def _check(results, name):
    matched = [r for r in results if r.name == name]
    assert matched, f"no check named {name} in {[r.name for r in results]}"
    return matched[0]


class TestIntegrityChecks:
    def test_a_healthy_database_passes_every_check(self, healthy_db):
        results = run_integrity_checks(healthy_db)
        assert results, "expected at least one check"
        assert all(r.passed for r in results), [r for r in results if not r.passed]

    def test_a_null_game_season_fails(self, healthy_db):
        with sqlite3.connect(healthy_db.db_path) as conn:
            conn.execute("UPDATE games SET season = NULL")
        assert not _check(run_integrity_checks(healthy_db), "games_season_populated").passed

    def test_a_game_that_was_never_played_needs_no_date(self, healthy_db):
        """Conditional playoff games (a game 7 that was not needed) have no date."""
        healthy_db.upsert_games(
            [{**GAME, "id": 2025030117, "season": "20252026", "game_state": "FUT", "date": None}]
        )
        assert _check(run_integrity_checks(healthy_db), "games_date_populated").passed

    def test_a_played_game_with_no_date_fails(self, healthy_db):
        healthy_db.upsert_games(
            [{**GAME, "id": 2025020117, "season": "20252026", "game_state": "OFF"}]
        )
        with sqlite3.connect(healthy_db.db_path) as conn:
            conn.execute("UPDATE games SET game_date = NULL WHERE id = 2025020117")
        assert not _check(run_integrity_checks(healthy_db), "games_date_populated").passed

    def test_a_null_game_date_fails(self, healthy_db):
        with sqlite3.connect(healthy_db.db_path) as conn:
            conn.execute("UPDATE games SET game_date = NULL")
        assert not _check(run_integrity_checks(healthy_db), "games_date_populated").passed

    def test_an_empty_shot_situation_fails(self, healthy_db):
        with sqlite3.connect(healthy_db.db_path) as conn:
            conn.execute("UPDATE shots SET situation = ''")
        assert not _check(run_integrity_checks(healthy_db), "shots_situation_populated").passed

    def test_a_null_shot_situation_fails(self, healthy_db):
        with sqlite3.connect(healthy_db.db_path) as conn:
            conn.execute("UPDATE shots SET situation = NULL")
        assert not _check(run_integrity_checks(healthy_db), "shots_situation_populated").passed

    def test_a_moneypuck_game_id_left_in_the_join_column_fails(self, healthy_db):
        """The exact broken state the audit found: 5-digit ids that join to nothing."""
        with sqlite3.connect(healthy_db.db_path) as conn:
            conn.execute("UPDATE shots SET game_id = 20001")
        result = _check(run_integrity_checks(healthy_db), "shots_join_games")
        assert not result.passed
        assert "1" in result.detail  # reports the orphan count

    def test_shots_with_no_play_by_play_for_the_same_game_fails(self, healthy_db):
        with sqlite3.connect(healthy_db.db_path) as conn:
            conn.execute("DELETE FROM play_by_play")
        assert not _check(run_integrity_checks(healthy_db), "shots_join_play_by_play").passed

    def test_missing_unique_ingest_keys_fail(self, healthy_db):
        with sqlite3.connect(healthy_db.db_path) as conn:
            conn.execute("DROP INDEX uq_pbp_game_event")
        result = _check(run_integrity_checks(healthy_db), "unique_ingest_keys")
        assert not result.passed
        assert "uq_pbp_game_event" in result.detail


class TestCorpusAssertion:
    def _load_pbp(self, db, seasons, games_per_season):
        for season in seasons:
            start = int(season[:4])
            for n in range(1, games_per_season + 1):
                game_id = start * 1000000 + 20000 + n
                db.upsert_games([{**GAME, "id": game_id, "season": season}])
                db.insert_play_by_play(game_id, [EVENT])

    def test_passes_when_every_required_season_is_present(self, db):
        self._load_pbp(db, ["20232024", "20242025"], games_per_season=3)
        assert_pbp_corpus(db, ["20232024", "20242025"], min_games_per_season=3)

    def test_aborts_when_a_season_is_missing_entirely(self, db):
        self._load_pbp(db, ["20242025"], games_per_season=3)
        with pytest.raises(CorpusError) as exc:
            assert_pbp_corpus(db, ["20232024", "20242025"], min_games_per_season=3)
        assert "20232024" in str(exc.value)

    def test_aborts_when_a_season_is_present_but_short(self, db):
        self._load_pbp(db, ["20232024", "20242025"], games_per_season=3)
        with pytest.raises(CorpusError) as exc:
            assert_pbp_corpus(db, ["20232024", "20242025"], min_games_per_season=5)
        assert "20232024" in str(exc.value)
        assert "3" in str(exc.value)

    def test_names_every_offending_season_not_just_the_first(self, db):
        self._load_pbp(db, ["20242025"], games_per_season=3)
        with pytest.raises(CorpusError) as exc:
            assert_pbp_corpus(db, ["20212022", "20222023", "20242025"], min_games_per_season=3)
        message = str(exc.value)
        assert "20212022" in message
        assert "20222023" in message

    def test_an_empty_database_aborts(self, db):
        with pytest.raises(CorpusError):
            assert_pbp_corpus(db, ["20242025"], min_games_per_season=1)


class TestMigrationLeavesADatabaseUsableWhenDuplicatesBlockAUniqueIndex:
    def test_database_still_opens_and_validation_reports_the_missing_key(self, tmp_path):
        path = tmp_path / "dupes.db"
        conn = sqlite3.connect(path)
        conn.execute(
            "CREATE TABLE play_by_play ("
            " id INTEGER PRIMARY KEY AUTOINCREMENT, game_id INTEGER, event_id INTEGER)"
        )
        conn.executemany(
            "INSERT INTO play_by_play (game_id, event_id) VALUES (?, ?)",
            [(2025020001, 51), (2025020001, 51)],
        )
        conn.commit()
        conn.close()

        db = Database(path)  # must not raise

        result = _check(run_integrity_checks(db), "unique_ingest_keys")
        assert not result.passed
        assert "uq_pbp_game_event" in result.detail


class TestSeasonsRequiringPbp:
    """The required-season list is derived from the schedule, so an in-progress
    season never trips the floor and a fully-played one can never be skipped."""

    def _load_games(self, db, season, count, state="OFF"):
        start = int(season[:4])
        db.upsert_games(
            [
                {**GAME, "id": start * 1000000 + 20000 + n, "season": season, "game_state": state}
                for n in range(1, count + 1)
            ]
        )

    def test_lists_seasons_whose_schedule_is_complete(self, db):
        self._load_games(db, "20232024", 5)
        self._load_games(db, "20242025", 5)

        seasons = seasons_requiring_pbp(db, earliest_start_year=2023, min_games=5)

        assert seasons == ["20232024", "20242025"]

    def test_excludes_a_season_that_has_not_been_fully_played(self, db):
        self._load_games(db, "20232024", 5)
        self._load_games(db, "20242025", 2)

        seasons = seasons_requiring_pbp(db, earliest_start_year=2023, min_games=5)

        assert seasons == ["20232024"]

    def test_excludes_seasons_before_the_backfill_window(self, db):
        self._load_games(db, "20152016", 5)
        self._load_games(db, "20232024", 5)

        seasons = seasons_requiring_pbp(db, earliest_start_year=2018, min_games=5)

        assert seasons == ["20232024"]

    def test_ignores_games_that_have_not_been_played(self, db):
        self._load_games(db, "20242025", 5, state="FUT")

        assert seasons_requiring_pbp(db, earliest_start_year=2018, min_games=5) == []


class TestCorpusCoverage:
    def test_aborts_when_a_season_is_only_partially_collected(self, db):
        db.upsert_games(
            [
                {**GAME, "id": 2024020000 + n, "season": "20242025", "game_state": "OFF"}
                for n in range(1, 11)
            ]
        )
        for n in range(1, 6):  # events for only half the played games
            db.insert_play_by_play(2024020000 + n, [EVENT])

        with pytest.raises(CorpusError) as exc:
            assert_pbp_corpus(db, ["20242025"], min_games_per_season=1, min_coverage=0.95)

        assert "20242025" in str(exc.value)

    def test_accepts_a_season_collected_above_the_coverage_floor(self, db):
        db.upsert_games(
            [
                {**GAME, "id": 2024020000 + n, "season": "20242025", "game_state": "OFF"}
                for n in range(1, 11)
            ]
        )
        for n in range(1, 11):
            db.insert_play_by_play(2024020000 + n, [EVENT])

        assert_pbp_corpus(db, ["20242025"], min_games_per_season=1, min_coverage=0.95)


class TestHomeAwayBalance:
    """The is_home defect (every 2018-2024 shot stored as away) had no guard.

    parse_moneypuck_flag returns False for anything it cannot parse, so if
    MoneyPuck switched isHomeTeam to "True"/"False" every shot would silently
    become an away shot again and every other check would stay green.
    """

    def _shots(self, db, season, home, away):
        rows = [
            {
                **SHOT,
                "season": season,
                "moneypuck_game_id": 20000 + i,
                "shot_id": i,
                "is_home": i < home,
            }
            for i in range(home + away)
        ]
        db.insert_shots(rows)

    def test_a_realistic_split_passes(self, db):
        self._shots(db, "2024", home=306, away=294)  # 51% home
        assert _check(run_integrity_checks(db), "shots_home_away_balance").passed

    def test_every_shot_stored_as_away_fails(self, db):
        self._shots(db, "2024", home=0, away=600)
        result = _check(run_integrity_checks(db), "shots_home_away_balance")
        assert not result.passed
        assert "2024" in result.detail

    def test_every_shot_stored_as_home_fails(self, db):
        self._shots(db, "2024", home=600, away=0)
        assert not _check(run_integrity_checks(db), "shots_home_away_balance").passed

    def test_a_season_too_small_to_judge_is_not_flagged(self, db):
        self._shots(db, "2024", home=0, away=5)
        assert _check(run_integrity_checks(db), "shots_home_away_balance").passed


class TestSituationPlausibility:
    """Non-empty is not enough: a semantic regression (say MoneyPuck starts
    counting the goalie, making everything 6v6) would leave the presence check
    green while every downstream situation query is wrong."""

    def _shots(self, db, situations):
        db.insert_shots(
            [
                {**SHOT, "moneypuck_game_id": 20000 + i, "shot_id": i, "situation": s}
                for i, s in enumerate(situations)
            ]
        )

    def test_real_situations_pass(self, db):
        self._shots(db, ["5v5"] * 900 + ["5v4"] * 60 + ["6v5"] * 40)
        assert _check(run_integrity_checks(db), "shots_situation_plausible").passed

    def test_a_trace_of_upstream_garbage_is_tolerated(self, db):
        """MoneyPuck itself ships a handful of impossible rows (7v5, 5v9)."""
        self._shots(db, ["5v5"] * 999 + ["7v5"])
        assert _check(run_integrity_checks(db), "shots_situation_plausible").passed

    def test_a_wholesale_semantic_regression_fails(self, db):
        self._shots(db, ["6v6"] * 500 + ["7v7"] * 500)
        result = _check(run_integrity_checks(db), "shots_situation_plausible")
        assert not result.passed
