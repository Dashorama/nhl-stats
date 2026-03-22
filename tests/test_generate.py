"""Tests for generate.py output."""
import json
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
    return Generator(
        db_path=str(tmp_path / "test.db"),
        site_dir=str(site_dir),
        history_path=str(data_dir / "story_history.json"),
    )


def test_leaderboard_json_has_required_keys(gen):
    with patch.object(gen, "_query_leaderboard", return_value={"hot_shooters": [], "cold_shooters": [], "teams": []}), \
         patch.object(gen, "_query_story_data", return_value={"shooters": [], "teams": [], "career_stats": {}, "unavailable": set()}), \
         patch.object(gen, "_generate_chart", return_value="chart-2026-03-22.png"):
        gen.run(injuries_available=False, headlines=[])
    lb = json.loads((Path(gen.site_dir) / "public/data/leaderboard.json").read_text())
    for key in ("date", "hot_shooters", "cold_shooters", "teams"):
        assert key in lb


def test_story_json_has_required_keys(gen):
    with patch.object(gen, "_query_leaderboard", return_value={"hot_shooters": [], "cold_shooters": [], "teams": []}), \
         patch.object(gen, "_query_story_data", return_value={"shooters": [], "teams": [], "career_stats": {}, "unavailable": set()}), \
         patch.object(gen, "_generate_chart", return_value="chart-2026-03-22.png"):
        gen.run(injuries_available=False, headlines=[])
    story = json.loads((Path(gen.site_dir) / "public/data/story.json").read_text())
    for key in ("date", "story_type", "headline", "body", "chart", "subject_type", "social_text"):
        assert key in story


def test_history_written_after_run(gen):
    with patch.object(gen, "_query_leaderboard", return_value={"hot_shooters": [], "cold_shooters": [], "teams": []}), \
         patch.object(gen, "_query_story_data", return_value={"shooters": [], "teams": [], "career_stats": {}, "unavailable": set()}), \
         patch.object(gen, "_generate_chart", return_value="chart-2026-03-22.png"):
        gen.run(injuries_available=False, headlines=[])
    assert Path(gen.history_path).exists()
