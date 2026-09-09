"""Tests for MoneyPuck shot-level parsing.

These cover the three shot-table data-integrity bugs found in the 2026-08-17 audit:

* ``situation`` was read from a column MoneyPuck's shots CSV does not have, so every
  one of the 899,651 stored rows had an empty situation.
* ``is_home`` was compared against ``"1"`` while MoneyPuck writes ``"1.0"``, so every
  shot in seasons 2018-2024 was recorded as an away shot.
* ``game_id`` was stored as MoneyPuck's 5-digit id, which does not join to
  ``games.id`` / ``play_by_play.game_id`` (both use the NHL 10-digit id).
"""

import pytest

from src.scrapers.moneypuck import (
    MoneyPuckScraper,
    derive_shot_situation,
    parse_moneypuck_flag,
    to_nhl_game_id,
)


def _row(**overrides: str) -> dict[str, str]:
    """A minimal MoneyPuck shots-CSV row, with real column names."""
    row = {
        "shotID": "0",
        "game_id": "20001",
        "season": "2024",
        "teamCode": "NJD",
        "homeTeamCode": "BUF",
        "awayTeamCode": "NJD",
        "isHomeTeam": "0.0",
        "homeSkatersOnIce": "5",
        "awaySkatersOnIce": "5",
        "homeEmptyNet": "0",
        "awayEmptyNet": "0",
        "event": "SHOT",
        "period": "1",
        "time": "8",
        "shooterPlayerId": "8483495",
        "shooterName": "Simon Nemec",
        "goalieIdForShot": "8480045",
        "goalieNameForShot": "Devon Levi",
        "shotType": "WRIST",
        "xCordAdjusted": "57",
        "yCordAdjusted": "-40",
        "xGoal": "0.0454343",
        "goal": "0",
        "shotAngleAdjusted": "34.28",
        "shotDistance": "26.62",
        "shotRebound": "0",
        "shotRush": "0",
    }
    row.update(overrides)
    return row


class TestToNhlGameId:
    def test_maps_regular_season_id_to_ten_digit_nhl_id(self):
        assert to_nhl_game_id("2024", 20001) == 2024020001

    def test_maps_playoff_id_to_ten_digit_nhl_id(self):
        assert to_nhl_game_id("2018", 30417) == 2018030417

    def test_accepts_integer_season(self):
        assert to_nhl_game_id(2020, 20500) == 2020020500

    def test_returns_none_for_missing_game_id(self):
        assert to_nhl_game_id("2024", None) is None

    def test_returns_none_for_missing_season(self):
        assert to_nhl_game_id(None, 20001) is None


class TestParseMoneyPuckFlag:
    def test_parses_float_formatted_true(self):
        assert parse_moneypuck_flag("1.0") is True

    def test_parses_float_formatted_false(self):
        assert parse_moneypuck_flag("0.0") is False

    def test_parses_integer_formatted_true(self):
        assert parse_moneypuck_flag("1") is True

    def test_empty_string_is_false(self):
        assert parse_moneypuck_flag("") is False

    def test_none_is_false(self):
        assert parse_moneypuck_flag(None) is False


class TestDeriveShotSituation:
    def test_even_strength_is_5v5(self):
        assert derive_shot_situation(_row()) == "5v5"

    def test_home_shooter_on_the_power_play(self):
        row = _row(isHomeTeam="1.0", homeSkatersOnIce="5", awaySkatersOnIce="4")
        assert derive_shot_situation(row) == "5v4"

    def test_away_shooter_shorthanded(self):
        row = _row(isHomeTeam="0.0", homeSkatersOnIce="5", awaySkatersOnIce="4")
        assert derive_shot_situation(row) == "4v5"

    def test_shooting_against_an_empty_net_counts_the_extra_attacker(self):
        # Away team pulled its goalie: 6 away skaters, home team shoots.
        row = _row(isHomeTeam="1.0", homeSkatersOnIce="5", awaySkatersOnIce="6")
        assert derive_shot_situation(row) == "5v6"

    def test_three_on_three_overtime(self):
        row = _row(isHomeTeam="1.0", homeSkatersOnIce="3", awaySkatersOnIce="3")
        assert derive_shot_situation(row) == "3v3"

    def test_returns_none_when_skater_counts_are_missing(self):
        assert derive_shot_situation(_row(homeSkatersOnIce="", awaySkatersOnIce="")) is None

    def test_returns_none_when_skater_counts_are_not_numeric(self):
        assert derive_shot_situation(_row(homeSkatersOnIce="NA")) is None


class TestParseShotRow:
    def test_situation_is_populated(self):
        parsed = MoneyPuckScraper.parse_shot_row(_row(), "2024")
        assert parsed["situation"] == "5v5"

    def test_game_id_is_the_joinable_nhl_id(self):
        parsed = MoneyPuckScraper.parse_shot_row(_row(), "2024")
        assert parsed["game_id"] == 2024020001

    def test_moneypuck_game_id_is_preserved_for_provenance(self):
        parsed = MoneyPuckScraper.parse_shot_row(_row(), "2024")
        assert parsed["moneypuck_game_id"] == 20001

    def test_shot_id_is_captured_for_idempotent_ingest(self):
        parsed = MoneyPuckScraper.parse_shot_row(_row(shotID="417"), "2024")
        assert parsed["shot_id"] == 417

    def test_is_home_is_true_for_a_home_shot(self):
        parsed = MoneyPuckScraper.parse_shot_row(_row(isHomeTeam="1.0"), "2024")
        assert parsed["is_home"] is True

    def test_is_home_is_false_for_an_away_shot(self):
        parsed = MoneyPuckScraper.parse_shot_row(_row(isHomeTeam="0.0"), "2024")
        assert parsed["is_home"] is False

    def test_keeps_the_existing_shot_fields(self):
        parsed = MoneyPuckScraper.parse_shot_row(_row(), "2024")
        assert parsed["season"] == "2024"
        assert parsed["team"] == "NJD"
        assert parsed["shooter_id"] == 8483495
        assert parsed["goalie_id"] == 8480045
        assert parsed["event"] == "SHOT"
        assert parsed["period"] == 1
        assert parsed["x_coord"] == pytest.approx(57.0)
        assert parsed["y_coord"] == pytest.approx(-40.0)
        assert parsed["shot_type"] == "WRIST"
        assert parsed["goal"] == 0
