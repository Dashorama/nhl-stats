"""Tests for generate.py output."""

import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.generate import Generator


@pytest.fixture
def gen(tmp_path):
    site_dir = tmp_path / "site"
    data_dir = tmp_path / "data"
    data_dir.mkdir()  # REQUIRED: story_history.json written here
    (site_dir / "public" / "data").mkdir(parents=True)
    (site_dir / "src" / "data" / "players").mkdir(parents=True)
    (site_dir / "src" / "data" / "teams").mkdir(parents=True)

    db_path = str(tmp_path / "test.db")
    # Create required tables in the test database
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS play_by_play (
            game_id     TEXT,
            event_id    INTEGER,
            event_type  TEXT,
            zone_code   TEXT,
            time_in_period TEXT,
            period      INTEGER,
            player1_id  INTEGER,
            player2_id  INTEGER
        )
    """)
    conn.execute("CREATE TABLE games (id INTEGER PRIMARY KEY, season TEXT)")
    conn.execute("CREATE TABLE players (id INTEGER, first_name TEXT, last_name TEXT)")
    conn.commit()
    conn.close()

    with patch("scripts.generate.LLMNarrator.narrate", return_value=None):
        yield Generator(
            db_path=db_path,
            site_dir=str(site_dir),
            history_path=str(data_dir / "story_history.json"),
        )


def _mock_gen(gen):
    """Return a context manager that patches leaderboard, story data, and chart generation."""
    leaderboard = {"hot_shooters": [], "cold_shooters": [], "teams": [], "all_teams": []}
    story_data = {"shooters": [], "teams": [], "career_stats": {}, "unavailable": {}}
    return (
        patch.object(gen, "_query_leaderboard", return_value=leaderboard),
        patch.object(gen, "_query_story_data", return_value=story_data),
        patch.object(gen, "_generate_chart", return_value="chart-2026-03-22.png"),
    )


def test_leaderboard_json_has_required_keys(gen):
    p1, p2, p3 = _mock_gen(gen)
    with p1, p2, p3:
        gen.run(injuries_available=False, headlines=[])
    lb = json.loads((Path(gen.site_dir) / "public/data/leaderboard.json").read_text())
    for key in ("date", "hot_shooters", "cold_shooters", "teams"):
        assert key in lb


def test_story_json_has_required_keys(gen):
    p1, p2, p3 = _mock_gen(gen)
    with p1, p2, p3:
        gen.run(injuries_available=False, headlines=[])
    story = json.loads((Path(gen.site_dir) / "public/data/story.json").read_text())
    for key in ("date", "story_type", "headline", "body", "chart", "subject_type", "social_text"):
        assert key in story


def test_history_written_after_run(gen):
    p1, p2, p3 = _mock_gen(gen)
    with p1, p2, p3:
        gen.run(injuries_available=False, headlines=[])
    assert Path(gen.history_path).exists()


def _rush_db(tmp_path):
    """A database with play-by-play for two seasons, one rush shot in each."""
    db_path = str(tmp_path / "rush.db")
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE play_by_play (game_id INTEGER, event_id INTEGER, event_type TEXT,"
        " zone_code TEXT, time_in_period TEXT, period INTEGER, player1_id INTEGER)"
    )
    conn.execute("CREATE TABLE games (id INTEGER PRIMARY KEY, season TEXT)")
    for game_id, season in ((2025020001, "20252026"), (2018020001, "20182019")):
        conn.execute("INSERT INTO games (id, season) VALUES (?, ?)", (game_id, season))
        conn.executemany(
            "INSERT INTO play_by_play VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (game_id, 1, "takeaway", "D", "01:00", 1, 999),
                (game_id, 2, "shot-on-goal", "O", "01:02", 1, 8477492),
            ],
        )
    conn.commit()
    conn.close()
    return db_path


def test_rush_rates_only_use_the_play_by_play_season(tmp_path):
    """Backfilled seasons must not leak into the current-season rush rate."""
    from scripts.generate import PBP_SEASON, Generator

    assert PBP_SEASON == "20252026"
    generator = Generator(db_path=_rush_db(tmp_path))

    rates = generator._compute_rush_rates()

    # One shot from the 2025-26 game only; the 2018-19 game must be excluded.
    assert rates == {8477492: 100.0}


def test_rush_rates_are_empty_when_the_season_has_no_play_by_play(tmp_path):
    from scripts.generate import Generator

    db_path = str(tmp_path / "empty.db")
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE play_by_play (game_id INTEGER, event_id INTEGER, event_type TEXT,"
        " zone_code TEXT, time_in_period TEXT, period INTEGER, player1_id INTEGER)"
    )
    conn.execute("CREATE TABLE games (id INTEGER PRIMARY KEY, season TEXT)")
    conn.execute("INSERT INTO games (id, season) VALUES (2018020001, '20182019')")
    conn.executemany(
        "INSERT INTO play_by_play VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            (2018020001, 1, "takeaway", "D", "01:00", 1, 999),
            (2018020001, 2, "shot-on-goal", "O", "01:02", 1, 8477492),
        ],
    )
    conn.commit()
    conn.close()

    assert Generator(db_path=db_path)._compute_rush_rates() == {}
