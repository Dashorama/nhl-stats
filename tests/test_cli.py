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
    monkeypatch.setenv("NHL_STATS_DB", str(target))
    result = CliRunner().invoke(main, ["stats"])
    assert result.exit_code == 0, result.output
    assert target.exists()
