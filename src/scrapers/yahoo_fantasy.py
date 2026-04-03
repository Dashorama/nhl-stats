"""Yahoo Fantasy Sports API integration for managing fantasy hockey teams.

Uses yfpy library for OAuth and API access. Requires YAHOO_CONSUMER_KEY
environment variable set (YAHOO_CONSUMER_SECRET can be empty for installed apps).

First run will open a browser for Yahoo OAuth login. After that, the access
token is cached and refreshed automatically.
"""

import json
from pathlib import Path
from typing import Any

import structlog
from yfpy.query import YahooFantasySportsQuery

logger = structlog.get_logger()

# Default paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
ENV_FILE_DIR = PROJECT_ROOT
TOKEN_DIR = PROJECT_ROOT / "data"


class YahooFantasyClient:
    """Client for Yahoo Fantasy Sports API focused on NHL/hockey."""

    def __init__(
        self,
        league_id: str,
        game_code: str = "nhl",
        game_id: int | None = None,
    ):
        self.league_id = league_id
        self.game_code = game_code

        # yfpy picks up YAHOO_CONSUMER_KEY and YAHOO_CONSUMER_SECRET from env
        self.query = YahooFantasySportsQuery(
            league_id=league_id,
            game_code=game_code,
            game_id=game_id,
            env_file_location=ENV_FILE_DIR,
            save_token_data_to_env_file=True,
            browser_callback=False,  # Print URL instead of opening browser
        )
        logger.info("yahoo_fantasy_client_init", league_id=league_id, game_code=game_code)

    # ── League Info ──────────────────────────────────────────────

    def get_league_info(self) -> dict[str, Any]:
        """Get league name, settings, scoring type, etc."""
        info = self.query.get_league_info()
        return _to_dict(info)

    def get_league_settings(self) -> dict[str, Any]:
        """Get league scoring categories, roster positions, etc."""
        settings = self.query.get_league_settings()
        return _to_dict(settings)

    def get_league_standings(self) -> list[dict[str, Any]]:
        """Get current league standings."""
        standings = self.query.get_league_standings()
        return _to_dict(standings)

    def get_league_scoreboard(self, week: int | None = None) -> dict[str, Any]:
        """Get scoreboard for a given week (current week if None)."""
        scoreboard = self.query.get_league_scoreboard_by_week(chosen_week=week)
        return _to_dict(scoreboard)

    # ── Team Info ────────────────────────────────────────────────

    def get_my_team(self) -> dict[str, Any]:
        """Get the authenticated user's team info."""
        user = self.query.get_current_user()
        teams = self.query.get_league_teams()
        return _to_dict(teams)

    def get_team_info(self, team_id: int | str | None = None) -> dict[str, Any]:
        """Get info for a specific team."""
        info = self.query.get_team_info(team_id)
        return _to_dict(info)

    def get_team_roster(
        self, team_id: int | str | None = None, week: int | None = None
    ) -> list[dict[str, Any]]:
        """Get roster for a team for a given week."""
        if week:
            roster = self.query.get_team_roster_player_info_by_week(
                team_id=team_id, chosen_week=week
            )
        else:
            roster = self.query.get_team_roster_player_stats(team_id=team_id)
        return _to_dict(roster)

    def get_team_matchups(self, team_id: int | str | None = None) -> list[dict[str, Any]]:
        """Get all matchups for a team this season."""
        matchups = self.query.get_team_matchups(team_id=team_id)
        return _to_dict(matchups)

    def get_team_stats(
        self, team_id: int | str | None = None, week: int | None = None
    ) -> dict[str, Any]:
        """Get team stats, optionally for a specific week."""
        if week:
            stats = self.query.get_team_stats_by_week(team_id=team_id, chosen_week=week)
        else:
            stats = self.query.get_team_stats(team_id=team_id)
        return _to_dict(stats)

    # ── Player Info ──────────────────────────────────────────────

    def get_player_stats(
        self, player_key: str, week: int | None = None
    ) -> dict[str, Any]:
        """Get stats for a specific player."""
        if week:
            stats = self.query.get_player_stats_by_week(player_key, chosen_week=week)
        else:
            stats = self.query.get_player_stats_for_season(player_key)
        return _to_dict(stats)

    def get_player_ownership(self, player_key: str) -> dict[str, Any]:
        """Get ownership info for a player (who owns them, % owned)."""
        ownership = self.query.get_player_ownership(player_key)
        return _to_dict(ownership)

    # ── Matchup Analysis ─────────────────────────────────────────

    def get_current_matchup(self, team_id: int | str | None = None) -> dict[str, Any]:
        """Get the current week's matchup details for a team."""
        scoreboard = self.query.get_league_scoreboard_by_week()
        return _to_dict(scoreboard)

    # ── Transactions ─────────────────────────────────────────────

    def get_transactions(self) -> list[dict[str, Any]]:
        """Get recent league transactions (adds, drops, trades)."""
        transactions = self.query.get_league_transactions()
        return _to_dict(transactions)

    def get_draft_results(self) -> list[dict[str, Any]]:
        """Get draft results."""
        results = self.query.get_league_draft_results()
        return _to_dict(results)

    # ── Free Agents / Waiver Wire ────────────────────────────────

    def get_league_players(
        self,
        status: str = "FA",
        sort: str = "AR",
        position: str | None = None,
        count: int = 25,
    ) -> list[dict[str, Any]]:
        """Get available players (free agents / waivers).

        Args:
            status: "FA" (free agents), "W" (waivers), "T" (taken), "A" (all)
            sort: Sort method - "AR" (actual rank), various stat categories
            position: Filter by position (C, LW, RW, D, G, etc.)
            count: Number of players to return
        """
        players = self.query.get_league_players(
            player_count=count,
            player_count_start=0,
        )
        return _to_dict(players)


def _to_dict(obj: Any) -> Any:
    """Convert yfpy objects to plain dicts/lists for easy consumption."""
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, list):
        return [_to_dict(item) for item in obj]
    if isinstance(obj, dict):
        return {k: _to_dict(v) for k, v in obj.items()}
    # yfpy model objects — try serialization approaches
    if hasattr(obj, "serialized"):
        try:
            return json.loads(json.dumps(obj.serialized(), default=str))
        except (TypeError, ValueError):
            pass
    if hasattr(obj, "__dict__"):
        result = {}
        for k, v in obj.__dict__.items():
            if not k.startswith("_"):
                result[k] = _to_dict(v)
        return result
    return str(obj)
