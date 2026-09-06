"""Adapter contract: one atomic, backed-up, formula-safe test-copy write."""
import copy
import json
from pathlib import Path

import pytest

from src.keeper.core import reconcile
from src.keeper.sheet import TEST_SHEET, apply_plan, make_plan

FIXTURES = Path(__file__).parent / 'fixtures/keeper_reconcile'


def snapshot():
    return json.loads((FIXTURES / 'rawdata_backup.json').read_text())


def test_plan_preserves_formula_columns_and_owner_blocks():
    before = snapshot()
    board = json.loads((FIXTURES / 'keepers_2025.json').read_text())
    plan = make_plan(before, reconcile(board, before))
    deletes = [r['deleteDimension']['range'] for r in plan['requests'] if 'deleteDimension' in r]
    assert [(r['startIndex'], r['endIndex']) for r in deletes] == [(66, 67), (25, 26), (14, 15), (8, 9)]
    updates = [r['updateCells'] for r in plan['requests'] if 'updateCells' in r]
    assert {r['range']['startColumnIndex'] for r in updates} == {2, 4, 6}
    assert all(r['fields'] == 'userEnteredValue' for r in updates)
    assert len(plan['expected']['raw_values']) == 63
    for i, row in enumerate(plan['expected']['raw_formulas'][3:], 4):
        assert all(row[c].startswith('=') for c in (0, 1, 3, 5))
        assert row[1] == f"='List Of Teams And Owners'!$B${2 + (i-4)//5}"
    assert plan['expected']['raw_formulas'][:3] == before['raw_formulas'][:3]


class FakeSheet:
    def __init__(self, before, after):
        self.before, self.after = before, after
        self.writes = []

    def read(self):
        return copy.deepcopy(self.after if self.writes else self.before)

    def write(self, requests):
        self.writes.append(requests)

    def check_ui(self):
        pass


def test_dry_run_backup_apply_and_verification(tmp_path):
    before = snapshot()
    board = json.loads((FIXTURES / 'keepers_2025.json').read_text())
    plan = make_plan(before, reconcile(board, before))
    api = FakeSheet(before, plan['expected'])
    apply_plan(api, TEST_SHEET, before, plan, tmp_path)
    assert api.writes == [] and list(tmp_path.iterdir()) == []
    apply_plan(api, TEST_SHEET, before, plan, tmp_path, apply=True)
    assert api.writes == [plan['requests']]
    assert json.loads(next(tmp_path.glob('*.json')).read_text()) == before
    api = FakeSheet(before, before)
    with pytest.raises(ValueError, match='verification'):
        apply_plan(api, TEST_SHEET, before, plan, tmp_path, apply=True)


def test_apply_rejects_live_stale_and_bad_formulas(tmp_path):
    before = snapshot()
    board = json.loads((FIXTURES / 'keepers_2025.json').read_text())
    plan = make_plan(before, reconcile(board, before))
    api = FakeSheet(before, plan['expected'])
    with pytest.raises(ValueError, match='TEST COPY'):
        apply_plan(api, 'live-or-any-other-id', before, plan, tmp_path, apply=True)
    stale = copy.deepcopy(before)
    stale['raw_formulas'][3][2] = 'Changed by owner'
    with pytest.raises(ValueError, match='changed'):
        apply_plan(FakeSheet(stale, stale), TEST_SHEET, before, plan, tmp_path, apply=True)
    before['raw_formulas'][3][0] = 'static team'
    with pytest.raises(ValueError, match='formula'):
        make_plan(before, reconcile(board, before))
