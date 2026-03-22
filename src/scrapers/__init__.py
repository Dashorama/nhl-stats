"""Scraper modules for various NHL data sources."""

from .base import BaseScraper
from .nhl_api import NHLAPIScraper
from .nhl_roster import NHLRosterScraper
from .moneypuck import MoneyPuckScraper
from .puckpedia import PuckPediaScraper
from .nhl_injuries import NHLInjuriesScraper

__all__ = [
    "BaseScraper",
    "NHLAPIScraper",
    "NHLRosterScraper",
    "MoneyPuckScraper",
    "PuckPediaScraper",
    "NHLInjuriesScraper",
]
