"""Tests for the idempotent backfills.

Every backfill here runs against data that already exists, so being safe to
re-run is the whole point: a second run must repair nothing new, duplicate
nothing, and cost no requests it does not need.
"""

import sqlite3

import pytest

from src.backfill import (
    backfill_games,
    backfill_play_by_play,
    backfill_shots,
    games_needing_play_by_play,
    repair_game_seasons_from_ids,
)
from src.storage.database import Database


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "test.db")


def _game(game_id, **overrides):
    game = {
        "id": game_id,
        "season": None,
        "date": None,
        "game_type": 2,
        "home_team": "BUF",
        "away_team": "NJD",
        "home_score": 3,
        "away_score": 4,
        "game_state": "OFF",
    }
    game.update(overrides)
    return game


def _shot(season, mp_game_id, shot_id, **overrides):
    shot = {
        "season": season,
        "game_id": int(season) * 1000000 + mp_game_id,
        "moneypuck_game_id": mp_game_id,
        "shot_id": shot_id,
        "team": "NJD",
        "situation": "5v5",
        "is_home": False,
        "goal": 0,
    }
    shot.update(overrides)
    return shot


EVENT = {"event_id": 51, "event_type": "faceoff", "period": 1}
SHIFT = {
    "player_id": 8483495,
    "player_name": "Simon Nemec",
    "period": 1,
    "shift_number": 1,
    "start_time": "00:00",
    "end_time": "00:42",
}


class TestRepairGameSeasonsFromIds:
    def test_derives_the_season_for_rows_that_have_none(self, db):
        db.upsert_games([_game(2018020001), _game(2024030412)])

        assert repair_game_seasons_from_ids(db) == 2

        with sqlite3.connect(db.db_path) as conn:
            rows = dict(conn.execute("SELECT id, season FROM games").fetchall())
        assert rows == {2018020001: "20182019", 2024030412: "20242025"}

    def test_leaves_a_season_that_is_already_set_alone(self, db):
        db.upsert_games([_game(2018020001, season="20182019")])

        assert repair_game_seasons_from_ids(db) == 0

    def test_repairs_empty_strings_as_well_as_nulls(self, db):
        db.upsert_games([_game(2018020001)])
        with sqlite3.connect(db.db_path) as conn:
            conn.execute("UPDATE games SET season = ''")

        assert repair_game_seasons_from_ids(db) == 1

    def test_a_second_run_repairs_nothing(self, db):
        db.upsert_games([_game(2018020001)])
        repair_game_seasons_from_ids(db)

        assert repair_game_seasons_from_ids(db) == 0


class TestGamesNeedingPlayByPlay:
    def test_lists_finished_games_with_no_events(self, db):
        db.upsert_games([_game(2018020001, season="20182019")])

        assert games_needing_play_by_play(db, ["20182019"]) == [2018020001]

    def test_skips_games_that_already_have_events(self, db):
        db.upsert_games([_game(2018020001, season="20182019")])
        db.insert_play_by_play(2018020001, [EVENT])

        assert games_needing_play_by_play(db, ["20182019"]) == []

    def test_includes_already_collected_games_when_asked_to_refetch(self, db):
        db.upsert_games([_game(2018020001, season="20182019")])
        db.insert_play_by_play(2018020001, [EVENT])

        assert games_needing_play_by_play(db, ["20182019"], skip_existing=False) == [2018020001]

    def test_skips_games_that_have_not_been_played(self, db):
        db.upsert_games([_game(2018020001, season="20182019", game_state="FUT")])

        assert games_needing_play_by_play(db, ["20182019"]) == []

    def test_skips_preseason_games(self, db):
        db.upsert_games([_game(2018010001, season="20182019", game_type=1)])

        assert games_needing_play_by_play(db, ["20182019"]) == []

    def test_includes_playoff_games(self, db):
        db.upsert_games([_game(2018030411, season="20182019", game_type=3)])

        assert games_needing_play_by_play(db, ["20182019"]) == [2018030411]

    def test_only_returns_games_from_the_requested_seasons(self, db):
        db.upsert_games(
            [
                _game(2018020001, season="20182019"),
                _game(2024020001, season="20242025"),
            ]
        )

        assert games_needing_play_by_play(db, ["20242025"]) == [2024020001]


class TestBackfillPlayByPlay:
    async def test_stores_events_for_each_game(self, db):
        db.upsert_games([_game(2018020001, season="20182019")])

        async def fetch(game_id):
            return [EVENT]

        report = await backfill_play_by_play(db, [2018020001], fetch)

        assert report.games_collected == 1
        assert report.events_written == 1

    async def test_a_second_run_fetches_nothing(self, db):
        db.upsert_games([_game(2018020001, season="20182019")])
        calls = []

        async def fetch(game_id):
            calls.append(game_id)
            return [EVENT]

        await backfill_play_by_play(db, [2018020001], fetch)
        await backfill_play_by_play(db, games_needing_play_by_play(db, ["20182019"]), fetch)

        assert calls == [2018020001]

    async def test_refetching_the_same_game_does_not_duplicate_events(self, db):
        db.upsert_games([_game(2018020001, season="20182019")])

        async def fetch(game_id):
            return [EVENT]

        await backfill_play_by_play(db, [2018020001], fetch)
        await backfill_play_by_play(db, [2018020001], fetch)

        with sqlite3.connect(db.db_path) as conn:
            assert conn.execute("SELECT COUNT(*) FROM play_by_play").fetchone()[0] == 1

    async def test_collects_shifts_when_a_shift_fetcher_is_given(self, db):
        db.upsert_games([_game(2018020001, season="20182019")])

        async def fetch(game_id):
            return [EVENT]

        async def fetch_shifts(game_id):
            return [{**SHIFT, "game_id": game_id}]

        report = await backfill_play_by_play(db, [2018020001], fetch, fetch_shifts=fetch_shifts)

        assert report.shifts_written == 1

    async def test_one_failing_game_does_not_stop_the_rest(self, db):
        db.upsert_games(
            [
                _game(2018020001, season="20182019"),
                _game(2018020002, season="20182019"),
            ]
        )

        async def fetch(game_id):
            if game_id == 2018020001:
                raise RuntimeError("404 from the API")
            return [EVENT]

        report = await backfill_play_by_play(db, [2018020001, 2018020002], fetch)

        assert report.games_collected == 1
        assert report.games_failed == 1

    async def test_a_game_that_returns_no_events_is_not_counted_as_collected(self, db):
        db.upsert_games([_game(2018020001, season="20182019")])

        async def fetch(game_id):
            return []

        report = await backfill_play_by_play(db, [2018020001], fetch)

        assert report.games_collected == 0
        assert report.games_empty == 1


class TestBackfillShots:
    async def test_reingests_each_requested_season(self, db):
        async def fetch(season):
            return [_shot(season, 20001, 0)]

        report = await backfill_shots(db, ["2018", "2019"], fetch)

        assert report.seasons_collected == 2
        with sqlite3.connect(db.db_path) as conn:
            assert conn.execute("SELECT COUNT(*) FROM shots").fetchone()[0] == 2

    async def test_a_second_run_replaces_rather_than_duplicates(self, db):
        async def fetch(season):
            return [_shot(season, 20001, 0), _shot(season, 20001, 1)]

        await backfill_shots(db, ["2018"], fetch)
        await backfill_shots(db, ["2018"], fetch)

        with sqlite3.connect(db.db_path) as conn:
            assert conn.execute("SELECT COUNT(*) FROM shots").fetchone()[0] == 2

    async def test_repairs_the_broken_rows_the_audit_found(self, db):
        """A season stored with the old parser is fully replaced by the fixed one."""
        with sqlite3.connect(db.db_path) as conn:
            conn.execute(
                "INSERT INTO shots (season, game_id, situation, is_home) "
                "VALUES ('2018', 20001, '', 0)"
            )

        async def fetch(season):
            return [_shot(season, 20001, 0)]

        await backfill_shots(db, ["2018"], fetch)

        with sqlite3.connect(db.db_path) as conn:
            rows = conn.execute("SELECT game_id, situation FROM shots").fetchall()
        assert rows == [(2018020001, "5v5")]

    async def test_a_season_that_returns_nothing_leaves_stored_shots_alone(self, db):
        async def good(season):
            return [_shot(season, 20001, 0)]

        async def empty(season):
            return []

        await backfill_shots(db, ["2018"], good)
        report = await backfill_shots(db, ["2018"], empty)

        assert report.seasons_failed == 1
        with sqlite3.connect(db.db_path) as conn:
            assert conn.execute("SELECT COUNT(*) FROM shots").fetchone()[0] == 1


class TestBackfillGames:
    async def test_repairs_season_and_date_on_existing_rows(self, db):
        db.upsert_games([_game(2018020001)])

        async def fetch(season):
            return [_game(2018020001, season="20182019", date="2018-10-03")]

        report = await backfill_games(db, ["20182019"], fetch)

        assert report.games_written == 1
        with sqlite3.connect(db.db_path) as conn:
            row = conn.execute("SELECT season, game_date FROM games").fetchone()
        assert row == ("20182019", "2018-10-03")

    async def test_falls_back_to_the_game_id_for_seasons_the_api_did_not_return(self, db):
        db.upsert_games([_game(2015010082)])

        async def fetch(season):
            return []

        report = await backfill_games(db, ["20182019"], fetch)

        assert report.seasons_repaired_from_ids == 1
        with sqlite3.connect(db.db_path) as conn:
            assert conn.execute("SELECT season FROM games").fetchone()[0] == "20152016"

    async def test_a_second_run_is_a_no_op(self, db):
        db.upsert_games([_game(2018020001)])

        async def fetch(season):
            return [_game(2018020001, season="20182019", date="2018-10-03")]

        await backfill_games(db, ["20182019"], fetch)
        await backfill_games(db, ["20182019"], fetch)

        with sqlite3.connect(db.db_path) as conn:
            assert conn.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 1
