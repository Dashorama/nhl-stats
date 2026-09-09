"""Tests for NHL api-web schedule parsing and season derivation.

Audit finding: ``games.season`` and ``games.game_date`` were NULL for all 15,569
rows. ``scrape_games`` never emitted a season at all, and read ``gameDate`` from the
game object -- a field the ``/schedule/{date}`` endpoint does not return. The
calendar date lives on the parent ``gameWeek`` entry.
"""

import pytest

from src.scrapers.nhl_api import NHLAPIScraper, season_from_game_id

SCHEDULE_PAYLOAD = {
    "nextStartDate": "2024-10-15",
    "gameWeek": [
        {
            "date": "2024-10-08",
            "dayAbbrev": "TUE",
            "games": [
                {
                    "id": 2024020003,
                    "season": 20242025,
                    "gameType": 2,
                    "gameState": "OFF",
                    "startTimeUTC": "2024-10-08T20:30:00Z",
                    "venue": {"default": "Climate Pledge Arena"},
                    "homeTeam": {"abbrev": "SEA", "score": 3},
                    "awayTeam": {"abbrev": "STL", "score": 1},
                }
            ],
        },
        {
            "date": "2024-10-09",
            "dayAbbrev": "WED",
            "games": [
                {
                    "id": 2024020004,
                    "season": 20242025,
                    "gameType": 2,
                    "gameState": "FUT",
                    "startTimeUTC": "2024-10-09T23:00:00Z",
                    "venue": {"default": "Bell Centre"},
                    "homeTeam": {"abbrev": "MTL"},
                    "awayTeam": {"abbrev": "TOR"},
                }
            ],
        },
    ],
}


class TestParseScheduleGames:
    def test_season_is_populated(self):
        games = NHLAPIScraper.parse_schedule_games(SCHEDULE_PAYLOAD)
        assert games[0]["season"] == "20242025"

    def test_season_is_a_string_so_it_matches_the_games_column(self):
        games = NHLAPIScraper.parse_schedule_games(SCHEDULE_PAYLOAD)
        assert all(isinstance(g["season"], str) and len(g["season"]) == 8 for g in games)

    def test_date_comes_from_the_parent_week_entry(self):
        games = NHLAPIScraper.parse_schedule_games(SCHEDULE_PAYLOAD)
        assert games[0]["date"] == "2024-10-08"
        assert games[1]["date"] == "2024-10-09"

    def test_date_falls_back_to_start_time_when_the_week_has_no_date(self):
        payload = {
            "gameWeek": [
                {
                    "games": [
                        {
                            "id": 2024020003,
                            "season": 20242025,
                            "startTimeUTC": "2024-10-08T20:30:00Z",
                            "homeTeam": {"abbrev": "SEA"},
                            "awayTeam": {"abbrev": "STL"},
                        }
                    ]
                }
            ]
        }
        assert NHLAPIScraper.parse_schedule_games(payload)[0]["date"] == "2024-10-08"

    def test_season_falls_back_to_the_game_id_when_absent(self):
        payload = {
            "gameWeek": [
                {
                    "date": "2024-10-08",
                    "games": [
                        {
                            "id": 2024020003,
                            "homeTeam": {"abbrev": "SEA"},
                            "awayTeam": {"abbrev": "STL"},
                        }
                    ],
                }
            ]
        }
        assert NHLAPIScraper.parse_schedule_games(payload)[0]["season"] == "20242025"

    def test_keeps_the_existing_game_fields(self):
        game = NHLAPIScraper.parse_schedule_games(SCHEDULE_PAYLOAD)[0]
        assert game["id"] == 2024020003
        assert game["game_type"] == 2
        assert game["home_team"] == "SEA"
        assert game["away_team"] == "STL"
        assert game["home_score"] == 3
        assert game["away_score"] == 1
        assert game["game_state"] == "OFF"
        assert game["venue"] == "Climate Pledge Arena"


class TestSeasonFromGameId:
    @pytest.mark.parametrize(
        ("game_id", "expected"),
        [
            (2024020001, "20242025"),
            (2018030417, "20182019"),
            (2015010082, "20152016"),
            (1999020001, "19992000"),
        ],
    )
    def test_derives_the_eight_digit_season(self, game_id, expected):
        assert season_from_game_id(game_id) == expected

    def test_returns_none_for_a_missing_id(self):
        assert season_from_game_id(None) is None

    def test_returns_none_for_an_id_that_is_not_a_game_id(self):
        assert season_from_game_id(12345) is None
