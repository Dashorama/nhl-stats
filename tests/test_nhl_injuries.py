"""Tests for injury DB methods and scraper."""
import pytest
from datetime import datetime
from src.storage.database import Database


@pytest.fixture
def db(tmp_path):
    return Database(str(tmp_path / "test.db"))


def test_upsert_and_get_unavailable(db):
    records = [
        {"player_id": 1, "player_name": "Player A", "team_abbrev": "EDM",
         "status": "IR", "detail": "upper body"},
        {"player_id": 2, "player_name": "Player B", "team_abbrev": "TOR",
         "status": "HEALTHY", "detail": None},
        {"player_id": 3, "player_name": "Player C", "team_abbrev": "BOS",
         "status": "SUSPENDED", "detail": "match penalty"},
    ]
    db.upsert_injuries(records)
    unavailable = db.get_unavailable_players()
    assert 1 in unavailable    # IR → unavailable
    assert 2 not in unavailable  # HEALTHY → available
    assert 3 in unavailable    # SUSPENDED → unavailable


def test_upsert_overwrites_status(db):
    db.upsert_injuries([{"player_id": 1, "player_name": "Player A",
                         "team_abbrev": "EDM", "status": "IR", "detail": None}])
    db.upsert_injuries([{"player_id": 1, "player_name": "Player A",
                         "team_abbrev": "EDM", "status": "HEALTHY", "detail": None}])
    assert 1 not in db.get_unavailable_players()


def test_empty_db_returns_empty_set(db):
    assert db.get_unavailable_players() == set()


def test_dtd_player_is_available(db):
    db.upsert_injuries([{"player_id": 5, "player_name": "DTD Guy",
                         "team_abbrev": "MTL", "status": "DTD", "detail": None}])
    assert 5 not in db.get_unavailable_players()
