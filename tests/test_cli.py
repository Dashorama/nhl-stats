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


def test_a_backfill_refuses_to_run_while_another_writer_holds_the_lock(tmp_path):
    """A multi-hour backfill and the nightly cron on one SQLite file means
    "database is locked", not a queue. Only one writer runs at a time."""
    import fcntl

    from src.cli import database_write_lock

    db_path = tmp_path / "locked.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    lock_file = tmp_path / ".nhl-stats-write.lock"

    holder = open(lock_file, "w")
    fcntl.flock(holder, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        with database_write_lock(db_path) as acquired:
            assert acquired is False
    finally:
        holder.close()


def test_the_lock_is_available_when_nothing_else_holds_it(tmp_path):
    from src.cli import database_write_lock

    with database_write_lock(tmp_path / "free.db") as acquired:
        assert acquired is True


def test_update_skips_rather_than_failing_when_the_lock_is_held(tmp_path, monkeypatch):
    """cron must not pile up or alarm: the next scheduled run catches up.

    The scraper is stubbed to blow up, so if the lock is not checked first this
    fails fast instead of making real network calls.
    """
    import fcntl

    import src.cli as cli_module

    def exploding_scraper(*args, **kwargs):
        raise AssertionError("update did work before checking the lock")

    monkeypatch.setattr(cli_module, "NHLAPIScraper", exploding_scraper)

    db_path = tmp_path / "busy.db"
    _seed(db_path)
    holder = open(tmp_path / ".nhl-stats-write.lock", "w")
    fcntl.flock(holder, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        result = CliRunner().invoke(main, ["--db", str(db_path), "update", "--daily"])
        assert result.exit_code == 0, result.output
        assert "lock" in result.output.lower()
    finally:
        holder.close()
