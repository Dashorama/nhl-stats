"""Scraper modules for various NHL data sources."""

from .base import BaseScraper
from .moneypuck import MoneyPuckScraper
from .nhl_api import NHLAPIScraper
from .nhl_injuries import NHLInjuriesScraper
from .nhl_roster import NHLRosterScraper
from .puckpedia import PuckPediaScraper
from .yahoo_fantasy import YahooFantasyClient

__all__ = [
    "BaseScraper",
    "NHLAPIScraper",
    "NHLRosterScraper",
    "MoneyPuckScraper",
    "PuckPediaScraper",
    "NHLInjuriesScraper",
    "YahooFantasyClient",
]
