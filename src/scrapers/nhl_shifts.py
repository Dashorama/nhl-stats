"""NHL shift-chart scraper.

Shift charts live on the stats REST host rather than api-web:

    https://api.nhle.com/stats/rest/en/shiftcharts?cayenneExp=gameId=2018020001

One row per player shift, with start/end times, period and duration. Verified
available back to at least 2018-19 (833 rows for a single 2018 game).
"""

from typing import Any

from .base import BaseScraper


class NHLShiftChartScraper(BaseScraper):
    """Scraper for NHL shift charts."""

    SOURCE_NAME = "nhl_shifts"
    BASE_URL = "https://api.nhle.com/stats/rest/en"
    REQUESTS_PER_SECOND = 2.0

    #: The endpoint returns goal markers (typeCode 505, shiftNumber 0, no duration)
    #: alongside the shifts themselves. Only 517 rows are shifts.
    SHIFT_TYPE_CODE = 517

    async def scrape_shifts(self, game_id: int) -> list[dict[str, Any]]:
        """Fetch every player shift for a single game."""
        data = await self.get_json(
            "/shiftcharts",
            params={"cayenneExp": f"gameId={game_id}"},
        )
        shifts = self.parse_shifts(data)
        self.logger.info("scraped_shifts", game_id=game_id, count=len(shifts))
        return shifts

    @staticmethod
    def parse_shifts(payload: dict[str, Any]) -> list[dict[str, Any]]:
        """Parse a shiftcharts payload into ``shifts`` table records.

        Only actual shifts are kept. The endpoint also returns goal markers, which
        share a player, period and a shiftNumber of 0, so storing them would
        collide on the shifts natural key and they are not shifts anyway.

        Rows missing any part of that key are dropped for the same reason.
        """
        shifts: list[dict[str, Any]] = []

        for row in payload.get("data") or []:
            if row.get("typeCode") != NHLShiftChartScraper.SHIFT_TYPE_CODE:
                continue

            game_id = row.get("gameId")
            player_id = row.get("playerId")
            period = row.get("period")
            shift_number = row.get("shiftNumber")
            if None in (game_id, player_id, period, shift_number):
                continue

            first = row.get("firstName") or ""
            last = row.get("lastName") or ""

            shifts.append(
                {
                    "game_id": game_id,
                    "player_id": player_id,
                    "player_name": f"{first} {last}".strip(),
                    "team_abbrev": row.get("teamAbbrev"),
                    "team_id": row.get("teamId"),
                    "period": period,
                    "shift_number": shift_number,
                    "start_time": row.get("startTime"),
                    "end_time": row.get("endTime"),
                    "duration": row.get("duration"),
                    "type_code": row.get("typeCode"),
                    "detail_code": row.get("detailCode"),
                    "event_number": row.get("eventNumber"),
                }
            )

        return shifts

    # Abstract method implementations required by BaseScraper
    async def scrape_players(self, season: str | None = None) -> list[dict[str, Any]]:
        """Not applicable -- shift charts are fetched per game."""
        return []

    async def scrape_teams(self) -> list[dict[str, Any]]:
        """Not applicable -- shift charts are fetched per game."""
        return []

    async def scrape_games(
        self,
        season: str | None = None,
        team_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Not applicable -- shift charts are fetched per game."""
        return []
