"""SQLite database storage for scraped NHL data."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Index,
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


class ContractRecord(Base):
    """Player contract table."""

    __tablename__ = "contracts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(Integer, index=True)
    player_name = Column(String(100))
    team_abbrev = Column(String(3), index=True)
    season = Column(String(8), index=True)

    contract_type = Column(String(20))
    start_season = Column(String(8))
    end_season = Column(String(8))
    total_years = Column(Integer)
    total_value = Column(Integer)
    aav = Column(Integer)
    current_cap_hit = Column(Integer)
    current_salary = Column(Integer)

    expiry_status = Column(String(10))
    has_nmc = Column(Boolean, default=False)
    has_ntc = Column(Boolean, default=False)

    source = Column(String(50))
    raw_data = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow)


class AdvancedStatsRecord(Base):
    """Advanced player statistics table."""

    __tablename__ = "advanced_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(Integer, index=True)
    player_name = Column(String(100))
    team_abbrev = Column(String(3))
    season = Column(String(8), index=True)
    position = Column(String(2))
    situation = Column(String(10), default="all")

    games_played = Column(Integer)
    toi_seconds = Column(Integer)

    # Corsi
    corsi_for = Column(Integer)
    corsi_against = Column(Integer)
    corsi_pct = Column(Float)
    corsi_rel = Column(Float)

    # Fenwick
    fenwick_for = Column(Integer)
    fenwick_against = Column(Integer)
    fenwick_pct = Column(Float)

    # xG
    xg_for = Column(Float)
    xg_against = Column(Float)
    xg_pct = Column(Float)
    goals_above_expected = Column(Float)

    # Zone starts
    oz_start_pct = Column(Float)

    # High danger
    hd_chances_for = Column(Integer)
    hd_chances_against = Column(Integer)

    source = Column(String(50))
    raw_data = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (Index("ix_advanced_player_season", "player_id", "season"),)


class RosterRecord(Base):
    """Team roster assignments."""

    __tablename__ = "rosters"

    id = Column(Integer, primary_key=True, autoincrement=True)
    team_abbrev = Column(String(3), index=True)
    player_id = Column(Integer, index=True)
    player_name = Column(String(100))
    season = Column(String(8), index=True)

    jersey_number = Column(Integer)
    position = Column(String(2))
    roster_status = Column(String(20), default="active")

    raw_data = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (Index("ix_roster_team_season", "team_abbrev", "season"),)


class DraftRecord(Base):
    """Draft picks/rankings table."""

    __tablename__ = "draft_picks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    draft_year = Column(Integer, index=True)
    rank = Column(Integer)
    first_name = Column(String(100))
    last_name = Column(String(100))
    position = Column(String(2))
    shoots_catches = Column(String(1))
    height_inches = Column(Integer)
    weight_pounds = Column(Integer)
    amateur_club = Column(String(100))
    amateur_league = Column(String(50))
    birth_date = Column(String(10))
    birth_country = Column(String(50))
    midterm_rank = Column(Integer)
    final_rank = Column(Integer)
    raw_data = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (Index("ix_draft_year_rank", "draft_year", "rank"),)


class BoxscoreRecord(Base):
    """Per-player per-game boxscore stats."""

    __tablename__ = "boxscores"

    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, index=True)
    player_id = Column(Integer, index=True)
    player_name = Column(String(100))
    team_abbrev = Column(String(3))
    position = Column(String(2))
    is_home = Column(Boolean)

    goals = Column(Integer, default=0)
    assists = Column(Integer, default=0)
    points = Column(Integer, default=0)
    plus_minus = Column(Integer, default=0)
    pim = Column(Integer, default=0)
    hits = Column(Integer, default=0)
    shots = Column(Integer, default=0)
    blocked_shots = Column(Integer, default=0)
    faceoff_pct = Column(Float)
    toi = Column(String(10))
    shifts = Column(Integer, default=0)
    giveaways = Column(Integer, default=0)
    takeaways = Column(Integer, default=0)
    power_play_goals = Column(Integer, default=0)

    # Goalie fields (null for skaters)
    saves = Column(Integer)
    shots_against = Column(Integer)
    goals_against = Column(Integer)

    raw_data = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_boxscore_game_player", "game_id", "player_id"),
    )


class PlayByPlayRecord(Base):
    """Individual game events (shots, hits, faceoffs, etc.)."""

    __tablename__ = "play_by_play"

    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, index=True)
    event_id = Column(Integer)
    event_type = Column(String(30), index=True)
    period = Column(Integer)
    period_type = Column(String(10))
    time_in_period = Column(String(10))
    time_remaining = Column(String(10))

    x_coord = Column(Integer)
    y_coord = Column(Integer)
    zone_code = Column(String(2))

    # Flexible player references (different events have different players)
    player1_id = Column(Integer, index=True)  # shooter/hitter/winner
    player2_id = Column(Integer)  # goalie/hittee/loser/assist1
    player3_id = Column(Integer)  # assist2

    team_id = Column(Integer)
    shot_type = Column(String(20))
    description = Column(String(50))

    raw_data = Column(Text)

    __table_args__ = (
        Index("ix_pbp_game_event", "game_id", "event_id"),
    )


class GameLogRecord(Base):
    """Per-player per-game stats from NHL API."""
    __tablename__ = "game_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(Integer, index=True)
    game_id = Column(Integer, index=True)
    season = Column(String(8))
    team_abbrev = Column(String(3))
    opponent_abbrev = Column(String(3))
    game_date = Column(String(10))
    home_road = Column(String(1))

    goals = Column(Integer, default=0)
    assists = Column(Integer, default=0)
    points = Column(Integer, default=0)
    plus_minus = Column(Integer, default=0)
    pim = Column(Integer, default=0)
    shots = Column(Integer, default=0)
    shifts = Column(Integer, default=0)
    toi = Column(String(10))
    power_play_goals = Column(Integer, default=0)
    power_play_points = Column(Integer, default=0)
    shorthanded_goals = Column(Integer, default=0)
    game_winning_goals = Column(Integer, default=0)
    ot_goals = Column(Integer, default=0)

    raw_data = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_gamelog_player_game", "player_id", "game_id"),
    )


class ShotRecord(Base):
    """Individual shot events from MoneyPuck shot data."""
    __tablename__ = "shots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    season = Column(String(8), index=True)
    game_id = Column(Integer, index=True)

    team = Column(String(3))
    shooter_id = Column(Integer, index=True)
    shooter_name = Column(String(100))
    goalie_id = Column(Integer)
    goalie_name = Column(String(100))

    event = Column(String(10))  # SHOT, GOAL, MISS
    period = Column(Integer)
    time = Column(Integer)  # seconds into period

    x_coord = Column(Float)
    y_coord = Column(Float)
    shot_type = Column(String(20))

    x_goal = Column(Float)  # expected goal probability
    goal = Column(Integer)  # 0 or 1

    shot_angle = Column(Float)
    shot_distance = Column(Float)
    shot_rebound = Column(Integer)
    shot_rush = Column(Integer)

    situation = Column(String(10))  # 5v5, 5v4, etc.
    is_home = Column(Boolean)

    __table_args__ = (
        Index("ix_shot_game_shooter", "game_id", "shooter_id"),
    )


class InjuryRecord(Base):
    """Player injury/availability snapshot."""

    __tablename__ = "injuries"

    player_id = Column(Integer, primary_key=True)
    player_name = Column(String(100))
    team_abbrev = Column(String(3))
    status = Column(String(20))   # 'IR', 'LTIR', 'DTD', 'SUSPENDED', 'HEALTHY'
    detail = Column(String(200))
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

    def upsert_injuries(self, records: list[dict]) -> int:
        """Insert or update player availability records."""
        with self.get_session() as session:
            count = 0
            for r in records:
                existing = session.get(InjuryRecord, r["player_id"])
                if existing:
                    existing.player_name = r["player_name"]
                    existing.team_abbrev = r["team_abbrev"]
                    existing.status = r["status"]
                    existing.detail = r.get("detail")
                    existing.updated_at = datetime.utcnow()
                else:
                    session.add(InjuryRecord(
                        player_id=r["player_id"],
                        player_name=r["player_name"],
                        team_abbrev=r["team_abbrev"],
                        status=r["status"],
                        detail=r.get("detail"),
                        updated_at=datetime.utcnow(),
                    ))
                count += 1
            session.commit()
        return count

    def get_unavailable_players(self) -> set[int]:
        """Return player IDs that are IR, LTIR, or SUSPENDED."""
        with self.get_session() as session:
            rows = session.query(InjuryRecord).filter(
                InjuryRecord.status.in_(["IR", "LTIR", "SUSPENDED"])
            ).all()
            return {r.player_id for r in rows}

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
                "contracts": session.query(ContractRecord).count(),
                "advanced_stats": session.query(AdvancedStatsRecord).count(),
                "rosters": session.query(RosterRecord).count(),
                "draft_picks": session.query(DraftRecord).count(),
                "boxscores": session.query(BoxscoreRecord).count(),
                "play_by_play": session.query(PlayByPlayRecord).count(),
                "game_logs": session.query(GameLogRecord).count(),
                "shots": session.query(ShotRecord).count(),
            }

    def upsert_contracts(self, contracts: list[dict[str, Any]]) -> int:
        """Insert or update contract records."""
        with self.get_session() as session:
            count = 0
            for c in contracts:
                player_name = c.get("player_name")
                team_abbrev = c.get("team_abbrev")
                if not player_name:
                    continue

                # Find existing by player name and team
                existing = (
                    session.query(ContractRecord)
                    .filter_by(player_name=player_name, team_abbrev=team_abbrev)
                    .first()
                )

                if existing:
                    existing.current_cap_hit = c.get("current_cap_hit", existing.current_cap_hit)
                    existing.current_salary = c.get("current_salary", existing.current_salary)
                    existing.aav = c.get("aav", existing.aav)
                    existing.total_years = c.get("total_years", existing.total_years)
                    existing.expiry_status = c.get("expiry_status", existing.expiry_status)
                    existing.has_nmc = c.get("has_nmc", existing.has_nmc)
                    existing.has_ntc = c.get("has_ntc", existing.has_ntc)
                    existing.raw_data = json.dumps(c)
                    existing.updated_at = datetime.utcnow()
                else:
                    session.add(
                        ContractRecord(
                            player_id=c.get("player_id"),
                            player_name=player_name,
                            team_abbrev=team_abbrev,
                            season=c.get("season"),
                            contract_type=c.get("contract_type"),
                            start_season=c.get("start_season"),
                            end_season=c.get("end_season"),
                            total_years=c.get("total_years"),
                            total_value=c.get("total_value"),
                            aav=c.get("aav"),
                            current_cap_hit=c.get("current_cap_hit"),
                            current_salary=c.get("current_salary"),
                            expiry_status=c.get("expiry_status"),
                            has_nmc=c.get("has_nmc", False),
                            has_ntc=c.get("has_ntc", False),
                            source=c.get("source"),
                            raw_data=json.dumps(c),
                        )
                    )
                count += 1

            session.commit()
            self.logger.info("upserted_contracts", count=count)
            return count

    def upsert_advanced_stats(self, stats: list[dict[str, Any]]) -> int:
        """Insert or update advanced statistics records."""
        with self.get_session() as session:
            count = 0
            for s in stats:
                player_id = s.get("player_id")
                season = s.get("season")
                situation = s.get("situation", "all")
                if not player_id:
                    continue

                # Find existing by player, season, and situation
                existing = (
                    session.query(AdvancedStatsRecord)
                    .filter_by(player_id=player_id, season=season, situation=situation)
                    .first()
                )

                if existing:
                    # Update all stats fields
                    existing.player_name = s.get("player_name", existing.player_name)
                    existing.team_abbrev = s.get("team_abbrev", existing.team_abbrev)
                    existing.position = s.get("position", existing.position)
                    existing.games_played = s.get("games_played", existing.games_played)
                    existing.toi_seconds = s.get("toi_seconds", existing.toi_seconds)
                    existing.corsi_for = s.get("corsi_for", existing.corsi_for)
                    existing.corsi_against = s.get("corsi_against", existing.corsi_against)
                    existing.corsi_pct = s.get("corsi_pct", existing.corsi_pct)
                    existing.corsi_rel = s.get("corsi_rel", existing.corsi_rel)
                    existing.fenwick_for = s.get("fenwick_for", existing.fenwick_for)
                    existing.fenwick_against = s.get("fenwick_against", existing.fenwick_against)
                    existing.fenwick_pct = s.get("fenwick_pct", existing.fenwick_pct)
                    existing.xg_for = s.get("xg_for", existing.xg_for)
                    existing.xg_against = s.get("xg_against", existing.xg_against)
                    existing.xg_pct = s.get("xg_pct", existing.xg_pct)
                    existing.goals_above_expected = s.get("goals_above_expected", existing.goals_above_expected)
                    existing.oz_start_pct = s.get("offensive_zone_start_pct", existing.oz_start_pct)
                    existing.hd_chances_for = s.get("high_danger_chances_for", existing.hd_chances_for)
                    existing.hd_chances_against = s.get("high_danger_chances_against", existing.hd_chances_against)
                    existing.raw_data = json.dumps(s)
                    existing.updated_at = datetime.utcnow()
                else:
                    session.add(
                        AdvancedStatsRecord(
                            player_id=player_id,
                            player_name=s.get("player_name"),
                            team_abbrev=s.get("team_abbrev"),
                            season=season,
                            position=s.get("position"),
                            situation=situation,
                            games_played=s.get("games_played"),
                            toi_seconds=s.get("toi_seconds"),
                            corsi_for=s.get("corsi_for"),
                            corsi_against=s.get("corsi_against"),
                            corsi_pct=s.get("corsi_pct"),
                            corsi_rel=s.get("corsi_rel"),
                            fenwick_for=s.get("fenwick_for"),
                            fenwick_against=s.get("fenwick_against"),
                            fenwick_pct=s.get("fenwick_pct"),
                            xg_for=s.get("xg_for"),
                            xg_against=s.get("xg_against"),
                            xg_pct=s.get("xg_pct"),
                            goals_above_expected=s.get("goals_above_expected"),
                            oz_start_pct=s.get("offensive_zone_start_pct"),
                            hd_chances_for=s.get("high_danger_chances_for"),
                            hd_chances_against=s.get("high_danger_chances_against"),
                            source=s.get("source"),
                            raw_data=json.dumps(s),
                        )
                    )
                count += 1

            session.commit()
            self.logger.info("upserted_advanced_stats", count=count)
            return count

    def upsert_draft_picks(self, picks: list[dict[str, Any]]) -> int:
        """Insert or update draft pick records."""
        with self.get_session() as session:
            count = 0
            for p in picks:
                year = p.get("draft_year")
                rank = p.get("rank")
                if not year or not rank:
                    continue

                existing = (
                    session.query(DraftRecord)
                    .filter_by(draft_year=year, rank=rank)
                    .first()
                )

                if existing:
                    existing.first_name = p.get("first_name", existing.first_name)
                    existing.last_name = p.get("last_name", existing.last_name)
                    existing.position = p.get("position", existing.position)
                    existing.raw_data = json.dumps(p)
                    existing.updated_at = datetime.utcnow()
                else:
                    session.add(DraftRecord(
                        draft_year=year,
                        rank=rank,
                        first_name=p.get("first_name"),
                        last_name=p.get("last_name"),
                        position=p.get("position"),
                        shoots_catches=p.get("shoots_catches"),
                        height_inches=p.get("height_inches"),
                        weight_pounds=p.get("weight_pounds"),
                        amateur_club=p.get("amateur_club"),
                        amateur_league=p.get("amateur_league"),
                        birth_date=p.get("birth_date"),
                        birth_country=p.get("birth_country"),
                        midterm_rank=p.get("midterm_rank"),
                        final_rank=p.get("final_rank"),
                        raw_data=json.dumps(p),
                    ))
                count += 1

            session.commit()
            self.logger.info("upserted_draft_picks", count=count)
            return count

    def upsert_boxscores(self, game_id: int, players: list[dict[str, Any]]) -> int:
        """Insert or update boxscore records for a game."""
        with self.get_session() as session:
            count = 0
            for p in players:
                player_id = p.get("player_id")
                if not player_id:
                    continue

                existing = (
                    session.query(BoxscoreRecord)
                    .filter_by(game_id=game_id, player_id=player_id)
                    .first()
                )

                if existing:
                    for key in ["goals", "assists", "points", "plus_minus", "pim",
                               "hits", "shots", "blocked_shots", "toi", "shifts",
                               "giveaways", "takeaways", "saves", "shots_against", "goals_against"]:
                        if p.get(key) is not None:
                            setattr(existing, key, p[key])
                    existing.raw_data = json.dumps(p)
                    existing.updated_at = datetime.utcnow()
                else:
                    session.add(BoxscoreRecord(
                        game_id=game_id,
                        player_id=player_id,
                        player_name=p.get("player_name"),
                        team_abbrev=p.get("team_abbrev"),
                        position=p.get("position"),
                        is_home=p.get("is_home"),
                        goals=p.get("goals", 0),
                        assists=p.get("assists", 0),
                        points=p.get("points", 0),
                        plus_minus=p.get("plus_minus", 0),
                        pim=p.get("pim", 0),
                        hits=p.get("hits", 0),
                        shots=p.get("shots", 0),
                        blocked_shots=p.get("blocked_shots", 0),
                        faceoff_pct=p.get("faceoff_pct"),
                        toi=p.get("toi"),
                        shifts=p.get("shifts", 0),
                        giveaways=p.get("giveaways", 0),
                        takeaways=p.get("takeaways", 0),
                        power_play_goals=p.get("power_play_goals", 0),
                        saves=p.get("saves"),
                        shots_against=p.get("shots_against"),
                        goals_against=p.get("goals_against"),
                        raw_data=json.dumps(p),
                    ))
                count += 1

            session.commit()
            return count

    def insert_play_by_play(self, game_id: int, events: list[dict[str, Any]]) -> int:
        """Insert play-by-play events for a game. Replaces existing events."""
        with self.get_session() as session:
            # Delete existing events for this game (full replace)
            session.query(PlayByPlayRecord).filter_by(game_id=game_id).delete()

            count = 0
            for e in events:
                session.add(PlayByPlayRecord(
                    game_id=game_id,
                    event_id=e.get("event_id"),
                    event_type=e.get("event_type"),
                    period=e.get("period"),
                    period_type=e.get("period_type"),
                    time_in_period=e.get("time_in_period"),
                    time_remaining=e.get("time_remaining"),
                    x_coord=e.get("x_coord"),
                    y_coord=e.get("y_coord"),
                    zone_code=e.get("zone_code"),
                    player1_id=e.get("player1_id"),
                    player2_id=e.get("player2_id"),
                    player3_id=e.get("player3_id"),
                    team_id=e.get("team_id"),
                    shot_type=e.get("shot_type"),
                    description=e.get("description"),
                    raw_data=json.dumps(e),
                ))
                count += 1

            session.commit()
            self.logger.info("inserted_play_by_play", game_id=game_id, count=count)
            return count

    def upsert_game_logs(self, player_id: int, season: str, logs: list[dict[str, Any]]) -> int:
        """Insert or update player game log records."""
        with self.get_session() as session:
            count = 0
            for log in logs:
                game_id = log.get("game_id")
                if not game_id:
                    continue

                existing = (
                    session.query(GameLogRecord)
                    .filter_by(player_id=player_id, game_id=game_id)
                    .first()
                )

                if existing:
                    for key in ["goals", "assists", "points", "plus_minus", "pim",
                               "shots", "shifts", "toi", "power_play_goals",
                               "power_play_points", "shorthanded_goals",
                               "game_winning_goals", "ot_goals"]:
                        if log.get(key) is not None:
                            setattr(existing, key, log[key])
                    existing.raw_data = json.dumps(log)
                    existing.updated_at = datetime.utcnow()
                else:
                    session.add(GameLogRecord(
                        player_id=player_id,
                        game_id=game_id,
                        season=season,
                        team_abbrev=log.get("team_abbrev"),
                        opponent_abbrev=log.get("opponent_abbrev"),
                        game_date=log.get("game_date"),
                        home_road=log.get("home_road"),
                        goals=log.get("goals", 0),
                        assists=log.get("assists", 0),
                        points=log.get("points", 0),
                        plus_minus=log.get("plus_minus", 0),
                        pim=log.get("pim", 0),
                        shots=log.get("shots", 0),
                        shifts=log.get("shifts", 0),
                        toi=log.get("toi"),
                        power_play_goals=log.get("power_play_goals", 0),
                        power_play_points=log.get("power_play_points", 0),
                        shorthanded_goals=log.get("shorthanded_goals", 0),
                        game_winning_goals=log.get("game_winning_goals", 0),
                        ot_goals=log.get("ot_goals", 0),
                        raw_data=json.dumps(log),
                    ))
                count += 1

            session.commit()
            return count

    def insert_shots(self, shots: list[dict[str, Any]]) -> int:
        """Insert shot records. Bulk insert for efficiency."""
        with self.get_session() as session:
            count = 0
            for s in shots:
                session.add(ShotRecord(
                    season=s.get("season"),
                    game_id=s.get("game_id"),
                    team=s.get("team"),
                    shooter_id=s.get("shooter_id"),
                    shooter_name=s.get("shooter_name"),
                    goalie_id=s.get("goalie_id"),
                    goalie_name=s.get("goalie_name"),
                    event=s.get("event"),
                    period=s.get("period"),
                    time=s.get("time"),
                    x_coord=s.get("x_coord"),
                    y_coord=s.get("y_coord"),
                    shot_type=s.get("shot_type"),
                    x_goal=s.get("x_goal"),
                    goal=s.get("goal"),
                    shot_angle=s.get("shot_angle"),
                    shot_distance=s.get("shot_distance"),
                    shot_rebound=s.get("shot_rebound"),
                    shot_rush=s.get("shot_rush"),
                    situation=s.get("situation"),
                    is_home=s.get("is_home"),
                ))
                count += 1

                # Batch commit every 10000
                if count % 10000 == 0:
                    session.commit()

            session.commit()
            self.logger.info("inserted_shots", count=count)
            return count

    def upsert_rosters(self, rosters: list[dict[str, Any]]) -> int:
        """Insert or update roster records from team roster data."""
        with self.get_session() as session:
            count = 0

            for roster in rosters:
                team_abbrev = roster.get("team_abbrev")
                season = roster.get("season")

                # Process all player groups
                all_players = (
                    roster.get("forwards", [])
                    + roster.get("defensemen", [])
                    + roster.get("goalies", [])
                )

                for p in all_players:
                    player_id = p.get("player_id")
                    if not player_id:
                        continue

                    # Find existing by player, team, and season
                    existing = (
                        session.query(RosterRecord)
                        .filter_by(player_id=player_id, team_abbrev=team_abbrev, season=season)
                        .first()
                    )

                    player_name = f"{p.get('first_name', '')} {p.get('last_name', '')}".strip()

                    if existing:
                        existing.player_name = player_name
                        existing.jersey_number = p.get("jersey_number", existing.jersey_number)
                        existing.position = p.get("position", existing.position)
                        existing.roster_status = p.get("roster_status", existing.roster_status)
                        existing.raw_data = json.dumps(p)
                        existing.updated_at = datetime.utcnow()
                    else:
                        session.add(
                            RosterRecord(
                                team_abbrev=team_abbrev,
                                player_id=player_id,
                                player_name=player_name,
                                season=season,
                                jersey_number=p.get("jersey_number"),
                                position=p.get("position"),
                                roster_status=p.get("roster_status", "active"),
                                raw_data=json.dumps(p),
                            )
                        )
                    count += 1

            session.commit()
            self.logger.info("upserted_rosters", count=count)
            return count
