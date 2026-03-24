"""Tests for LLM narrator — uses mocks since Ollama may not be available."""

import json
from unittest.mock import MagicMock, patch

import pytest

from scripts.llm_narrator import LLMNarrator, _trim_shooters, _trim_faceoffs, _trim_tracking


SHOOTERS = [
    {"player_id": 1, "player_name": "Hot Shooter", "team_abbrev": "EDM",
     "goals": 63, "xg": 37.4, "gax": 25.6, "shots": 436, "sh_vs_expected": 1.68,
     "hd_shot_pct": 18.5, "rush_rate": 7.2, "rebound_rate": 4.1},
    {"player_id": 2, "player_name": "Cold Shooter", "team_abbrev": "TOR",
     "goals": 10, "xg": 25.0, "gax": -15.0, "shots": 200, "sh_vs_expected": 0.40,
     "hd_shot_pct": 12.0, "rush_rate": 3.0, "rebound_rate": 2.0},
    {"player_id": 3, "player_name": "Normal Player", "team_abbrev": "BOS",
     "goals": 30, "xg": 28.0, "gax": 2.0, "shots": 300, "sh_vs_expected": 1.07,
     "hd_shot_pct": 25.0, "rush_rate": 15.0, "rebound_rate": 8.0},
]

TEAMS = [
    {"abbrev": "BUF", "name": "Buffalo Sabres", "win_pct": 0.623, "xg_win_pct": 0.495, "diff": 0.128},
    {"abbrev": "VGK", "name": "Vegas Golden Knights", "win_pct": 0.449, "xg_win_pct": 0.535, "diff": -0.086},
]

CAREER = {
    1: [{"season": "2022", "sh_vs_expected": 1.50, "hd_shot_pct": 17.0, "rush_rate": 6.5, "rebound_rate": 3.8},
        {"season": "2024", "sh_vs_expected": 1.68, "hd_shot_pct": 18.5, "rush_rate": 7.2, "rebound_rate": 4.1}],
}

FACEOFFS = {
    99: {"fo_wins": 520, "fo_losses": 310, "fo_pct": 62.7,
         "fo_oz_pct": 68.0, "fo_dz_pct": 55.0, "fo_nz_pct": 63.0},
}

EDGE = {
    88: {"player_id": 88, "max_speed_mph": 23.5, "max_speed_pct": 92.0,
         "shot_speed_mph": 97.3, "shot_speed_pct": 88.0,
         "oz_pct": 44.0, "oz_percentile": 75.0,
         "distance_mi": 200.0, "distance_pct": 70.0},
}

HEADLINES = [{"title": "Hot Shooter scores hat trick", "source": "TSN"}]


def _mock_response(content: str):
    choice = MagicMock()
    choice.message.content = content
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def _valid_llm_json(**overrides):
    base = {
        "subject_type": "player",
        "subject_id": 1,
        "subject_name": "Hot Shooter",
        "headline": "Hot Shooter's goal binge defies probability",
        "body": "With 63 goals on 37.4 xG, Hot Shooter is 25.6 goals above expected. "
                "That 1.68x conversion rate is historically unsustainable.",
        "social_text": "Hot Shooter: 63 goals, 37.4 xG. Something has to give.",
        "story_type": "shooting_outlier",
    }
    base.update(overrides)
    return json.dumps(base)


class TestNarrateEndToEnd:
    def _call(self, narrator, llm_output):
        mock_resp = _mock_response(llm_output)
        with patch.object(narrator, "_client") as mc:
            mc.return_value.chat.completions.create.return_value = mock_resp
            return narrator.narrate(
                shooters=SHOOTERS, teams=TEAMS, career_stats=CAREER,
                faceoff_stats=FACEOFFS, edge_stats=EDGE,
                headlines=HEADLINES, recent_subjects=[],
            )

    def test_picks_player_story(self):
        narrator = LLMNarrator()
        result = self._call(narrator, _valid_llm_json())
        assert result is not None
        assert result["subject_id"] == 1
        assert result["story_type"] == "shooting_outlier"
        assert "Hot Shooter" in result["headline"]

    def test_picks_team_story(self):
        narrator = LLMNarrator()
        result = self._call(narrator, _valid_llm_json(
            subject_type="team", subject_id="BUF",
            subject_name="Buffalo Sabres",
            headline="The Sabres are living on borrowed time",
            body="Buffalo's record says 62.3% but shot quality says 49.5%.",
            social_text="Sabres overperforming by 12.8%. Regression incoming.",
            story_type="team_regression",
        ))
        assert result is not None
        assert result["subject_id"] == "BUF"
        assert result["subject_type"] == "team"

    def test_rejects_unknown_player(self):
        narrator = LLMNarrator()
        result = self._call(narrator, _valid_llm_json(subject_id=999999))
        assert result is None

    def test_rejects_unknown_team(self):
        narrator = LLMNarrator()
        result = self._call(narrator, _valid_llm_json(
            subject_type="team", subject_id="XXX"))
        assert result is None

    def test_rejects_recent_subject(self):
        narrator = LLMNarrator()
        mock_resp = _mock_response(_valid_llm_json(subject_id=1))
        with patch.object(narrator, "_client") as mc:
            mc.return_value.chat.completions.create.return_value = mock_resp
            result = narrator.narrate(
                shooters=SHOOTERS, teams=TEAMS, career_stats=CAREER,
                faceoff_stats=FACEOFFS, edge_stats=EDGE,
                headlines=HEADLINES,
                recent_subjects=[{"subject_id": 1, "date": "2026-03-23", "story_type": "x"}],
            )
        assert result is None

    def test_returns_none_on_connection_error(self):
        narrator = LLMNarrator()
        with patch.object(narrator, "_client") as mc:
            mc.return_value.chat.completions.create.side_effect = ConnectionError
            result = narrator.narrate(
                shooters=SHOOTERS, teams=TEAMS, career_stats=CAREER,
                faceoff_stats=None, edge_stats=None,
                headlines=[], recent_subjects=[],
            )
        assert result is None

    def test_returns_none_on_bad_json(self):
        narrator = LLMNarrator()
        result = self._call(narrator, "I think the best story is about...")
        assert result is None

    def test_strips_markdown_fences(self):
        narrator = LLMNarrator()
        result = self._call(narrator, "```json\n" + _valid_llm_json() + "\n```")
        assert result is not None
        assert result["subject_id"] == 1

    def test_accepts_faceoff_player(self):
        """LLM can pick a player only present in faceoff data."""
        narrator = LLMNarrator()
        result = self._call(narrator, _valid_llm_json(
            subject_id=99, subject_name="Faceoff Guy",
            story_type="faceoff_dominance",
        ))
        assert result is not None
        assert result["subject_id"] == 99

    def test_accepts_edge_player(self):
        """LLM can pick a player only present in EDGE tracking data."""
        narrator = LLMNarrator()
        result = self._call(narrator, _valid_llm_json(
            subject_id=88, subject_name="Speed Demon",
            story_type="elite_speed",
        ))
        assert result is not None
        assert result["subject_id"] == 88

    def test_llm_invented_story_type(self):
        """The LLM can return any story_type label it wants."""
        narrator = LLMNarrator()
        result = self._call(narrator, _valid_llm_json(
            story_type="career_arc_reversal",
        ))
        assert result is not None
        assert result["story_type"] == "career_arc_reversal"


class TestTrimFunctions:
    def test_trim_shooters_deduplicates(self):
        result = _trim_shooters(SHOOTERS, CAREER, limit=5)
        ids = [s["player_id"] for s in result]
        assert len(ids) == len(set(ids))

    def test_trim_shooters_attaches_career(self):
        result = _trim_shooters(SHOOTERS, CAREER, limit=5)
        p1 = next(s for s in result if s["player_id"] == 1)
        assert "career" in p1
        assert len(p1["career"]) == 2

    def test_trim_faceoffs_filters_low_volume(self):
        low = {50: {"fo_wins": 10, "fo_losses": 5, "fo_pct": 66.7}}
        assert _trim_faceoffs(low) == []

    def test_trim_faceoffs_returns_empty_for_none(self):
        assert _trim_faceoffs(None) == []

    def test_trim_tracking_returns_empty_for_none(self):
        assert _trim_tracking(None) == []

    def test_trim_tracking_sorts_by_best_percentile(self):
        data = {
            1: {"player_id": 1, "max_speed_pct": 50, "shot_speed_pct": 50,
                "oz_percentile": 50, "distance_pct": 50},
            2: {"player_id": 2, "max_speed_pct": 95, "shot_speed_pct": 90,
                "oz_percentile": 80, "distance_pct": 70},
        }
        result = _trim_tracking(data, limit=2)
        assert result[0]["player_id"] == 2
