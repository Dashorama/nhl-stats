"""Advanced analytics models."""

from pydantic import BaseModel


class AdvancedSkaterStats(BaseModel):
    """Advanced analytics for skaters."""

    player_id: int
    player_name: str
    team_abbrev: str
    season: str
    position: str | None = None
    situation: str = "all"  # "all", "5on5", "5on4", "4on5", etc.

    games_played: int = 0
    toi_seconds: int = 0

    # Corsi (all shot attempts)
    corsi_for: int = 0
    corsi_against: int = 0
    corsi_pct: float | None = None
    corsi_for_per_60: float | None = None
    corsi_against_per_60: float | None = None
    corsi_rel: float | None = None  # Relative to team

    # Fenwick (unblocked shot attempts)
    fenwick_for: int = 0
    fenwick_against: int = 0
    fenwick_pct: float | None = None
    fenwick_rel: float | None = None

    # Expected Goals (xG)
    xg_for: float = 0.0
    xg_against: float = 0.0
    xg_pct: float | None = None
    xg_for_per_60: float | None = None
    xg_against_per_60: float | None = None
    goals_above_expected: float | None = None

    # Scoring Chances
    scoring_chances_for: int = 0
    scoring_chances_against: int = 0
    high_danger_chances_for: int = 0
    high_danger_chances_against: int = 0
    high_danger_goals_for: int = 0
    high_danger_goals_against: int = 0

    # Zone Starts
    offensive_zone_starts: int = 0
    defensive_zone_starts: int = 0
    neutral_zone_starts: int = 0
    offensive_zone_start_pct: float | None = None

    # On-Ice vs Off-Ice
    on_ice_sh_pct: float | None = None
    on_ice_sv_pct: float | None = None
    pdo: float | None = None  # SH% + SV% (luck indicator, regresses to 100)

    # Individual
    individual_xg: float = 0.0
    shots: int = 0
    individual_corsi_for: int = 0
    goals: int = 0
    primary_assists: int = 0
    secondary_assists: int = 0

    source: str = "moneypuck"

    @property
    def toi_minutes(self) -> float:
        return self.toi_seconds / 60 if self.toi_seconds else 0

    @property
    def corsi_diff(self) -> int:
        """Corsi differential (for - against)."""
        return self.corsi_for - self.corsi_against

    @property
    def xg_diff(self) -> float:
        """Expected goals differential."""
        return self.xg_for - self.xg_against


class AdvancedGoalieStats(BaseModel):
    """Advanced analytics for goalies."""

    player_id: int
    player_name: str
    team_abbrev: str
    season: str
    situation: str = "all"

    games_played: int = 0
    toi_seconds: int = 0

    # Basic
    shots_against: int = 0
    goals_against: int = 0
    saves: int = 0
    save_pct: float | None = None

    # Expected Goals
    xg_against: float = 0.0
    goals_saved_above_expected: float | None = None
    gsax_per_60: float | None = None

    # By Danger Level
    low_danger_shots: int = 0
    low_danger_goals: int = 0
    low_danger_save_pct: float | None = None

    medium_danger_shots: int = 0
    medium_danger_goals: int = 0
    medium_danger_save_pct: float | None = None

    high_danger_shots: int = 0
    high_danger_goals: int = 0
    high_danger_save_pct: float | None = None

    # Rebounds
    rebounds_given: int = 0
    rebound_goals_against: int = 0

    # Freeze/play
    freeze_pct: float | None = None

    source: str = "moneypuck"

    @property
    def toi_minutes(self) -> float:
        return self.toi_seconds / 60 if self.toi_seconds else 0

    @property
    def goals_against_average(self) -> float | None:
        """Calculate GAA (goals against per 60 minutes)."""
        if self.toi_seconds and self.toi_seconds > 0:
            return (self.goals_against / self.toi_seconds) * 3600
        return None
