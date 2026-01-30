"""Game data models."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class Game(BaseModel):
    """NHL game information."""

    id: int
    season: str
    game_type: Literal["PR", "R", "P", "A"] | int  # Preseason, Regular, Playoff, All-Star
    game_date: datetime
    home_team_abbrev: str
    away_team_abbrev: str
    venue: str | None = None
    attendance: int | None = None

    # Final state
    game_state: str | None = None  # LIVE, FINAL, etc.
    home_score: int | None = None
    away_score: int | None = None
    period: int | None = None
    ended_in_ot: bool = False
    ended_in_shootout: bool = False

    # Officials
    referees: list[str] = []
    linesmen: list[str] = []


class GameStats(BaseModel):
    """Team stats for a single game."""

    game_id: int
    team_abbrev: str
    is_home: bool

    goals: int = 0
    shots: int = 0
    hits: int = 0
    blocks: int = 0
    pim: int = 0
    powerplay_goals: int = 0
    powerplay_opportunities: int = 0
    faceoff_wins: int = 0
    faceoff_total: int = 0
    takeaways: int = 0
    giveaways: int = 0

    @property
    def faceoff_pct(self) -> float | None:
        if self.faceoff_total == 0:
            return None
        return self.faceoff_wins / self.faceoff_total * 100


class Period(BaseModel):
    """Stats for a single period."""

    game_id: int
    period_number: int
    period_type: Literal["REG", "OT", "SO"] = "REG"

    home_goals: int = 0
    away_goals: int = 0
    home_shots: int = 0
    away_shots: int = 0


class Play(BaseModel):
    """Individual play/event in a game."""

    game_id: int
    event_id: int
    period: int
    time_in_period: str  # "MM:SS"
    time_remaining: str | None = None

    event_type: str  # GOAL, SHOT, HIT, BLOCK, PENALTY, FACEOFF, etc.
    description: str | None = None

    team_abbrev: str | None = None
    player_id: int | None = None
    player_name: str | None = None

    # For goals
    assist1_id: int | None = None
    assist2_id: int | None = None
    shot_type: str | None = None
    strength: str | None = None  # EV, PP, SH

    # Location (if available)
    x_coord: float | None = None
    y_coord: float | None = None
