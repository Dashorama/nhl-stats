"""Tests for scraper modules."""

import pytest
from src.scrapers import NHLAPIScraper


@pytest.mark.asyncio
async def test_nhl_api_scraper_init():
    """Test NHL API scraper initialization."""
    scraper = NHLAPIScraper()
    assert scraper.SOURCE_NAME == "nhl_api"
    assert scraper.BASE_URL == "https://api-web.nhle.com/v1"
    assert scraper.REQUESTS_PER_SECOND == 1.0


@pytest.mark.asyncio
async def test_get_current_season():
    """Test current season calculation."""
    scraper = NHLAPIScraper()
    season = await scraper.get_current_season()
    
    # Should be 8 characters (e.g., "20242025")
    assert len(season) == 8
    assert season.isdigit()
    
    # Second half should be first half + 1
    year1 = int(season[:4])
    year2 = int(season[4:])
    assert year2 == year1 + 1


@pytest.mark.asyncio
@pytest.mark.integration
async def test_scrape_teams():
    """Integration test: scrape real team data."""
    async with NHLAPIScraper() as scraper:
        teams = await scraper.scrape_teams()
        
        assert len(teams) >= 32  # At least 32 NHL teams
        
        # Check structure
        team = teams[0]
        assert "abbreviation" in team or "id" in team
        assert "name" in team


@pytest.mark.asyncio
@pytest.mark.integration
async def test_scrape_standings():
    """Integration test: scrape current standings."""
    async with NHLAPIScraper() as scraper:
        standings = await scraper.scrape_standings()
        
        assert "teams" in standings
        assert len(standings["teams"]) >= 32
        
        # Check team structure
        team = standings["teams"][0]
        assert "wins" in team
        assert "losses" in team
        assert "points" in team
