"""Scraper for NHL player injury/availability status."""
import httpx
import structlog

from ..storage.database import Database

logger = structlog.get_logger()

BASE_URL = "https://api-web.nhle.com/v1"

NHL_TEAMS = [
    "ANA","BOS","BUF","CAR","CBJ","CGY","CHI","COL","DAL","DET",
    "EDM","FLA","LAK","MIN","MTL","NJD","NSH","NYI","NYR","OTT",
    "PHI","PIT","SEA","SJS","STL","TBL","TOR","UTA","VAN","VGK",
    "WSH","WPG",
]

STATUS_MAP = {
    "IR": "IR",
    "INJURED_RESERVE": "IR",
    "LONG_TERM_INJURED_RESERVE": "LTIR",
    "LTIR": "LTIR",
    "DAY_TO_DAY": "DTD",
    "ACTIVE": "HEALTHY",
    "SUSPENDED": "SUSPENDED",
}


class NHLInjuriesScraper:
    async def scrape_all(self, db: Database) -> dict:
        records = []
        errors = []

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            for team in NHL_TEAMS:
                try:
                    resp = await client.get(f"{BASE_URL}/roster/{team}/current")
                    resp.raise_for_status()
                    data = resp.json()
                    for group in ("forwards", "defensemen", "goalies"):
                        for player in data.get(group, []):
                            roster_status = player.get("rosterStatus", "ACTIVE")
                            status = STATUS_MAP.get(roster_status, "HEALTHY")
                            records.append({
                                "player_id": player["id"],
                                "player_name": (
                                    f"{player['firstName']['default']} "
                                    f"{player['lastName']['default']}"
                                ),
                                "team_abbrev": team,
                                "status": status,
                                "detail": None,
                            })
                except Exception as e:
                    logger.error("injury_scrape_failed", team=team, error=str(e))
                    errors.append(team)

        if records:
            db.upsert_injuries(records)

        logger.info("scraped_injuries", players=len(records), errors=len(errors))
        return {"players": len(records), "errors": errors}
