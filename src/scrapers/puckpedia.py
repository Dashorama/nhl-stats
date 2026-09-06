"""PuckPedia contract data scraper.

PuckPedia provides NHL contract information including:
- Salary and cap hit
- Contract length and expiry
- UFA/RFA status
- Trade clauses (NMC/NTC)

Note: This scrapes HTML as there is no public API.
Be respectful with request rates.
"""

import re
from datetime import datetime
from typing import Any

from bs4 import BeautifulSoup

from .base import BaseScraper

# Team URL slugs on PuckPedia
TEAM_SLUGS = {
    "ANA": "anaheim-ducks",
    "BOS": "boston-bruins",
    "BUF": "buffalo-sabres",
    "CAR": "carolina-hurricanes",
    "CBJ": "columbus-blue-jackets",
    "CGY": "calgary-flames",
    "CHI": "chicago-blackhawks",
    "COL": "colorado-avalanche",
    "DAL": "dallas-stars",
    "DET": "detroit-red-wings",
    "EDM": "edmonton-oilers",
    "FLA": "florida-panthers",
    "LAK": "los-angeles-kings",
    "MIN": "minnesota-wild",
    "MTL": "montreal-canadiens",
    "NJD": "new-jersey-devils",
    "NSH": "nashville-predators",
    "NYI": "new-york-islanders",
    "NYR": "new-york-rangers",
    "OTT": "ottawa-senators",
    "PHI": "philadelphia-flyers",
    "PIT": "pittsburgh-penguins",
    "SEA": "seattle-kraken",
    "SJS": "san-jose-sharks",
    "STL": "st-louis-blues",
    "TBL": "tampa-bay-lightning",
    "TOR": "toronto-maple-leafs",
    "UTA": "utah-hockey-club",
    "VAN": "vancouver-canucks",
    "VGK": "vegas-golden-knights",
    "WPG": "winnipeg-jets",
    "WSH": "washington-capitals",
}


class PuckPediaScraper(BaseScraper):
    """Scraper for PuckPedia contract data."""

    SOURCE_NAME = "puckpedia"
    BASE_URL = "https://puckpedia.com"
    REQUESTS_PER_SECOND = 0.3  # Very conservative - respect their servers

    def _parse_salary(self, text: str) -> int:
        """Parse salary string like '$1,500,000' or '$1.5M' to int."""
        if not text:
            return 0
        text = text.strip().replace("$", "").replace(",", "")

        # Handle M suffix (millions)
        if "M" in text.upper():
            text = text.upper().replace("M", "")
            try:
                return int(float(text) * 1_000_000)
            except ValueError:
                return 0

        # Handle K suffix (thousands)
        if "K" in text.upper():
            text = text.upper().replace("K", "")
            try:
                return int(float(text) * 1_000)
            except ValueError:
                return 0

        try:
            return int(float(text))
        except ValueError:
            return 0

    async def scrape_team_contracts(self, team_abbrev: str) -> list[dict[str, Any]]:
        """
        Scrape all contract data for a team.

        Args:
            team_abbrev: Team abbreviation (e.g., 'TOR')

        Returns:
            List of contract dicts for all players on the team
        """
        slug = TEAM_SLUGS.get(team_abbrev)
        if not slug:
            self.logger.warning("unknown_team", team=team_abbrev)
            return []

        try:
            response = await self.get(f"/{slug}/cap")
            soup = BeautifulSoup(response.text, "lxml")
        except Exception as e:
            self.logger.error("puckpedia_fetch_failed", team=team_abbrev, error=str(e))
            return []

        contracts = []

        # Find contract tables
        tables = soup.find_all("table", class_=re.compile(r"cap-table|roster-table", re.I))
        if not tables:
            # Try alternative selectors
            tables = soup.find_all("table")

        for table in tables:
            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all(["td", "th"])
                if len(cells) < 3:
                    continue

                try:
                    contract = self._parse_contract_row(cells, team_abbrev)
                    if contract and contract.get("player_name"):
                        contracts.append(contract)
                except Exception as e:
                    self.logger.debug("parse_row_failed", error=str(e))

        self.logger.info("scraped_team_contracts", team=team_abbrev, count=len(contracts))
        return contracts

    def _parse_contract_row(
        self,
        cells: list,
        team_abbrev: str,
    ) -> dict[str, Any] | None:
        """Parse a table row into contract data."""
        # This is a simplified parser - actual PuckPedia HTML structure varies
        # and may need adjustment based on their current layout

        cell_texts = [c.get_text(strip=True) for c in cells]

        # Skip header rows
        if any(h in cell_texts[0].lower() for h in ["player", "name", "pos"]):
            return None

        # Try to extract player name from first cell (may contain link)
        player_cell = cells[0]
        player_link = player_cell.find("a")
        player_name = player_link.get_text(strip=True) if player_link else cell_texts[0]

        if not player_name or len(player_name) < 2:
            return None

        # Extract cap hit (usually in a cell with $ sign)
        cap_hit = 0
        salary = 0
        expiry_status = None

        for i, text in enumerate(cell_texts[1:], 1):
            if "$" in text:
                value = self._parse_salary(text)
                if cap_hit == 0:
                    cap_hit = value
                elif salary == 0:
                    salary = value
            elif text.upper() in ("UFA", "RFA", "10.2(C)"):
                expiry_status = text.upper()

        # Look for contract years
        years_match = re.search(r"(\d+)\s*(?:yr|year)", " ".join(cell_texts), re.I)
        total_years = int(years_match.group(1)) if years_match else 1

        # Detect clauses
        row_text = " ".join(cell_texts).upper()
        has_nmc = "NMC" in row_text or "NO-MOVE" in row_text
        has_ntc = "NTC" in row_text or "NO-TRADE" in row_text

        return {
            "player_name": player_name,
            "team_abbrev": team_abbrev,
            "current_cap_hit": cap_hit,
            "current_salary": salary if salary else cap_hit,
            "aav": cap_hit,
            "total_years": total_years,
            "expiry_status": expiry_status,
            "has_nmc": has_nmc,
            "has_ntc": has_ntc,
            "source": "puckpedia",
            "scraped_at": datetime.now().isoformat(),
        }

    async def scrape_all_contracts(self) -> list[dict[str, Any]]:
        """
        Scrape contract data for all NHL teams.

        Returns:
            List of all contract dicts
        """
        all_contracts = []

        for team_abbrev in TEAM_SLUGS:
            try:
                contracts = await self.scrape_team_contracts(team_abbrev)
                all_contracts.extend(contracts)
            except Exception as e:
                self.logger.warning(
                    "team_contracts_failed",
                    team=team_abbrev,
                    error=str(e),
                )

        self.logger.info("scraped_all_contracts", count=len(all_contracts))
        return all_contracts

    async def scrape_player_contract(self, player_name: str) -> dict[str, Any] | None:
        """
        Scrape detailed contract for a specific player.

        Args:
            player_name: Player's name (e.g., "Connor McDavid")

        Returns:
            Contract dict or None if not found
        """
        # Convert name to URL slug
        slug = player_name.lower().replace(" ", "-").replace("'", "")
        slug = re.sub(r"[^a-z0-9-]", "", slug)

        try:
            response = await self.get(f"/player/{slug}")
            soup = BeautifulSoup(response.text, "lxml")
        except Exception as e:
            self.logger.warning("player_lookup_failed", player=player_name, error=str(e))
            return None

        contract = {
            "player_name": player_name,
            "source": "puckpedia",
            "scraped_at": datetime.now().isoformat(),
        }

        # Parse contract details from page
        # This is a simplified parser - actual structure varies

        # Look for cap hit
        cap_hit_elem = soup.find(text=re.compile(r"cap hit", re.I))
        if cap_hit_elem:
            parent = cap_hit_elem.find_parent()
            if parent:
                value = parent.find_next(text=re.compile(r"\$"))
                if value:
                    contract["current_cap_hit"] = self._parse_salary(str(value))

        # Look for term
        term_elem = soup.find(text=re.compile(r"term|years", re.I))
        if term_elem:
            parent = term_elem.find_parent()
            if parent:
                match = re.search(r"(\d+)", parent.get_text())
                if match:
                    contract["total_years"] = int(match.group(1))

        # Look for expiry status
        for status in ["UFA", "RFA"]:
            if soup.find(text=re.compile(status)):
                contract["expiry_status"] = status
                break

        # Look for clauses
        page_text = soup.get_text().upper()
        contract["has_nmc"] = "NMC" in page_text or "NO-MOVEMENT" in page_text
        contract["has_ntc"] = "NTC" in page_text or "NO-TRADE" in page_text

        return contract

    # Abstract method implementations required by BaseScraper
    async def scrape_players(self, season: str | None = None) -> list[dict[str, Any]]:
        """Scrape all player contracts."""
        return await self.scrape_all_contracts()

    async def scrape_teams(self) -> list[dict[str, Any]]:
        """Not applicable for PuckPedia."""
        return []

    async def scrape_games(
        self,
        season: str | None = None,
        team_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Not applicable for PuckPedia."""
        return []
