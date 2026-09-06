"""Tests for data models."""

from src.models import (
    AdvancedGoalieStats,
    AdvancedSkaterStats,
    ContractClause,
    PlayerContract,
    RosterPlayer,
    TeamRoster,
)


class TestPlayerContract:
    """Tests for PlayerContract model."""

    def test_basic_contract(self):
        """Test creating a basic contract."""
        contract = PlayerContract(
            player_id=8478402,
            player_name="Connor McDavid",
            team_abbrev="EDM",
            start_season="20262027",
            end_season="20332034",
            total_years=8,
            total_value=100_000_000,
            aav=12_500_000,
            current_cap_hit=12_500_000,
            current_salary=12_500_000,
            expiry_status="UFA",
        )

        assert contract.player_name == "Connor McDavid"
        assert contract.aav == 12_500_000
        assert contract.expiry_status == "UFA"

    def test_contract_with_clauses(self):
        """Test contract with NMC/NTC clauses."""
        contract = PlayerContract(
            player_id=12345,
            player_name="Test Player",
            team_abbrev="TOR",
            start_season="20242025",
            end_season="20272028",
            total_years=4,
            total_value=20_000_000,
            aav=5_000_000,
            current_cap_hit=5_000_000,
            current_salary=5_000_000,
            clauses=[
                ContractClause(clause_type="NMC"),
                ContractClause(clause_type="M-NTC", teams_protected=10),
            ],
        )

        assert contract.has_trade_protection
        assert len(contract.clauses) == 2


class TestRosterPlayer:
    """Tests for RosterPlayer model."""

    def test_forward(self):
        """Test creating a forward."""
        player = RosterPlayer(
            player_id=8478402,
            first_name="Connor",
            last_name="McDavid",
            jersey_number=97,
            position="C",
            shoots_catches="L",
            height_inches=73,
            weight_pounds=193,
        )

        assert player.full_name == "Connor McDavid"
        assert player.is_forward
        assert not player.is_defenseman
        assert not player.is_goalie

    def test_defenseman(self):
        """Test creating a defenseman."""
        player = RosterPlayer(
            player_id=8479982,
            first_name="Cale",
            last_name="Makar",
            jersey_number=8,
            position="D",
            shoots_catches="R",
        )

        assert player.is_defenseman
        assert not player.is_forward

    def test_goalie(self):
        """Test creating a goalie."""
        player = RosterPlayer(
            player_id=8479394,
            first_name="Connor",
            last_name="Hellebuyck",
            jersey_number=37,
            position="G",
            shoots_catches="L",
        )

        assert player.is_goalie


class TestTeamRoster:
    """Tests for TeamRoster model."""

    def test_roster_totals(self):
        """Test roster player counts."""
        roster = TeamRoster(
            team_abbrev="TOR",
            team_name="Toronto Maple Leafs",
            season="20242025",
            as_of_date="2025-01-01",
            forwards=[
                RosterPlayer(player_id=1, first_name="A", last_name="B", position="C"),
                RosterPlayer(player_id=2, first_name="C", last_name="D", position="L"),
            ],
            defensemen=[
                RosterPlayer(player_id=3, first_name="E", last_name="F", position="D"),
            ],
            goalies=[
                RosterPlayer(player_id=4, first_name="G", last_name="H", position="G"),
            ],
        )

        assert roster.total_players == 4
        assert len(roster.all_players) == 4

    def test_find_player_by_id(self):
        """Test finding player by ID."""
        roster = TeamRoster(
            team_abbrev="TOR",
            team_name="Toronto Maple Leafs",
            season="20242025",
            as_of_date="2025-01-01",
            forwards=[
                RosterPlayer(player_id=123, first_name="Test", last_name="Player", position="C"),
            ],
        )

        player = roster.get_player_by_id(123)
        assert player is not None
        assert player.first_name == "Test"

        assert roster.get_player_by_id(999) is None


class TestAdvancedSkaterStats:
    """Tests for AdvancedSkaterStats model."""

    def test_basic_stats(self):
        """Test creating advanced skater stats."""
        stats = AdvancedSkaterStats(
            player_id=8478402,
            player_name="Connor McDavid",
            team_abbrev="EDM",
            season="20242025",
            games_played=50,
            toi_seconds=60 * 22 * 50,  # ~22 min/game
            corsi_for=1000,
            corsi_against=800,
            corsi_pct=55.5,
            xg_for=45.0,
            xg_against=30.0,
        )

        assert stats.corsi_diff == 200
        assert stats.xg_diff == 15.0
        assert stats.toi_minutes == (60 * 22 * 50) / 60

    def test_pdo(self):
        """Test PDO calculation (luck metric)."""
        stats = AdvancedSkaterStats(
            player_id=12345,
            player_name="Test Player",
            team_abbrev="TOR",
            season="20242025",
            on_ice_sh_pct=10.0,
            on_ice_sv_pct=92.0,
            pdo=102.0,  # Pre-calculated
        )

        # PDO around 100 is average
        assert stats.pdo == 102.0


class TestAdvancedGoalieStats:
    """Tests for AdvancedGoalieStats model."""

    def test_basic_stats(self):
        """Test creating advanced goalie stats."""
        stats = AdvancedGoalieStats(
            player_id=8479394,
            player_name="Connor Hellebuyck",
            team_abbrev="WPG",
            season="20242025",
            games_played=50,
            toi_seconds=60 * 60 * 50,  # 60 min/game
            shots_against=1500,
            goals_against=120,
            saves=1380,
            save_pct=0.920,
            xg_against=130.0,
            goals_saved_above_expected=10.0,
        )

        assert stats.saves == 1380
        assert stats.toi_minutes == 60 * 50

    def test_danger_saves(self):
        """Test high-danger save stats."""
        stats = AdvancedGoalieStats(
            player_id=12345,
            player_name="Test Goalie",
            team_abbrev="TOR",
            season="20242025",
            high_danger_shots=200,
            high_danger_goals=40,
            high_danger_save_pct=0.800,
        )

        assert stats.high_danger_save_pct == 0.800
