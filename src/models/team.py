"""Team data models."""

from pydantic import BaseModel


class Team(BaseModel):
    """NHL team information."""

    id: int | None = None
    abbreviation: str  # e.g., "TOR", "NYR"
    name: str  # Full name
    location: str | None = None  # City
    nickname: str | None = None  # e.g., "Maple Leafs"
    conference: str | None = None
    division: str | None = None
    venue: str | None = None
    founded_year: int | None = None
    primary_color: str | None = None
    secondary_color: str | None = None


class TeamStandings(BaseModel):
    """Team standings record."""

    team_abbrev: str
    season: str
    conference: str
    division: str

    games_played: int = 0
    wins: int = 0
    losses: int = 0
    ot_losses: int = 0
    points: int = 0
    points_pct: float | None = None
    regulation_wins: int = 0

    goals_for: int = 0
    goals_against: int = 0
    goal_differential: int = 0

    home_wins: int = 0
    home_losses: int = 0
    away_wins: int = 0
    away_losses: int = 0

    last_10_wins: int = 0
    last_10_losses: int = 0
    streak_code: str | None = None  # e.g., "W3", "L2"

    conference_rank: int | None = None
    division_rank: int | None = None
    league_rank: int | None = None


class TeamSeasonStats(BaseModel):
    """Aggregated team statistics for a season."""

    team_abbrev: str
    season: str

    games_played: int = 0
    goals_for: int = 0
    goals_against: int = 0
    shots_for: int = 0
    shots_against: int = 0
    powerplay_pct: float | None = None
    penalty_kill_pct: float | None = None
    faceoff_pct: float | None = None

    # Advanced
    corsi_pct: float | None = None
    fenwick_pct: float | None = None
    expected_goals_for: float | None = None
    expected_goals_against: float | None = None
