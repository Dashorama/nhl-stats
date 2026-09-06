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
