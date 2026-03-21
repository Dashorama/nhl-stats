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
        """Fetch skater statistics.

        The leaders endpoint doesn't support real pagination (start param is ignored),
        so we request all skaters in a single call with a high limit.
        """
        data = await self.get_json(
            f"/skater-stats-leaders/{season}/2",
            params={"categories": "points", "limit": 1000},
        )

        players = []
        for p in data.get("points", []):
            first = p.get("firstName", {}).get("default", "") if isinstance(p.get("firstName"), dict) else p.get("firstName", "")
            last = p.get("lastName", {}).get("default", "") if isinstance(p.get("lastName"), dict) else p.get("lastName", "")
            players.append({
                "id": p.get("id"),
                "first_name": first,
                "last_name": last,
                "name": f"{first} {last}".strip(),
                "team": p.get("teamAbbrev"),
                "position": p.get("position"),
                "points": p.get("value"),
                "player_type": "skater",
            })

        return players

    async def _scrape_goalie_stats(self, season: str) -> list[dict[str, Any]]:
        """Fetch goalie statistics."""
        data = await self.get_json(
            f"/goalie-stats-leaders/{season}/2",
            params={"categories": "wins", "limit": 100},
        )

        goalies = []
        for g in data.get("wins", []):
            first = g.get("firstName", {}).get("default", "") if isinstance(g.get("firstName"), dict) else g.get("firstName", "")
            last = g.get("lastName", {}).get("default", "") if isinstance(g.get("lastName"), dict) else g.get("lastName", "")
            goalies.append({
                "id": g.get("id"),
                "first_name": first,
                "last_name": last,
                "name": f"{first} {last}".strip(),
                "team": g.get("teamAbbrev"),
                "position": "G",
                "wins": g.get("value"),
                "player_type": "goalie",
            })

        return goalies

    async def scrape_games(
        self,
        season: str | None = None,
        team_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch game schedule and results for the full season.

        The schedule endpoint returns one week at a time, so we paginate
        using the nextStartDate field until we pass the season end date.
        """
        if season is None:
            season = await self.get_current_season()

        games = []
        current_date = f"{season[:4]}-10-01"
        season_end = f"{season[4:]}-07-01"  # Well past any playoff end

        while current_date and current_date < season_end:
            data = await self.get_json(f"/schedule/{current_date}")

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

            current_date = data.get("nextStartDate")

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

    async def scrape_draft(self, year: int | None = None) -> list[dict[str, Any]]:
        """Fetch draft rankings/picks for a given year."""
        if year is None:
            year = datetime.now().year

        data = await self.get_json(
            f"/draft/rankings/{year}/1",
            # Note: this is on api-web.nhle.com, same base URL
        )

        picks = []
        for rank, p in enumerate(data.get("rankings", []), 1):
            picks.append({
                "draft_year": year,
                "rank": rank,
                "first_name": p.get("firstName", ""),
                "last_name": p.get("lastName", ""),
                "position": p.get("positionCode"),
                "shoots_catches": p.get("shootsCatches"),
                "height_inches": p.get("heightInInches"),
                "weight_pounds": p.get("weightInPounds"),
                "amateur_club": p.get("lastAmateurClub"),
                "amateur_league": p.get("lastAmateurLeague"),
                "birth_date": p.get("birthDate"),
                "birth_country": p.get("birthCountry"),
                "midterm_rank": p.get("midtermRank"),
                "final_rank": p.get("finalRank"),
            })

        self.logger.info("scraped_draft", year=year, count=len(picks))
        return picks

    async def scrape_boxscore(self, game_id: int) -> dict[str, Any]:
        """Fetch boxscore for a single game."""
        data = await self.get_json(f"/gamecenter/{game_id}/boxscore")

        players = []
        home_abbrev = data.get("homeTeam", {}).get("abbrev", "")
        away_abbrev = data.get("awayTeam", {}).get("abbrev", "")

        pg = data.get("playerByGameStats", {})

        for side, is_home in [("homeTeam", True), ("awayTeam", False)]:
            team_data = pg.get(side, {})
            team_abbrev = home_abbrev if is_home else away_abbrev

            for group in ["forwards", "defense", "goalies"]:
                for p in team_data.get(group, []):
                    player = {
                        "player_id": p.get("playerId"),
                        "player_name": p.get("name", {}).get("default", ""),
                        "team_abbrev": team_abbrev,
                        "position": p.get("position"),
                        "is_home": is_home,
                    }

                    if group == "goalies":
                        player.update({
                            "saves": p.get("saves", 0),
                            "shots_against": p.get("shotsAgainst", 0),
                            "goals_against": p.get("goalsAgainst", 0),
                            "toi": p.get("toi"),
                        })
                    else:
                        player.update({
                            "goals": p.get("goals", 0),
                            "assists": p.get("assists", 0),
                            "points": p.get("points", 0),
                            "plus_minus": p.get("plusMinus", 0),
                            "pim": p.get("pim", 0),
                            "hits": p.get("hits", 0),
                            "shots": p.get("sog", 0),
                            "blocked_shots": p.get("blockedShots", 0),
                            "faceoff_pct": p.get("faceoffWinningPctg"),
                            "toi": p.get("toi"),
                            "shifts": p.get("shifts", 0),
                            "giveaways": p.get("giveaways", 0),
                            "takeaways": p.get("takeaways", 0),
                            "power_play_goals": p.get("powerPlayGoals", 0),
                        })

                    players.append(player)

        return {"game_id": game_id, "players": players}

    async def scrape_play_by_play(self, game_id: int) -> list[dict[str, Any]]:
        """Fetch play-by-play events for a single game."""
        data = await self.get_json(f"/gamecenter/{game_id}/play-by-play")

        events = []
        for play in data.get("plays", []):
            details = play.get("details", {})
            event_type = play.get("typeDescKey", "")
            period_desc = play.get("periodDescriptor", {})

            event = {
                "event_id": play.get("eventId"),
                "event_type": event_type,
                "period": period_desc.get("number"),
                "period_type": period_desc.get("periodType"),
                "time_in_period": play.get("timeInPeriod"),
                "time_remaining": play.get("timeRemaining"),
                "x_coord": details.get("xCoord"),
                "y_coord": details.get("yCoord"),
                "zone_code": details.get("zoneCode"),
                "team_id": details.get("eventOwnerTeamId"),
                "shot_type": details.get("shotType"),
            }

            # Map players based on event type
            if event_type == "goal":
                event["player1_id"] = details.get("scoringPlayerId")
                event["player2_id"] = details.get("assist1PlayerId")
                event["player3_id"] = details.get("assist2PlayerId")
            elif event_type == "shot-on-goal":
                event["player1_id"] = details.get("shootingPlayerId")
                event["player2_id"] = details.get("goalieInNetId")
            elif event_type == "missed-shot":
                event["player1_id"] = details.get("shootingPlayerId")
                event["player2_id"] = details.get("goalieInNetId")
            elif event_type == "blocked-shot":
                event["player1_id"] = details.get("shootingPlayerId")
                event["player2_id"] = details.get("blockingPlayerId")
            elif event_type == "hit":
                event["player1_id"] = details.get("hittingPlayerId")
                event["player2_id"] = details.get("hitteePlayerId")
            elif event_type == "faceoff":
                event["player1_id"] = details.get("winningPlayerId")
                event["player2_id"] = details.get("losingPlayerId")
            elif event_type == "penalty":
                event["player1_id"] = details.get("committedByPlayerId")
                event["player2_id"] = details.get("drawnByPlayerId")
                event["description"] = details.get("descKey")
            elif event_type in ("giveaway", "takeaway"):
                event["player1_id"] = details.get("playerId")

            events.append(event)

        self.logger.info("scraped_play_by_play", game_id=game_id, events=len(events))
        return events

    async def scrape_player_game_log(self, player_id: int, season: str | None = None) -> list[dict[str, Any]]:
        """Fetch game-by-game stats for a player."""
        if season is None:
            season = await self.get_current_season()

        data = await self.get_json(f"/player/{player_id}/game-log/{season}/2")

        logs = []
        for g in data.get("gameLog", []):
            logs.append({
                "game_id": g.get("gameId"),
                "team_abbrev": g.get("teamAbbrev"),
                "opponent_abbrev": g.get("opponentAbbrev"),
                "game_date": g.get("gameDate"),
                "home_road": g.get("homeRoadFlag"),
                "goals": g.get("goals", 0),
                "assists": g.get("assists", 0),
                "points": g.get("points", 0),
                "plus_minus": g.get("plusMinus", 0),
                "pim": g.get("pim", 0),
                "shots": g.get("shots", 0),
                "shifts": g.get("shifts", 0),
                "toi": g.get("toi"),
                "power_play_goals": g.get("powerPlayGoals", 0),
                "power_play_points": g.get("powerPlayPoints", 0),
                "shorthanded_goals": g.get("shorthandedGoals", 0),
                "game_winning_goals": g.get("gameWinningGoals", 0),
                "ot_goals": g.get("otGoals", 0),
            })

        return logs

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
