"""Player data models."""

from datetime import date
from typing import Literal

from pydantic import BaseModel


class Player(BaseModel):
    """Core player information."""

    id: int
    first_name: str
    last_name: str
    position: Literal["C", "L", "R", "D", "G"]
    shoots_catches: Literal["L", "R"] | None = None
    height_inches: int | None = None
    weight_pounds: int | None = None
    birth_date: date | None = None
    birth_city: str | None = None
    birth_country: str | None = None
    nationality: str | None = None
    current_team_id: str | None = None
    jersey_number: int | None = None

    # Draft info
    draft_year: int | None = None
    draft_round: int | None = None
    draft_pick: int | None = None
    draft_team_id: str | None = None

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def is_goalie(self) -> bool:
        return self.position == "G"


class PlayerStats(BaseModel):
    """Skater statistics for a season or game."""

    player_id: int
    season: str | None = None
    game_id: int | None = None
    team_id: str | None = None

    games_played: int = 0
    goals: int = 0
    assists: int = 0
    points: int = 0
    plus_minus: int = 0
    pim: int = 0  # Penalty minutes
    shots: int = 0
    shot_pct: float | None = None
    hits: int = 0
    blocks: int = 0
    toi_seconds: int = 0  # Time on ice
    powerplay_goals: int = 0
    powerplay_points: int = 0
    shorthanded_goals: int = 0
    game_winning_goals: int = 0
    faceoff_pct: float | None = None

    # Advanced stats (from secondary sources)
    corsi_for: float | None = None
    corsi_against: float | None = None
    corsi_pct: float | None = None
    fenwick_pct: float | None = None
    expected_goals_for: float | None = None
    expected_goals_against: float | None = None

    @property
    def toi_minutes(self) -> float:
        return self.toi_seconds / 60


class GoalieStats(BaseModel):
    """Goaltender statistics."""

    player_id: int
    season: str | None = None
    game_id: int | None = None
    team_id: str | None = None

    games_played: int = 0
    games_started: int = 0
    wins: int = 0
    losses: int = 0
    ot_losses: int = 0
    shutouts: int = 0
    saves: int = 0
    shots_against: int = 0
    goals_against: int = 0
    save_pct: float | None = None
    gaa: float | None = None  # Goals against average
    toi_seconds: int = 0

    # Advanced
    goals_saved_above_expected: float | None = None
    high_danger_save_pct: float | None = None
