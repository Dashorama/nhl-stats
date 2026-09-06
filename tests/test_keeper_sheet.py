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


def test_expand_and_zero_keeper_template():
    from src.keeper.core import from_snapshot
    before = snapshot()
    rows = from_snapshot(before)
    destination = rows[0].team
    emptied = rows[-1].team
    from dataclasses import replace
    rows = [replace(r, team=destination) if r.team == emptied else r for r in rows]
    plan = make_plan(before, rows)
    assert any('insertDimension' in r for r in plan['requests'])
    copies = [r['copyPaste'] for r in plan['requests'] if 'copyPaste' in r]
    assert {r['source']['startColumnIndex'] for r in copies if r['pasteType'] == 'PASTE_FORMULA'} == {0, 1, 3, 5}
    assert plan['expected']['raw_formulas'][-1][2] == ''
    assert plan['expected']['raw_formulas'][-1][1] == "='List Of Teams And Owners'!$B$13"


@pytest.mark.parametrize('mutation,message', [
    ('length', 'snapshot'), ('partial', 'incomplete'), ('blocks', 'contiguous'),
    ('unknown', 'unknown team'),
])
def test_bad_sheet_plan_rejected(mutation, message):
    from src.keeper.core import Keeper, from_snapshot
    before = snapshot()
    rows = from_snapshot(before)
    if mutation == 'length':
        before['raw_formulas'].pop()
    elif mutation == 'partial':
        before['raw_formulas'][3] = ['=x']
    elif mutation == 'blocks':
        before['raw_values'][4][0] = 'Another'
    else:
        rows.append(Keeper('Unknown', 'Name', 2025, 0))
    with pytest.raises(ValueError, match=message):
        make_plan(before, rows)


def test_verification_owner_and_error_cells():
    from src.keeper.sheet import verify
    expected = snapshot()
    actual = copy.deepcopy(expected)
    actual['raw_values'][3][1] = 'Wrong owner'
    with pytest.raises(ValueError, match='owner alignment'):
        verify(actual, expected)
    actual = copy.deepcopy(expected)
    actual['raw_values'][3][3] = '#REF!'
    with pytest.raises(ValueError, match='formula error'):
        verify(actual, expected)
