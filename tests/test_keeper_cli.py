import json

from src.keeper import cli
from src.keeper.core import reconcile
from src.keeper.sheet import make_plan
from test_keeper_sheet import FakeSheet, FIXTURES, snapshot


def test_cli_dry_run_and_watermark_after_verified_apply(tmp_path, monkeypatch, capsys):
    before = snapshot()
    board = json.loads((FIXTURES / 'keepers_2025.json').read_text())
    after = make_plan(before, reconcile(board, before))['expected']
    api = FakeSheet(before, after)
    monkeypatch.setattr(cli, 'Sheets', lambda *args: api)
    args = ['reconcile', '--input', str(FIXTURES / 'keepers_2025.json'), '--season', '2025',
            '--state-dir', str(tmp_path)]
    cli.main(args)
    assert not api.writes
    assert 'dry_run' in capsys.readouterr().out
    cli.main(args + ['--apply'])
    assert len(api.writes) == 1
    api = FakeSheet(before, before)
    monkeypatch.setattr(cli, 'Sheets', lambda *args: api)
    args = ['scan-trades', '--input', str(FIXTURES / 'trades.json'), '--season', '2024',
            '--state-dir', str(tmp_path)]
    cli.main(args)
    assert not list(tmp_path.glob('watermark*.json'))
    cli.main(args + ['--apply'])
    assert len(json.loads(next(tmp_path.glob('watermark*.json')).read_text())['seen']) == 7
