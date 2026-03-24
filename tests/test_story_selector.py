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

FACEOFF_STATS = {
    99: {
        "fo_wins": 520, "fo_losses": 310,
        "fo_pct": 62.7, "fo_oz_pct": 68.0, "fo_dz_pct": 55.0, "fo_nz_pct": 63.0,
    },
}

EDGE_STATS = {
    88: {
        "player_id": 88, "max_speed_mph": 23.5, "max_speed_pct": 92.0,
        "shot_speed_mph": 97.3, "shot_speed_pct": 88.0,
        "oz_pct": 44.0, "oz_percentile": 75.0,
        "distance_mi": 200.0, "distance_pct": 70.0,
    },
}


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


def test_faceoff_king_selected(tmp_path):
    """Faceoff story fires when no shooting stories qualify."""
    mild_shooters = [
        {"player_id": 3, "player_name": "Normal Player", "team_abbrev": "BOS",
         "goals": 30, "xg": 28.0, "gax": 2.0, "shots": 300, "sh_vs_expected": 1.07},
    ]
    sel = StorySelector(
        shooters=mild_shooters, teams=[], career_stats={},
        headlines=[], unavailable_players=set(),
        history_path=str(tmp_path / "h.json"),
        faceoff_stats=FACEOFF_STATS,
    )
    story = sel.select()
    assert story["story_type"] == StoryType.FACEOFF_KING
    assert story["subject_id"] == 99
    assert "faceoff" in story["headline"].lower()


def test_speed_demon_selected(tmp_path):
    """Speed demon story fires for elite EDGE tracking stats."""
    mild_shooters = [
        {"player_id": 88, "player_name": "Fast Guy", "team_abbrev": "NYR",
         "goals": 20, "xg": 19.0, "gax": 1.0, "shots": 200, "sh_vs_expected": 1.05},
    ]
    sel = StorySelector(
        shooters=mild_shooters, teams=[], career_stats={},
        headlines=[], unavailable_players=set(),
        history_path=str(tmp_path / "h.json"),
        edge_stats=EDGE_STATS,
    )
    story = sel.select()
    assert story["story_type"] == StoryType.SPEED_DEMON
    assert story["subject_id"] == 88
    assert "speed" in story["headline"].lower() or "elite" in story["headline"].lower()


def test_style_shift_selected(tmp_path):
    """Style shift story fires when a player's shot profile changes dramatically."""
    shooters = [
        {"player_id": 5, "player_name": "Changed Guy", "team_abbrev": "MTL",
         "goals": 25, "xg": 22.0, "gax": 3.0, "shots": 250, "sh_vs_expected": 1.14},
    ]
    career = {
        5: [
            {"season": "2022", "sh_vs_expected": 1.05, "hd_shot_pct": 20.0, "rush_rate": 8.0, "rebound_rate": 5.0},
            {"season": "2023", "sh_vs_expected": 1.08, "hd_shot_pct": 22.0, "rush_rate": 9.0, "rebound_rate": 6.0},
            {"season": "2024", "sh_vs_expected": 1.14, "hd_shot_pct": 35.0, "rush_rate": 7.0, "rebound_rate": 5.5},
        ],
    }
    sel = StorySelector(
        shooters=shooters, teams=[], career_stats=career,
        headlines=[], unavailable_players=set(),
        history_path=str(tmp_path / "h.json"),
    )
    story = sel.select()
    assert story["story_type"] == StoryType.STYLE_SHIFT
    assert "high-danger" in story["headline"].lower() or "rush" in story["headline"].lower()


def test_new_types_respect_dedup(tmp_path):
    """New story types skip recently covered subjects."""
    history_path = tmp_path / "h.json"
    history_path.write_text(json.dumps({"stories": [
        {"date": str(date.today()), "subject_id": 99, "story_type": "faceoff_king"}
    ]}))
    sel = StorySelector(
        shooters=SHOOTERS, teams=TEAMS, career_stats=CAREER_STATS,
        headlines=[], unavailable_players=set(),
        history_path=str(history_path),
        faceoff_stats=FACEOFF_STATS,
    )
    story = sel.select()
    assert story.get("subject_id") != 99
