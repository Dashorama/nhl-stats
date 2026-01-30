"""SQLite database storage for scraped NHL data."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import Session, declarative_base, sessionmaker
import structlog

logger = structlog.get_logger()
Base = declarative_base()


class PlayerRecord(Base):
    """Player table."""

    __tablename__ = "players"

    id = Column(Integer, primary_key=True)
    first_name = Column(String(100))
    last_name = Column(String(100))
    position = Column(String(2))
    team_abbrev = Column(String(3))
    birth_date = Column(String(10))
    birth_country = Column(String(50))
    draft_year = Column(Integer)
    draft_round = Column(Integer)
    draft_pick = Column(Integer)
    raw_data = Column(Text)  # JSON blob for extra data
    updated_at = Column(DateTime, default=datetime.utcnow)


class PlayerStatsRecord(Base):
    """Player season stats table."""

    __tablename__ = "player_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(Integer, index=True)
    season = Column(String(8), index=True)
    team_abbrev = Column(String(3))
    games_played = Column(Integer)
    goals = Column(Integer)
    assists = Column(Integer)
    points = Column(Integer)
    plus_minus = Column(Integer)
    pim = Column(Integer)
    shots = Column(Integer)
    toi_seconds = Column(Integer)
    source = Column(String(50))  # Which scraper provided this
    raw_data = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow)


class TeamRecord(Base):
    """Team table."""

    __tablename__ = "teams"

    abbrev = Column(String(3), primary_key=True)
    name = Column(String(100))
    conference = Column(String(20))
    division = Column(String(20))
    raw_data = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow)


class GameRecord(Base):
    """Game table."""

    __tablename__ = "games"

    id = Column(Integer, primary_key=True)
    season = Column(String(8), index=True)
    game_date = Column(String(10), index=True)
    game_type = Column(String(2))
    home_team = Column(String(3))
    away_team = Column(String(3))
    home_score = Column(Integer)
    away_score = Column(Integer)
    game_state = Column(String(20))
    raw_data = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow)


class Database:
    """SQLite database wrapper for NHL data."""

    def __init__(self, db_path: str | Path = "data/nhl.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.engine = create_engine(f"sqlite:///{self.db_path}", echo=False)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.logger = logger.bind(component="database")

    def get_session(self) -> Session:
        """Get a new database session."""
        return self.SessionLocal()

    def upsert_players(self, players: list[dict[str, Any]]) -> int:
        """Insert or update player records."""
        with self.get_session() as session:
            count = 0
            for p in players:
                player_id = p.get("id")
                if not player_id:
                    continue

                existing = session.get(PlayerRecord, player_id)
                if existing:
                    existing.first_name = p.get("first_name", existing.first_name)
                    existing.last_name = p.get("last_name", existing.last_name)
                    existing.position = p.get("position", existing.position)
                    existing.team_abbrev = p.get("team", existing.team_abbrev)
                    existing.raw_data = json.dumps(p)
                    existing.updated_at = datetime.utcnow()
                else:
                    session.add(PlayerRecord(
                        id=player_id,
                        first_name=p.get("first_name"),
                        last_name=p.get("last_name"),
                        position=p.get("position"),
                        team_abbrev=p.get("team"),
                        birth_date=p.get("birth_date"),
                        birth_country=p.get("birth_country"),
                        draft_year=p.get("draft_year"),
                        draft_round=p.get("draft_round"),
                        draft_pick=p.get("draft_pick"),
                        raw_data=json.dumps(p),
                    ))
                count += 1

            session.commit()
            self.logger.info("upserted_players", count=count)
            return count

    def upsert_teams(self, teams: list[dict[str, Any]]) -> int:
        """Insert or update team records."""
        with self.get_session() as session:
            count = 0
            for t in teams:
                abbrev = t.get("abbreviation")
                if not abbrev:
                    continue

                existing = session.get(TeamRecord, abbrev)
                if existing:
                    existing.name = t.get("name", existing.name)
                    existing.conference = t.get("conference", existing.conference)
                    existing.division = t.get("division", existing.division)
                    existing.raw_data = json.dumps(t)
                    existing.updated_at = datetime.utcnow()
                else:
                    session.add(TeamRecord(
                        abbrev=abbrev,
                        name=t.get("name"),
                        conference=t.get("conference"),
                        division=t.get("division"),
                        raw_data=json.dumps(t),
                    ))
                count += 1

            session.commit()
            self.logger.info("upserted_teams", count=count)
            return count

    def upsert_games(self, games: list[dict[str, Any]]) -> int:
        """Insert or update game records."""
        with self.get_session() as session:
            count = 0
            for g in games:
                game_id = g.get("id")
                if not game_id:
                    continue

                existing = session.get(GameRecord, game_id)
                if existing:
                    existing.home_score = g.get("home_score", existing.home_score)
                    existing.away_score = g.get("away_score", existing.away_score)
                    existing.game_state = g.get("game_state", existing.game_state)
                    existing.raw_data = json.dumps(g)
                    existing.updated_at = datetime.utcnow()
                else:
                    session.add(GameRecord(
                        id=game_id,
                        season=g.get("season"),
                        game_date=g.get("date"),
                        game_type=str(g.get("game_type")),
                        home_team=g.get("home_team"),
                        away_team=g.get("away_team"),
                        home_score=g.get("home_score"),
                        away_score=g.get("away_score"),
                        game_state=g.get("game_state"),
                        raw_data=json.dumps(g),
                    ))
                count += 1

            session.commit()
            self.logger.info("upserted_games", count=count)
            return count

    def get_stats(self) -> dict[str, int]:
        """Get counts of all records."""
        with self.get_session() as session:
            return {
                "players": session.query(PlayerRecord).count(),
                "teams": session.query(TeamRecord).count(),
                "games": session.query(GameRecord).count(),
            }
