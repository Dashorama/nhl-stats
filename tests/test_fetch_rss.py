"""Tests for RSS headline fetcher."""
import pytest
from scripts.fetch_rss import filter_headlines


def test_filter_by_name():
    headlines = [
        {"title": "Oilers recall player", "url": "https://tsn.ca/1", "source": "TSN"},
        {"title": "Maple Leafs sign defenseman", "url": "https://tsn.ca/2", "source": "TSN"},
    ]
    result = filter_headlines(headlines, subject_name="Oilers")
    assert len(result) == 1
    assert result[0]["title"] == "Oilers recall player"


def test_filter_case_insensitive():
    headlines = [{"title": "DRAISAITL scores hat trick", "url": "https://x.com", "source": "NHL"}]
    result = filter_headlines(headlines, subject_name="Draisaitl")
    assert len(result) == 1


def test_filter_returns_max_two():
    headlines = [
        {"title": "Oilers win 1", "url": "a", "source": "TSN"},
        {"title": "Oilers win 2", "url": "b", "source": "TSN"},
        {"title": "Oilers win 3", "url": "c", "source": "TSN"},
    ]
    result = filter_headlines(headlines, subject_name="Oilers")
    assert len(result) == 2


def test_filter_no_match_returns_empty():
    headlines = [{"title": "NHL trade deadline recap", "url": "x", "source": "TSN"}]
    result = filter_headlines(headlines, subject_name="Canucks")
    assert result == []
