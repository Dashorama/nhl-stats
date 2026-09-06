"""NHL API scraper for full team rosters."""

from datetime import datetime
from typing import Any

from .base import BaseScraper

# All 32 NHL team abbreviations
NHL_TEAMS = [
    "ANA",
    "ARI",
    "BOS",
    "BUF",
    "CAR",
    "CBJ",
    "CGY",
    "CHI",
    "COL",
    "DAL",
    "DET",
    "EDM",
    "FLA",
    "LAK",
    "MIN",
    "MTL",
    "NJD",
    "NSH",
    "NYI",
    "NYR",
    "OTT",
    "PHI",
    "PIT",
    "SEA",
    "SJS",
    "STL",
    "TBL",
    "TOR",
    "UTA",
    "VAN",
    "VGK",
    "WPG",
    "WSH",
]


class NHLRosterScraper(BaseScraper):
    """Scraper for NHL team rosters via the official API."""

    SOURCE_NAME = "nhl_roster"
    BASE_URL = "https://api-web.nhle.com/v1"
    REQUESTS_PER_SECOND = 2.0  # Be polite

    async def get_current_season(self) -> str:
        """Get the current season ID (e.g., '20242025')."""
        now = datetime.now()
        year = now.year if now.month >= 10 else now.year - 1
        return f"{year}{year + 1}"

    async def scrape_roster(self, team_abbrev: str, season: str | None = None) -> dict[str, Any]:
        """
        Fetch full roster for a single team.

        Args:
            team_abbrev: Team abbreviation (e.g., 'TOR', 'NYR')
            season: Season ID (e.g., '20242025'). Uses current season if None.

        Returns:
            Dict with team info and player lists by position
        """
        if season is None:
            season = await self.get_current_season()

        # Fetch roster from NHL API
        data = await self.get_json(f"/roster/{team_abbrev}/current")

        roster = {
            "team_abbrev": team_abbrev,
            "season": season,
            "as_of_date": datetime.now().isoformat(),
            "forwards": [],
            "defensemen": [],
            "goalies": [],
        }

        # Process each position group
        for player_data in data.get("forwards", []):
            roster["forwards"].append(self._parse_player(player_data))

        for player_data in data.get("defensemen", []):
            roster["defensemen"].append(self._parse_player(player_data))

        for player_data in data.get("goalies", []):
            roster["goalies"].append(self._parse_player(player_data))

        self.logger.info(
            "scraped_roster",
            team=team_abbrev,
            forwards=len(roster["forwards"]),
            defensemen=len(roster["defensemen"]),
            goalies=len(roster["goalies"]),
        )

        return roster

    def _parse_player(self, data: dict[str, Any]) -> dict[str, Any]:
        """Parse player data from API response."""
        return {
            "player_id": data.get("id"),
            "first_name": data.get("firstName", {}).get("default", ""),
            "last_name": data.get("lastName", {}).get("default", ""),
            "jersey_number": data.get("sweaterNumber"),
            "position": data.get("positionCode"),
            "shoots_catches": data.get("shootsCatches"),
            "height_inches": data.get("heightInInches"),
            "weight_pounds": data.get("weightInPounds"),
            "birth_date": data.get("birthDate"),
            "birth_city": data.get("birthCity", {}).get("default"),
            "birth_country": data.get("birthCountry"),
            "nationality": data.get("nationality"),
        }

    async def scrape_all_rosters(self, season: str | None = None) -> list[dict[str, Any]]:
        """
        Fetch rosters for all NHL teams.

        Args:
            season: Season ID. Uses current season if None.

        Returns:
            List of roster dicts for all teams
        """
        if season is None:
            season = await self.get_current_season()

        rosters = []
        for team in NHL_TEAMS:
            try:
                roster = await self.scrape_roster(team, season)
                rosters.append(roster)
            except Exception as e:
                self.logger.warning("roster_scrape_failed", team=team, error=str(e))

        self.logger.info("scraped_all_rosters", count=len(rosters), season=season)
        return rosters

    async def scrape_player_details(self, player_id: int) -> dict[str, Any]:
        """
        Fetch detailed info for a specific player.

        Args:
            player_id: NHL player ID

        Returns:
            Dict with comprehensive player data
        """
        data = await self.get_json(f"/player/{player_id}/landing")

        player = {
            "id": player_id,
            "first_name": data.get("firstName", {}).get("default"),
            "last_name": data.get("lastName", {}).get("default"),
            "birth_date": data.get("birthDate"),
            "birth_city": data.get("birthCity", {}).get("default"),
            "birth_state": data.get("birthStateProvince", {}).get("default"),
            "birth_country": data.get("birthCountry"),
            "nationality": data.get("nationality"),
            "height_inches": data.get("heightInInches"),
            "weight_pounds": data.get("weightInPounds"),
            "position": data.get("position"),
            "shoots_catches": data.get("shootsCatches"),
            "team_abbrev": data.get("currentTeamAbbrev"),
            "team_id": data.get("currentTeamId"),
            "jersey_number": data.get("sweaterNumber"),
            "is_active": data.get("isActive", True),
            "in_top_100": data.get("inTop100AllTime", False),
            "in_hhof": data.get("inHHOF", False),
            # Draft info
            "draft_year": data.get("draftDetails", {}).get("year"),
            "draft_round": data.get("draftDetails", {}).get("round"),
            "draft_pick": data.get("draftDetails", {}).get("pickInRound"),
            "draft_overall": data.get("draftDetails", {}).get("overallPick"),
            "draft_team": data.get("draftDetails", {}).get("teamAbbrev"),
            # Career totals
            "career_stats": data.get("careerTotals"),
            # Recent seasons
            "season_stats": data.get("seasonTotals", [])[:5],  # Last 5 seasons
            # Awards
            "awards": data.get("awards", []),
        }

        self.logger.debug("scraped_player_details", player_id=player_id)
        return player

    async def scrape_all_skater_stats(self, season: str | None = None) -> list[dict[str, Any]]:
        """
        Fetch comprehensive stats for all skaters in a season.
        Uses the NHL stats API endpoint.

        Args:
            season: Season ID (e.g., '20242025')

        Returns:
            List of player stat dicts
        """
        if season is None:
            season = await self.get_current_season()

        # Use the stats.nhl.com API for comprehensive stats
        stats_url = "https://api.nhle.com/stats/rest/en/skater/summary"

        players = []
        start = 0
        limit = 100

        while True:
            params = {
                "isAggregate": "false",
                "isGame": "false",
                "sort": '[{"property":"points","direction":"DESC"}]',
                "start": start,
                "limit": limit,
                "cayenneExp": f"seasonId={season} and gameTypeId=2",
            }

            # Need to use full URL since it's a different base
            response = await self.client.get(stats_url, params=params)
            response.raise_for_status()
            data = response.json()

            batch = data.get("data", [])
            if not batch:
                break

            for p in batch:
                players.append(
                    {
                        "player_id": p.get("playerId"),
                        "player_name": p.get("skaterFullName"),
                        "team_abbrev": p.get("teamAbbrevs"),
                        "position": p.get("positionCode"),
                        "season": season,
                        "games_played": p.get("gamesPlayed", 0),
                        "goals": p.get("goals", 0),
                        "assists": p.get("assists", 0),
                        "points": p.get("points", 0),
                        "plus_minus": p.get("plusMinus", 0),
                        "pim": p.get("penaltyMinutes", 0),
                        "ppg": p.get("ppGoals", 0),
                        "ppp": p.get("ppPoints", 0),
                        "shg": p.get("shGoals", 0),
                        "shp": p.get("shPoints", 0),
                        "gwg": p.get("gameWinningGoals", 0),
                        "otg": p.get("otGoals", 0),
                        "shots": p.get("shots", 0),
                        "shot_pct": p.get("shootingPct"),
                        "toi_per_game": p.get("timeOnIcePerGame"),
                        "faceoff_pct": p.get("faceoffWinPct"),
                    }
                )

            if len(batch) < limit:
                break
            start += limit

        self.logger.info("scraped_all_skaters", count=len(players), season=season)
        return players

    async def scrape_all_goalie_stats(self, season: str | None = None) -> list[dict[str, Any]]:
        """
        Fetch comprehensive stats for all goalies in a season.

        Args:
            season: Season ID (e.g., '20242025')

        Returns:
            List of goalie stat dicts
        """
        if season is None:
            season = await self.get_current_season()

        stats_url = "https://api.nhle.com/stats/rest/en/goalie/summary"

        goalies = []
        start = 0
        limit = 100

        while True:
            params = {
                "isAggregate": "false",
                "isGame": "false",
                "sort": '[{"property":"wins","direction":"DESC"}]',
                "start": start,
                "limit": limit,
                "cayenneExp": f"seasonId={season} and gameTypeId=2",
            }

            response = await self.client.get(stats_url, params=params)
            response.raise_for_status()
            data = response.json()

            batch = data.get("data", [])
            if not batch:
                break

            for g in batch:
                goalies.append(
                    {
                        "player_id": g.get("playerId"),
                        "player_name": g.get("goalieFullName"),
                        "team_abbrev": g.get("teamAbbrevs"),
                        "season": season,
                        "games_played": g.get("gamesPlayed", 0),
                        "games_started": g.get("gamesStarted", 0),
                        "wins": g.get("wins", 0),
                        "losses": g.get("losses", 0),
                        "ot_losses": g.get("otLosses", 0),
                        "shutouts": g.get("shutouts", 0),
                        "shots_against": g.get("shotsAgainst", 0),
                        "goals_against": g.get("goalsAgainst", 0),
                        "saves": g.get("saves", 0),
                        "save_pct": g.get("savePct"),
                        "gaa": g.get("goalsAgainstAverage"),
                        "toi_seconds": g.get("timeOnIce"),
                    }
                )

            if len(batch) < limit:
                break
            start += limit

        self.logger.info("scraped_all_goalies", count=len(goalies), season=season)
        return goalies

    # Abstract method implementations required by BaseScraper
    async def scrape_players(self, season: str | None = None) -> list[dict[str, Any]]:
        """Scrape all players (skaters + goalies)."""
        skaters = await self.scrape_all_skater_stats(season)
        goalies = await self.scrape_all_goalie_stats(season)
        return skaters + goalies

    async def scrape_teams(self) -> list[dict[str, Any]]:
        """Scrape team info (delegate to roster data)."""
        rosters = await self.scrape_all_rosters()
        return [{"abbreviation": r["team_abbrev"]} for r in rosters]

    async def scrape_games(
        self,
        season: str | None = None,
        team_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Not implemented - use NHLAPIScraper for games."""
        return []
