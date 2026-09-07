"""Pydantic data models for NHL entities."""

from .advanced_stats import AdvancedGoalieStats, AdvancedSkaterStats
from .contract import ContractClause, ContractYear, PlayerContract
from .game import Game, GameStats
from .player import GoalieStats, Player, PlayerStats
from .roster import RosterPlayer, TeamRoster
from .team import Team, TeamSeasonStats, TeamStandings

__all__ = [
    # Player
    "Player",
    "PlayerStats",
    "GoalieStats",
    # Team
    "Team",
    "TeamStandings",
    "TeamSeasonStats",
    # Game
    "Game",
    "GameStats",
    # Contract
    "PlayerContract",
    "ContractClause",
    "ContractYear",
    # Roster
    "RosterPlayer",
    "TeamRoster",
    # Advanced
    "AdvancedSkaterStats",
    "AdvancedGoalieStats",
]
