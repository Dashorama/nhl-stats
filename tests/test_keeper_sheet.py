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
    before["raw_validation"] = [{"strict": True}] * (len(before["raw_values"]) - 3)
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
    if kwargs.get('ranges'):
        return {'sheets':[{'data':[{'rowData':[{'values':[{'dataValidation':r}]}
                   for r in DATA['snapshot']['raw_validation']]}]}]}
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
    assert all(path.startswith(TEST_SHEET + "/values/") for path, _ in calls[1:-1])
    assert calls[-1] == (
        TEST_SHEET,
        {
            "ranges": f"'Raw Data'!G4:G{len(before['raw_values'])}",
            "fields": "sheets(data(rowData(values(dataValidation))))",
        },
    )
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


def test_formula_offsets_match_sheet_row_references():
    from src.keeper.sheet import shifted

    assert shifted("=F10-$B$1-1", -3) == "=F7-$B$1-1"
    assert shifted("=E10+$G$1+G10", 3) == "=E13+$G$1+G13"
    formula = (
        "=Index('List Of Teams And Owners'!$A$2:$B$13,"
        "Match(B10,'List Of Teams And Owners'!$B$2:$B$13,0),1)"
    )
    assert shifted(formula, -2) == formula.replace("B10", "B8")


@pytest.mark.parametrize("error", ["#NAME?", "#NUM!", "#NULL!"])
def test_all_sheet_formula_errors_fail_verification(error):
    from src.keeper.sheet import Sheets, verify

    before = snapshot()
    after = copy.deepcopy(before)
    after["raw_values"][3][3] = error
    with pytest.raises(ValueError, match="formula error"):
        verify(after, before)
    api = Sheets.__new__(Sheets)
    api.tabs = {"UI": {"gridProperties": {"rowCount": 1}}}
    api.values = lambda *args: [[error]]
    with pytest.raises(ValueError, match="UI formula error"):
        api.check_ui()


def test_empty_block_keeps_one_physical_row_and_insert_structure():
    from dataclasses import replace

    from src.keeper.core import from_snapshot

    before = snapshot()
    rows = from_snapshot(before)
    empty = rows[-1].team
    start = next(i for i, r in enumerate(before["raw_values"]) if r and r[0] == empty)
    rows = [replace(r, team=rows[0].team) if r.team == empty else r for r in rows]
    plan = make_plan(before, rows)
    removal = plan["requests"][0]["deleteDimension"]["range"]
    assert removal["startIndex"] == start + 1
    assert removal["endIndex"] == len(before["raw_values"])
    pastes = {r["copyPaste"]["pasteType"] for r in plan["requests"] if "copyPaste" in r}
    assert "PASTE_FORMAT" in pastes
    assert "PASTE_DATA_VALIDATION" in pastes


@pytest.mark.parametrize("cell", [(0, 1), (3, 0), (3, 5), (3, 2)])
def test_formula_value_comparison_cannot_hide_behind_owner_check(cell, tmp_path):
    before = snapshot()
    board = json.loads((FIXTURES / "keepers_2025.json").read_text())
    plan = make_plan(before, reconcile(board, before))
    wrong = copy.deepcopy(plan["expected"])
    wrong["raw_formulas"][cell[0]][cell[1]] = "static replacement"
    with pytest.raises(ValueError, match="^post-write formula/value verification failed"):
        apply_plan(FakeSheet(before, wrong), TEST_SHEET, before, plan, tmp_path, apply=True)


def test_apply_checks_dependent_ui_before_success(tmp_path):
    before = snapshot()
    board = json.loads((FIXTURES / "keepers_2025.json").read_text())
    plan = make_plan(before, reconcile(board, before))
    api = FakeSheet(before, plan["expected"])

    def broken_ui():
        raise ValueError("dependent UI broken")

    api.check_ui = broken_ui
    with pytest.raises(ValueError, match="dependent UI broken"):
        apply_plan(api, TEST_SHEET, before, plan, tmp_path, apply=True)


def test_empty_template_uses_current_year_input():
    from src.keeper.core import from_snapshot

    before = snapshot()
    rows = from_snapshot(before)
    rows = [r for r in rows if r.team != rows[-1].team]
    plan = make_plan(before, rows)
    assert plan["expected"]["raw_formulas"][-1][4] == int(before["raw_values"][0][1])


def test_content_requests_never_target_headers():
    before = snapshot()
    board = json.loads((FIXTURES / "keepers_2025.json").read_text())
    plan = make_plan(before, reconcile(board, before))
    for request in plan["requests"]:
        if "updateCells" in request:
            update = request["updateCells"]
            assert update["range"]["startRowIndex"] == 3
            assert update["range"]["endRowIndex"] - 3 == len(update["rows"])


def test_count_validation_targets_only_keeper_g_cells_and_is_verified(tmp_path):
    from src.keeper.sheet import verify

    before = snapshot()
    board = json.loads((FIXTURES / "keepers_2025.json").read_text())
    plan = make_plan(before, reconcile(board, before))
    rules = [r["setDataValidation"] for r in plan["requests"] if "setDataValidation" in r]
    assert rules == [
        {
            "range": {
                "sheetId": 0,
                "startRowIndex": i,
                "endRowIndex": i + 1,
                "startColumnIndex": 6,
                "endColumnIndex": 7,
            },
            "rule": {
                "condition": {
                    "type": "CUSTOM_FORMULA",
                    "values": [
                        {
                            "userEnteredValue": f"=AND(ISNUMBER(G{i + 1}),G{i + 1}>=0,"
                            f"MOD(G{i + 1},1)=0)"
                        }
                    ],
                },
                "strict": True,
            },
        }
        for i in range(3, 63)
    ]
    validation_index = next(i for i, r in enumerate(plan["requests"]) if "setDataValidation" in r)
    value_index = next(i for i, r in enumerate(plan["requests"]) if "updateCells" in r)
    assert validation_index < value_index
    after = copy.deepcopy(plan["expected"])
    after["raw_validation"][0] = {"condition": {"type": "NUMBER_BETWEEN"}}
    with pytest.raises(ValueError, match="validation"):
        verify(after, plan["expected"])
    before["raw_validation"] = [{"strict": True}]
    api = FakeSheet(before, plan["expected"])
    apply_plan(api, TEST_SHEET, before, plan, tmp_path, apply=True)
    assert json.loads(next(tmp_path.glob("*.json")).read_text())["raw_validation"] == [
        {"strict": True}
    ]


def test_plan_exposes_contract_year_and_count_deltas():
    from dataclasses import replace

    from src.keeper.core import from_snapshot

    before = snapshot()
    rows = from_snapshot(before)
    rows[0] = replace(rows[0], first_year=rows[0].first_year - 1, traded=2)
    plan = make_plan(before, rows)
    assert plan["diff"][0]["updated"] == [
        {
            "player": rows[0].player,
            "first_year": {"before": 2024, "after": 2023},
            "trade_count": {"before": 0, "after": 2},
        }
    ]
