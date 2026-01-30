"""Scraper modules for various NHL data sources."""

from .base import BaseScraper
from .nhl_api import NHLAPIScraper

__all__ = ["BaseScraper", "NHLAPIScraper"]
