"""NHL Official API scraper using the new api-web.nhle.com endpoint."""

from datetime import datetime
from typing import Any

from .base import BaseScraper


class NHLAPIScraper(BaseScraper):
    """Scraper for the official NHL API."""

    SOURCE_NAME = "nhl_api"
    BASE_URL = "https://api-web.nhle.com/v1"
    REQUESTS_PER_SECOND = 1.0  # Be polite

    async def get_current_season(self) -> str:
        """Get the current season ID (e.g., '20232024')."""
        # NHL season starts in October, so adjust year accordingly
        now = datetime.now()
        year = now.year if now.month >= 10 else now.year - 1
        return f"{year}{year + 1}"

    async def scrape_teams(self) -> list[dict[str, Any]]:
        """Fetch all NHL teams."""
        data = await self.get_json("/standings/now")
        teams = []

        for record in data.get("standings", []):
            teams.append({
                "id": record.get("teamAbbrev", {}).get("default"),
                "name": record.get("teamName", {}).get("default"),
                "abbreviation": record.get("teamAbbrev", {}).get("default"),
                "conference": record.get("conferenceName"),
                "division": record.get("divisionName"),
                "wins": record.get("wins"),
                "losses": record.get("losses"),
                "ot_losses": record.get("otLosses"),
                "points": record.get("points"),
                "games_played": record.get("gamesPlayed"),
            })

        self.logger.info("scraped_teams", count=len(teams))
        return teams

    async def scrape_players(self, season: str | None = None) -> list[dict[str, Any]]:
        """Fetch player stats for a season."""
        if season is None:
            season = await self.get_current_season()

        # Get skater stats
        skaters = await self._scrape_skater_stats(season)
        goalies = await self._scrape_goalie_stats(season)

        all_players = skaters + goalies
        self.logger.info("scraped_players", count=len(all_players), season=season)
        return all_players

    async def _scrape_skater_stats(self, season: str) -> list[dict[str, Any]]:
        """Fetch skater statistics."""
        players = []
        limit = 100
        start = 0

        while True:
            data = await self.get_json(
                f"/skater-stats-leaders/{season}/2",
                params={"categories": "points", "limit": limit, "start": start},
            )

            batch = data.get("points", [])
            if not batch:
                break

            for p in batch:
                players.append({
                    "id": p.get("playerId"),
                    "name": f"{p.get('firstName', {}).get('default', '')} {p.get('lastName', {}).get('default', '')}".strip(),
                    "team": p.get("teamAbbrev"),
                    "position": p.get("positionCode"),
                    "goals": p.get("goals"),
                    "assists": p.get("assists"),
                    "points": p.get("value"),
                    "games_played": p.get("gamesPlayed"),
                    "player_type": "skater",
                })

            if len(batch) < limit:
                break
            start += limit

        return players

    async def _scrape_goalie_stats(self, season: str) -> list[dict[str, Any]]:
        """Fetch goalie statistics."""
        data = await self.get_json(
            f"/goalie-stats-leaders/{season}/2",
            params={"categories": "wins", "limit": 100},
        )

        goalies = []
        for g in data.get("wins", []):
            goalies.append({
                "id": g.get("playerId"),
                "name": f"{g.get('firstName', {}).get('default', '')} {g.get('lastName', {}).get('default', '')}".strip(),
                "team": g.get("teamAbbrev"),
                "position": "G",
                "wins": g.get("value"),
                "games_played": g.get("gamesPlayed"),
                "player_type": "goalie",
            })

        return goalies

    async def scrape_games(
        self,
        season: str | None = None,
        team_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch game schedule and results."""
        if season is None:
            season = await self.get_current_season()

        # Get schedule for the season
        data = await self.get_json(f"/schedule/{season[:4]}-10-01")

        games = []
        for week in data.get("gameWeek", []):
            for game in week.get("games", []):
                games.append({
                    "id": game.get("id"),
                    "date": game.get("gameDate"),
                    "game_type": game.get("gameType"),
                    "home_team": game.get("homeTeam", {}).get("abbrev"),
                    "away_team": game.get("awayTeam", {}).get("abbrev"),
                    "home_score": game.get("homeTeam", {}).get("score"),
                    "away_score": game.get("awayTeam", {}).get("score"),
                    "game_state": game.get("gameState"),
                    "venue": game.get("venue", {}).get("default"),
                })

        self.logger.info("scraped_games", count=len(games))
        return games

    async def scrape_player_details(self, player_id: int) -> dict[str, Any]:
        """Fetch detailed info for a specific player."""
        data = await self.get_json(f"/player/{player_id}/landing")

        return {
            "id": player_id,
            "first_name": data.get("firstName", {}).get("default"),
            "last_name": data.get("lastName", {}).get("default"),
            "birth_date": data.get("birthDate"),
            "birth_city": data.get("birthCity", {}).get("default"),
            "birth_country": data.get("birthCountry"),
            "height_inches": data.get("heightInInches"),
            "weight_pounds": data.get("weightInPounds"),
            "position": data.get("position"),
            "shoots_catches": data.get("shootsCatches"),
            "team": data.get("currentTeamAbbrev"),
            "jersey_number": data.get("sweaterNumber"),
            "draft_year": data.get("draftDetails", {}).get("year"),
            "draft_round": data.get("draftDetails", {}).get("round"),
            "draft_pick": data.get("draftDetails", {}).get("pickInRound"),
            "career_stats": data.get("careerTotals"),
        }

    async def scrape_standings(self) -> dict[str, Any]:
        """Fetch current league standings."""
        data = await self.get_json("/standings/now")

        standings = {
            "as_of": data.get("standingsDate"),
            "teams": [],
        }

        for team in data.get("standings", []):
            standings["teams"].append({
                "team": team.get("teamAbbrev", {}).get("default"),
                "conference": team.get("conferenceName"),
                "division": team.get("divisionName"),
                "games_played": team.get("gamesPlayed"),
                "wins": team.get("wins"),
                "losses": team.get("losses"),
                "ot_losses": team.get("otLosses"),
                "points": team.get("points"),
                "points_pct": team.get("pointPctg"),
                "goals_for": team.get("goalFor"),
                "goals_against": team.get("goalAgainst"),
                "goal_diff": team.get("goalDifferential"),
                "regulation_wins": team.get("regulationWins"),
                "streak": team.get("streakCode"),
            })

        return standings
