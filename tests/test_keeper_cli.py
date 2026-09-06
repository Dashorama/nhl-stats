import json

from src.keeper import cli
from src.keeper.core import from_snapshot, reconcile, scanTrades
from src.keeper.sheet import make_plan
from tests.test_keeper_sheet import FIXTURES, FakeSheet, snapshot


def test_cli_dry_run_and_watermark_after_verified_apply(tmp_path, monkeypatch, capsys):
    before = snapshot()
    board = json.loads((FIXTURES / "keepers_2025.json").read_text())
    after = make_plan(before, reconcile(board, before))["expected"]
    api = FakeSheet(before, after)
    monkeypatch.setattr(cli, "Sheets", lambda *args: api)
    args = [
        "reconcile",
        "--input",
        str(FIXTURES / "keepers_2025.json"),
        "--season",
        "2025",
        "--state-dir",
        str(tmp_path),
    ]
    cli.main(args)
    assert not api.writes
    assert "dry_run" in capsys.readouterr().out
    cli.main(args + ["--apply"])
    assert len(api.writes) == 1
    scanned, _ = scanTrades(
        from_snapshot(before), json.loads((FIXTURES / "trades.json").read_text()), season=2024
    )
    api = FakeSheet(before, make_plan(before, scanned)["expected"])
    monkeypatch.setattr(cli, "Sheets", lambda *args: api)
    args = [
        "scan-trades",
        "--input",
        str(FIXTURES / "trades.json"),
        "--season",
        "2024",
        "--state-dir",
        str(tmp_path),
    ]
    cli.main(args)
    assert not list(tmp_path.glob("watermark*.json"))
    cli.main(args + ["--apply"])
    assert len(json.loads(next(tmp_path.glob("watermark*.json")).read_text())["seen"]) == 7


def test_recover_verified_sheet_after_watermark_write_failure(tmp_path, monkeypatch, capsys):
    before = snapshot()
    data = json.loads((FIXTURES / "trades.json").read_text())
    rows, _ = scanTrades(from_snapshot(before), data, season=2024)
    after = make_plan(before, rows)["expected"]
    api = FakeSheet(before, after)
    monkeypatch.setattr(cli, "Sheets", lambda *args: api)
    real_save = cli.save_json

    def fail_watermark(path, data):
        if path.name.startswith("watermark"):
            raise OSError("simulated disk failure")
        real_save(path, data)

    monkeypatch.setattr(cli, "save_json", fail_watermark)
    args = [
        "scan-trades",
        "--input",
        str(FIXTURES / "trades.json"),
        "--season",
        "2024",
        "--state-dir",
        str(tmp_path),
        "--apply",
    ]
    import pytest

    with pytest.raises(OSError, match="disk failure"):
        cli.main(args)
    assert list(tmp_path.glob("pending*.json"))
    monkeypatch.setattr(cli, "save_json", real_save)
    cli.main(args)
    assert len(api.writes) == 1
    assert not list(tmp_path.glob("pending*.json"))
    assert len(json.loads(next(tmp_path.glob("watermark*.json")).read_text())["seen"]) == 7
    capsys.readouterr()


def test_cli_rejects_missing_source_and_live_apply(tmp_path):
    import pytest

    with pytest.raises(SystemExit):
        cli.main(["reconcile", "--season", "2025", "--state-dir", str(tmp_path)])
    with pytest.raises(SystemExit):
        cli.main(
            [
                "reconcile",
                "--season",
                "2025",
                "--sheet-id",
                "live",
                "--apply",
                "--input",
                str(FIXTURES / "keepers_2025.json"),
                "--state-dir",
                str(tmp_path),
            ]
        )
    assert list(tmp_path.iterdir()) == []


def test_cli_preserves_empty_team_identity(tmp_path, monkeypatch, capsys):
    before = snapshot()
    rows = from_snapshot(before)
    empty_team = rows[-1].team
    source = rows[0]
    before = make_plan(before, [r for r in rows if r.team != empty_team])["expected"]
    api = FakeSheet(before, before)
    monkeypatch.setattr(cli, "Sheets", lambda *args: api)
    data = [
        {
            "season": 2026,
            "league_id": 5003,
            "date": "Oct 1, 4:10 am",
            "teams": [
                {"team": source.team, "received": ["Round 1"]},
                {"team": empty_team, "received": [source.player + " (FLA - RW)"]},
            ],
        }
    ]
    input_file = tmp_path / "trade.json"
    input_file.write_text(json.dumps(data))
    cli.main(
        [
            "scan-trades",
            "--season",
            "2026",
            "--input",
            str(input_file),
            "--state-dir",
            str(tmp_path),
        ]
    )
    output = json.loads(capsys.readouterr().out)
    assert next(t for t in output["diff"] if t["team"] == empty_team)["added"] == [source.player]


def pending_before_write(tmp_path, monkeypatch):
    before = snapshot()
    board = json.loads((FIXTURES / "keepers_2025.json").read_text())
    api = FakeSheet(before, make_plan(before, reconcile(board, before))["expected"])
    monkeypatch.setattr(cli, "Sheets", lambda *args: api)
    write = api.write

    def fail_write(_):
        raise OSError("write never landed")

    api.write = fail_write
    args = [
        "reconcile",
        "--season",
        "2025",
        "--input",
        str(FIXTURES / "keepers_2025.json"),
        "--state-dir",
        str(tmp_path),
        "--apply",
    ]
    import pytest

    with pytest.raises(OSError, match="never landed"):
        cli.main(args)
    api.write = write
    return api, args


def test_pending_retry_writes_unchanged_source(tmp_path, monkeypatch, capsys):
    api, args = pending_before_write(tmp_path, monkeypatch)
    cli.main(args[:-1])
    assert api.writes == []
    assert list(tmp_path.glob("pending*.json"))
    cli.main(args)
    assert len(api.writes) == 1
    assert not list(tmp_path.glob("pending*.json"))
    capsys.readouterr()


def test_pending_conflict_retains_journal_and_backups(tmp_path, monkeypatch, capsys):
    api, args = pending_before_write(tmp_path, monkeypatch)
    api.before["raw_formulas"][3][2] = "Owner edited this keeper"
    pending = next(tmp_path.glob("pending*.json"))
    prior = pending.read_text()
    backups = list((tmp_path / "backups").glob("*.json"))
    import pytest

    with pytest.raises(ValueError, match="conflicts"):
        cli.main(args)
    assert api.writes == []
    assert pending.read_text() == prior
    assert list((tmp_path / "backups").glob("*.json")) == backups
    capsys.readouterr()
