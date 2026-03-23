"""Tests for generate.py output."""
import json
import sqlite3
import pytest
from pathlib import Path
from unittest.mock import patch
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
    conn.commit()
    conn.close()

    return Generator(
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
