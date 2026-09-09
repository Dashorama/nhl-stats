"""Tests for CLI-level wiring."""

from click.testing import CliRunner

from src.cli import main


def test_db_path_can_be_pointed_at_another_database(tmp_path):
    target = tmp_path / "other.db"
    result = CliRunner().invoke(main, ["--db", str(target), "stats"])
    assert result.exit_code == 0, result.output
    assert target.exists()


def test_db_path_can_come_from_the_environment(tmp_path, monkeypatch):
    target = tmp_path / "env.db"
    monkeypatch.setenv("NHL_STATS_DB_PATH", str(target))
    result = CliRunner().invoke(main, ["stats"])
    assert result.exit_code == 0, result.output
    assert target.exists()


def _seed(path, *, situation="5v5"):
    from src.storage.database import Database

    db = Database(path)
    db.upsert_games(
        [
            {
                "id": 2024020001,
                "season": "20242025",
                "date": "2024-10-04",
                "game_type": 2,
                "home_team": "BUF",
                "away_team": "NJD",
                "game_state": "OFF",
            }
        ]
    )
    db.insert_shots(
        [
            {
                "season": "2024",
                "game_id": 2024020001,
                "moneypuck_game_id": 20001,
                "shot_id": 0,
                "situation": situation,
                "is_home": False,
                "goal": 0,
            }
        ]
    )
    db.insert_play_by_play(2024020001, [{"event_id": 51, "event_type": "faceoff", "period": 1}])
    return db


def test_validate_exits_zero_when_the_data_is_healthy(tmp_path):
    path = tmp_path / "healthy.db"
    _seed(path)

    result = CliRunner().invoke(main, ["--db", str(path), "validate"])

    assert result.exit_code == 0, result.output


def test_validate_exits_non_zero_when_a_check_fails(tmp_path):
    """cron and CI gate on this exit code; a silent 0 would defeat the whole guard."""
    path = tmp_path / "broken.db"
    _seed(path, situation="")

    result = CliRunner().invoke(main, ["--db", str(path), "validate"])

    assert result.exit_code == 1
    assert "shots_situation_populated" in result.output


def test_validate_exits_non_zero_when_a_required_season_is_missing(tmp_path):
    path = tmp_path / "corpus.db"
    _seed(path)

    result = CliRunner().invoke(
        main, ["--db", str(path), "validate", "--require-seasons", "20182019"]
    )

    assert result.exit_code == 1
    assert "20182019" in result.output


def test_the_preexisting_sqlalchemy_url_env_var_is_not_treated_as_a_path(tmp_path, monkeypatch):
    """Dockerfile, docker-compose and .env.example all set
    NHL_STATS_DB=sqlite:///data/nhl.db. Consuming that as a filesystem path would
    silently create a database in a directory literally named "sqlite:"."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("NHL_STATS_DB", "sqlite:///data/nhl.db")

    result = CliRunner().invoke(main, ["stats"])

    assert result.exit_code == 0, result.output
    assert not (tmp_path / "sqlite:").exists()
    assert (tmp_path / "data" / "nhl.db").exists()


def test_db_path_env_var_is_the_path_specific_name(tmp_path, monkeypatch):
    target = tmp_path / "env.db"
    monkeypatch.setenv("NHL_STATS_DB_PATH", str(target))

    result = CliRunner().invoke(main, ["stats"])

    assert result.exit_code == 0, result.output
    assert target.exists()
