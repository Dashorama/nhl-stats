"""Tests for the storage layer's integrity guarantees.

Covers the schema and write paths the audit findings depend on: games keeping
their season/date on re-scrape, shots carrying a joinable id, and shots /
play-by-play / shifts all being safe to re-ingest.
"""

import sqlite3

import pytest
from sqlalchemy import text

from src.storage.database import Database


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "test.db")


def _columns(db: Database, table: str) -> set[str]:
    with db.engine.connect() as conn:
        return {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))}


def _indexes(db: Database, table: str) -> set[str]:
    with db.engine.connect() as conn:
        return {row[1] for row in conn.execute(text(f"PRAGMA index_list({table})"))}


SHOT = {
    "season": "2024",
    "game_id": 2024020001,
    "moneypuck_game_id": 20001,
    "shot_id": 0,
    "team": "NJD",
    "shooter_id": 8483495,
    "shooter_name": "Simon Nemec",
    "goalie_id": 8480045,
    "goalie_name": "Devon Levi",
    "event": "SHOT",
    "period": 1,
    "time": 8,
    "x_coord": 57.0,
    "y_coord": -40.0,
    "shot_type": "WRIST",
    "x_goal": 0.045,
    "goal": 0,
    "shot_angle": 34.28,
    "shot_distance": 26.62,
    "shot_rebound": 0,
    "shot_rush": 0,
    "situation": "5v5",
    "is_home": False,
}

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

PBP_EVENTS = [
    {
        "event_id": 51,
        "event_type": "faceoff",
        "period": 1,
        "period_type": "REG",
        "time_in_period": "00:00",
        "x_coord": 0,
        "y_coord": 0,
        "zone_code": "N",
        "player1_id": 8477450,
    },
    {
        "event_id": 52,
        "event_type": "shot-on-goal",
        "period": 1,
        "period_type": "REG",
        "time_in_period": "00:42",
        "x_coord": 57,
        "y_coord": -40,
        "zone_code": "O",
        "player1_id": 8483495,
    },
]

SHIFTS = [
    {
        "game_id": 2024020001,
        "player_id": 8483495,
        "player_name": "Simon Nemec",
        "team_abbrev": "NJD",
        "team_id": 1,
        "period": 1,
        "shift_number": 1,
        "start_time": "00:00",
        "end_time": "00:42",
        "duration": "00:42",
        "type_code": 517,
        "detail_code": 0,
        "event_number": 6,
    }
]


class TestShotsSchema:
    def test_shots_carry_the_moneypuck_id_alongside_the_nhl_id(self, db):
        assert {"moneypuck_game_id", "shot_id"} <= _columns(db, "shots")

    def test_shots_have_a_unique_key_for_idempotent_ingest(self, db):
        assert "uq_shots_season_game_shot" in _indexes(db, "shots")

    def test_insert_shots_persists_the_new_fields(self, db):
        db.insert_shots([SHOT])
        with db.engine.connect() as conn:
            row = conn.execute(
                text("SELECT game_id, moneypuck_game_id, shot_id, situation, is_home FROM shots")
            ).one()
        assert row[0] == 2024020001
        assert row[1] == 20001
        assert row[2] == 0
        assert row[3] == "5v5"
        assert row[4] == 0

    def test_reingesting_a_season_does_not_duplicate_shots(self, db):
        db.insert_shots([SHOT])
        db.insert_shots([SHOT])
        with db.engine.connect() as conn:
            assert conn.execute(text("SELECT COUNT(*) FROM shots")).scalar() == 1

    def test_duplicate_shots_within_one_batch_are_rejected(self, db):
        with pytest.raises(Exception):
            db.insert_shots([SHOT, dict(SHOT)])


class TestGamesUpsert:
    def test_new_games_keep_their_season_and_date(self, db):
        db.upsert_games([GAME])
        with db.engine.connect() as conn:
            row = conn.execute(text("SELECT season, game_date FROM games")).one()
        assert row == ("20242025", "2024-10-04")

    def test_rescraping_backfills_a_season_onto_an_existing_row(self, db):
        db.upsert_games([{**GAME, "season": None, "date": None}])
        db.upsert_games([GAME])
        with db.engine.connect() as conn:
            row = conn.execute(text("SELECT season, game_date FROM games")).one()
        assert row == ("20242025", "2024-10-04")

    def test_rescraping_still_updates_the_score(self, db):
        db.upsert_games([{**GAME, "home_score": 0, "away_score": 0, "game_state": "LIVE"}])
        db.upsert_games([GAME])
        with db.engine.connect() as conn:
            row = conn.execute(text("SELECT home_score, away_score, game_state FROM games")).one()
        assert row == (3, 4, "OFF")

    def test_a_rescrape_without_a_season_does_not_wipe_a_stored_one(self, db):
        db.upsert_games([GAME])
        db.upsert_games([{**GAME, "season": None, "date": None}])
        with db.engine.connect() as conn:
            row = conn.execute(text("SELECT season, game_date FROM games")).one()
        assert row == ("20242025", "2024-10-04")


class TestPlayByPlay:
    def test_events_have_a_unique_key_per_game(self, db):
        assert "uq_pbp_game_event" in _indexes(db, "play_by_play")

    def test_reingesting_a_game_does_not_duplicate_events(self, db):
        db.insert_play_by_play(2024020001, PBP_EVENTS)
        db.insert_play_by_play(2024020001, PBP_EVENTS)
        with db.engine.connect() as conn:
            assert conn.execute(text("SELECT COUNT(*) FROM play_by_play")).scalar() == 2

    def test_duplicate_event_ids_within_one_game_are_rejected(self, db):
        with pytest.raises(Exception):
            db.insert_play_by_play(2024020001, [PBP_EVENTS[0], dict(PBP_EVENTS[0])])


class TestShifts:
    def test_shifts_table_exists(self, db):
        assert {"game_id", "player_id", "period", "shift_number"} <= _columns(db, "shifts")

    def test_insert_shifts_stores_the_rows(self, db):
        assert db.insert_shifts(2024020001, SHIFTS) == 1
        with db.engine.connect() as conn:
            row = conn.execute(text("SELECT player_name, start_time, end_time FROM shifts")).one()
        assert row == ("Simon Nemec", "00:00", "00:42")

    def test_reingesting_a_game_does_not_duplicate_shifts(self, db):
        db.insert_shifts(2024020001, SHIFTS)
        db.insert_shifts(2024020001, SHIFTS)
        with db.engine.connect() as conn:
            assert conn.execute(text("SELECT COUNT(*) FROM shifts")).scalar() == 1

    def test_shifts_are_counted_in_the_stats_summary(self, db):
        db.insert_shifts(2024020001, SHIFTS)
        assert db.get_stats()["shifts"] == 1


class TestJoinsAcrossTables:
    def test_shots_join_to_games_and_play_by_play(self, db):
        db.upsert_games([GAME])
        db.insert_shots([SHOT])
        db.insert_play_by_play(2024020001, PBP_EVENTS)

        with db.engine.connect() as conn:
            joined = conn.execute(
                text(
                    "SELECT COUNT(*) FROM shots s "
                    "JOIN games g ON g.id = s.game_id "
                    "JOIN play_by_play p ON p.game_id = s.game_id"
                )
            ).scalar()

        assert joined == 2  # one shot x two events, proving both joins resolve


class TestMigrationOfAnExistingDatabase:
    """The live database predates these columns, so opening it must migrate in place."""

    def _legacy_db(self, path):
        conn = sqlite3.connect(path)
        conn.execute(
            "CREATE TABLE shots ("
            " id INTEGER PRIMARY KEY AUTOINCREMENT, season VARCHAR(8), game_id INTEGER,"
            " team VARCHAR(3), shooter_id INTEGER, shooter_name VARCHAR(100),"
            " goalie_id INTEGER, goalie_name VARCHAR(100), event VARCHAR(10),"
            " period INTEGER, time INTEGER, x_coord FLOAT, y_coord FLOAT,"
            " shot_type VARCHAR(20), x_goal FLOAT, goal INTEGER, shot_angle FLOAT,"
            " shot_distance FLOAT, shot_rebound INTEGER, shot_rush INTEGER,"
            " situation VARCHAR(10), is_home BOOLEAN)"
        )
        conn.execute(
            "INSERT INTO shots (season, game_id, team, situation, is_home)"
            " VALUES ('2024', 20001, 'NJD', '', 0)"
        )
        conn.execute(
            "CREATE TABLE play_by_play ("
            " id INTEGER PRIMARY KEY AUTOINCREMENT, game_id INTEGER, event_id INTEGER,"
            " event_type VARCHAR(30), period INTEGER, period_type VARCHAR(10),"
            " time_in_period VARCHAR(10), time_remaining VARCHAR(10), x_coord INTEGER,"
            " y_coord INTEGER, zone_code VARCHAR(2), player1_id INTEGER,"
            " player2_id INTEGER, player3_id INTEGER, team_id INTEGER,"
            " shot_type VARCHAR(20), description VARCHAR(50), raw_data TEXT)"
        )
        conn.execute("INSERT INTO play_by_play (game_id, event_id) VALUES (2025020001, 51)")
        conn.commit()
        conn.close()

    def test_opening_a_legacy_database_adds_the_missing_shot_columns(self, tmp_path):
        path = tmp_path / "legacy.db"
        self._legacy_db(path)

        db = Database(path)

        assert {"moneypuck_game_id", "shot_id"} <= _columns(db, "shots")

    def test_migration_preserves_existing_rows(self, tmp_path):
        path = tmp_path / "legacy.db"
        self._legacy_db(path)

        db = Database(path)

        with db.engine.connect() as conn:
            assert conn.execute(text("SELECT COUNT(*) FROM shots")).scalar() == 1
            assert conn.execute(text("SELECT COUNT(*) FROM play_by_play")).scalar() == 1

    def test_migration_adds_the_unique_keys(self, tmp_path):
        path = tmp_path / "legacy.db"
        self._legacy_db(path)

        db = Database(path)

        assert "uq_pbp_game_event" in _indexes(db, "play_by_play")
        assert "uq_shots_season_game_shot" in _indexes(db, "shots")

    def test_migration_is_safe_to_run_twice(self, tmp_path):
        path = tmp_path / "legacy.db"
        self._legacy_db(path)

        Database(path)
        db = Database(path)

        assert {"moneypuck_game_id", "shot_id"} <= _columns(db, "shots")


class TestSeasonReplaceIsAtomic:
    """insert_shots clears a season before inserting it.

    With a unique key on the season, a duplicate row part-way through the batch
    raises after earlier rows have been written. If the clear is not in the same
    transaction, the season is left truncated -- and every integrity check still
    passes, because nothing counts shots per season.
    """

    def _season(self, n, start=0):
        return [
            {**SHOT, "moneypuck_game_id": 20000 + i, "shot_id": i} for i in range(start, start + n)
        ]

    def test_a_failed_replace_leaves_the_stored_season_intact(self, db):
        db.insert_shots(self._season(30))

        # A batch containing a duplicate natural key: the write must fail whole.
        poisoned = self._season(20)
        poisoned.append(dict(poisoned[0]))
        with pytest.raises(Exception):
            db.insert_shots(poisoned)

        with db.engine.connect() as conn:
            assert conn.execute(text("SELECT COUNT(*) FROM shots")).scalar() == 30

    def test_a_successful_replace_still_swaps_the_season(self, db):
        db.insert_shots(self._season(30))
        db.insert_shots(self._season(12))

        with db.engine.connect() as conn:
            assert conn.execute(text("SELECT COUNT(*) FROM shots")).scalar() == 12

    def test_a_replace_does_not_touch_other_seasons(self, db):
        db.insert_shots(self._season(5))
        db.insert_shots([{**s, "season": "2023"} for s in self._season(7)])

        db.insert_shots(self._season(3))

        with db.engine.connect() as conn:
            by_season = dict(
                conn.execute(text("SELECT season, COUNT(*) FROM shots GROUP BY season")).all()
            )
        assert by_season == {"2024": 3, "2023": 7}
