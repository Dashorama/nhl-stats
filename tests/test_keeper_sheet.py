"""Adapter contract: one atomic, backed-up, formula-safe test-copy write."""

import copy
import json
from pathlib import Path

import pytest

from src.keeper.core import reconcile
from src.keeper.sheet import TEST_SHEET, apply_plan, make_plan

FIXTURES = Path(__file__).parent / "fixtures/keeper_reconcile"


def snapshot():
    return json.loads((FIXTURES / "rawdata_backup.json").read_text())


def test_plan_preserves_formula_columns_and_owner_blocks():
    before = snapshot()
    board = json.loads((FIXTURES / "keepers_2025.json").read_text())
    plan = make_plan(before, reconcile(board, before))
    deletes = [r["deleteDimension"]["range"] for r in plan["requests"] if "deleteDimension" in r]
    assert [(r["startIndex"], r["endIndex"]) for r in deletes] == [
        (66, 67),
        (25, 26),
        (14, 15),
        (8, 9),
    ]
    updates = [r["updateCells"] for r in plan["requests"] if "updateCells" in r]
    assert {r["range"]["startColumnIndex"] for r in updates} == {2, 4, 6}
    assert all(r["fields"] == "userEnteredValue" for r in updates)
    assert len(plan["expected"]["raw_values"]) == 63
    for i, row in enumerate(plan["expected"]["raw_formulas"][3:], 4):
        assert all(row[c].startswith("=") for c in (0, 1, 3, 5))
        assert row[1] == f"='List Of Teams And Owners'!$B${2 + (i - 4) // 5}"
    assert plan["expected"]["raw_formulas"][:3] == before["raw_formulas"][:3]


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
    board = json.loads((FIXTURES / "keepers_2025.json").read_text())
    plan = make_plan(before, reconcile(board, before))
    api = FakeSheet(before, plan["expected"])
    apply_plan(api, TEST_SHEET, before, plan, tmp_path)
    assert api.writes == [] and list(tmp_path.iterdir()) == []
    apply_plan(api, TEST_SHEET, before, plan, tmp_path, apply=True)
    assert api.writes == [plan["requests"]]
    assert json.loads(next(tmp_path.glob("*.json")).read_text()) == before
    api = FakeSheet(before, before)
    with pytest.raises(ValueError, match="verification"):
        apply_plan(api, TEST_SHEET, before, plan, tmp_path, apply=True)


def test_apply_rejects_live_stale_and_bad_formulas(tmp_path):
    before = snapshot()
    board = json.loads((FIXTURES / "keepers_2025.json").read_text())
    plan = make_plan(before, reconcile(board, before))
    api = FakeSheet(before, plan["expected"])
    with pytest.raises(ValueError, match="TEST COPY"):
        apply_plan(api, "live-or-any-other-id", before, plan, tmp_path, apply=True)
    stale = copy.deepcopy(before)
    stale["raw_formulas"][3][2] = "Changed by owner"
    with pytest.raises(ValueError, match="changed"):
        apply_plan(FakeSheet(stale, stale), TEST_SHEET, before, plan, tmp_path, apply=True)
    before["raw_formulas"][3][0] = "static team"
    with pytest.raises(ValueError, match="formula"):
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
    assert any("insertDimension" in r for r in plan["requests"])
    copies = [r["copyPaste"] for r in plan["requests"] if "copyPaste" in r]
    assert {
        r["source"]["startColumnIndex"] for r in copies if r["pasteType"] == "PASTE_FORMULA"
    } == {0, 1, 3, 5}
    assert plan["expected"]["raw_formulas"][-1][2] == ""
    assert plan["expected"]["raw_formulas"][-1][1] == "='List Of Teams And Owners'!$B$13"


@pytest.mark.parametrize(
    "mutation,message",
    [
        ("length", "snapshot"),
        ("partial", "incomplete"),
        ("blocks", "contiguous"),
        ("unknown", "unknown team"),
    ],
)
def test_bad_sheet_plan_rejected(mutation, message):
    from src.keeper.core import Keeper, from_snapshot

    before = snapshot()
    rows = from_snapshot(before)
    if mutation == "length":
        before["raw_formulas"].pop()
    elif mutation == "partial":
        before["raw_formulas"][3] = ["=x"]
    elif mutation == "blocks":
        before["raw_values"][4][0] = "Another"
    else:
        rows.append(Keeper("Unknown", "Name", 2025, 0))
    with pytest.raises(ValueError, match=message):
        make_plan(before, rows)


def test_verification_owner_and_error_cells():
    from src.keeper.sheet import verify

    expected = snapshot()
    actual = copy.deepcopy(expected)
    actual["raw_values"][3][1] = "Wrong owner"
    with pytest.raises(ValueError, match="owner alignment"):
        verify(actual, expected)
    actual = copy.deepcopy(expected)
    actual["raw_values"][3][3] = "#REF!"
    with pytest.raises(ValueError, match="formula error"):
        verify(actual, expected)


def test_sheets_helper_paths_owner_checks_and_ui_errors(tmp_path):
    from src.keeper.sheet import Sheets

    before = snapshot()
    owners = list(dict.fromkeys((r[0], r[1]) for r in before["raw_values"][3:]))
    data = {"snapshot": before, "owners": owners}
    helper = tmp_path / "sheets.py"
    helper.write_text(
        """
import json
DATA = json.loads("""
        + repr(json.dumps(data))
        + """)
calls=[]
def call(path, **kwargs):
    calls.append((path,kwargs))
    if '/values/' not in path:
        return {'sheets':[{'properties':{'title':'Raw Data','sheetId':0,
                          'gridProperties':{'rowCount':100}}},
                          {'properties':{'title':'UI','sheetId':1,'gridProperties':{'rowCount':20}}}]}
    if 'List%20Of%20Teams' in path:return {'values':DATA['owners']}
    if 'UI' in path:return {'values':[['#REF!']]}
    key='raw_formulas' if kwargs.get('valueRenderOption')=='FORMULA' else 'raw_values'
    return {'values':DATA['snapshot'][key]}
"""
    )
    api = Sheets(TEST_SHEET, str(helper))
    assert api.read() == before
    calls = api.call.__globals__["calls"]
    assert all(path.startswith(TEST_SHEET + "/values/") for path, _ in calls[1:])
    with pytest.raises(ValueError, match="UI formula"):
        api.check_ui()
    state = api.call.__globals__["DATA"]
    state["owners"][0][1] = "Wrong Owner"
    with pytest.raises(ValueError, match="owner blocks"):
        api.read()
    state["owners"][0][1] = owners[0][1]
    state["snapshot"]["raw_formulas"][3][1] = "='List Of Teams And Owners'!$B$3"
    with pytest.raises(ValueError, match="wrong owner cell"):
        api.read()
    api.sheet_id = "not-test-copy"
    with pytest.raises(ValueError, match="TEST COPY"):
        api.write([])
    helper.write_text(helper.read_text().replace("'sheetId':0", "'sheetId':99"))
    with pytest.raises(ValueError, match="sheetId"):
        Sheets(TEST_SHEET, str(helper))


def test_backup_is_durable_before_first_write(tmp_path, monkeypatch):
    import src.keeper.sheet as sheet

    before = snapshot()
    board = json.loads((FIXTURES / "keepers_2025.json").read_text())
    plan = make_plan(before, reconcile(board, before))
    api = FakeSheet(before, plan["expected"])
    written = api.write

    def check_backup(requests):
        assert json.loads(next(tmp_path.glob("*.json")).read_text()) == before
        written(requests)

    api.write = check_backup
    apply_plan(api, TEST_SHEET, before, plan, tmp_path, apply=True)
    failed = FakeSheet(before, plan["expected"])

    def unavailable(_):
        raise OSError("backup fsync failed")

    monkeypatch.setattr(sheet.os, "fsync", unavailable)
    with pytest.raises(OSError, match="backup fsync"):
        apply_plan(failed, TEST_SHEET, before, plan, tmp_path, apply=True)
    assert failed.writes == []
