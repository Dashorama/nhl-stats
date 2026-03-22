"""Tests for story selection logic."""
import json
import pytest
from datetime import date
from scripts.story_selector import StorySelector, StoryType


SHOOTERS = [
    {"player_id": 1, "player_name": "Hot Shooter", "team_abbrev": "EDM",
     "goals": 63, "xg": 37.4, "gax": 25.6, "shots": 436, "sh_vs_expected": 1.68},
    {"player_id": 2, "player_name": "Cold Shooter", "team_abbrev": "TOR",
     "goals": 10, "xg": 25.0, "gax": -15.0, "shots": 200, "sh_vs_expected": 0.40},
    {"player_id": 3, "player_name": "Normal Player", "team_abbrev": "BOS",
     "goals": 30, "xg": 28.0, "gax": 2.0, "shots": 300, "sh_vs_expected": 1.07},
]

TEAMS = [
    {"abbrev": "BUF", "name": "Buffalo Sabres", "win_pct": 0.623, "xg_win_pct": 0.495, "diff": 0.128},
    {"abbrev": "VGK", "name": "Vegas Golden Knights", "win_pct": 0.449, "xg_win_pct": 0.535, "diff": -0.086},
]

CAREER_STATS = {
    1: [{"season": "2022", "sh_vs_expected": 1.50},
        {"season": "2023", "sh_vs_expected": 1.45},
        {"season": "2024", "sh_vs_expected": 1.68}],
    2: [{"season": "2022", "sh_vs_expected": 0.82},
        {"season": "2023", "sh_vs_expected": 0.75},
        {"season": "2024", "sh_vs_expected": 0.40}],
}

HEADLINES = [{"title": "Hot Shooter scores hat trick", "url": "https://tsn.ca/x", "source": "TSN"}]


@pytest.fixture
def selector(tmp_path):
    return StorySelector(
        shooters=SHOOTERS, teams=TEAMS, career_stats=CAREER_STATS,
        headlines=HEADLINES, unavailable_players=set(),
        history_path=str(tmp_path / "story_history.json"),
    )


def test_news_combo_is_highest_priority(selector):
    story = selector.select()
    assert story["story_type"] == StoryType.NEWS_COMBO
    assert story["subject_id"] == 1


def test_extreme_shooter_when_no_headlines(tmp_path):
    sel = StorySelector(
        shooters=SHOOTERS, teams=TEAMS, career_stats=CAREER_STATS,
        headlines=[], unavailable_players=set(),
        history_path=str(tmp_path / "h.json"),
    )
    story = sel.select()
    assert story["story_type"] == StoryType.EXTREME_SHOOTER


def test_injured_player_excluded(tmp_path):
    sel = StorySelector(
        shooters=SHOOTERS, teams=TEAMS, career_stats=CAREER_STATS,
        headlines=[], unavailable_players={1},  # Hot Shooter unavailable
        history_path=str(tmp_path / "h.json"),
    )
    story = sel.select()
    assert story.get("subject_id") != 1


def test_team_story_when_all_players_unavailable(tmp_path):
    sel = StorySelector(
        shooters=SHOOTERS, teams=TEAMS, career_stats=CAREER_STATS,
        headlines=[], unavailable_players={1, 2, 3},
        history_path=str(tmp_path / "h.json"),
    )
    story = sel.select()
    assert story["story_type"] == StoryType.TEAM_RECORD


def test_dedup_skips_recent_subject(tmp_path):
    history_path = tmp_path / "h.json"
    history_path.write_text(json.dumps({"stories": [
        {"date": str(date.today()), "subject_id": 1, "story_type": "extreme_shooter"}
    ]}))
    sel = StorySelector(
        shooters=SHOOTERS, teams=TEAMS, career_stats=CAREER_STATS,
        headlines=[], unavailable_players=set(),
        history_path=str(history_path),
    )
    story = sel.select()
    assert story.get("subject_id") != 1


def test_output_has_required_keys(selector):
    story = selector.select()
    for key in ("story_type", "headline", "body", "subject_type",
                "subject_id", "subject_name", "social_text", "headlines"):
        assert key in story, f"Missing key: {key}"


def test_record_writes_history(tmp_path):
    history_path = tmp_path / "h.json"
    sel = StorySelector(
        shooters=SHOOTERS, teams=TEAMS, career_stats=CAREER_STATS,
        headlines=[], unavailable_players=set(),
        history_path=str(history_path),
    )
    story = sel.select()
    sel.record(story)
    history = json.loads(history_path.read_text())
    assert len(history["stories"]) == 1
    assert history["stories"][0]["subject_id"] == story["subject_id"]
