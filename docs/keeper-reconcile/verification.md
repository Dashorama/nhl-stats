# Verification evidence

Baseline origin/main: 59 passed, 3 failed (`sqlite3.OperationalError: no such table: players`).
The existing generator test fixture now creates its required players table and mocks
LLM narration, so tests do not depend on an external narrator. No generator production
code changed. Final full suite: `89 passed, 2 warnings in 5.02s`. Existing integration
marker warnings remain. Scoped Ruff passed. `pip wheel . --no-deps` built nhl-stats.

Live read-only collector checks on 2026-09-06: 60 2025 keeper badges matched staged
player lists; seven 2024 trade records matched the corresponding supplied sample.
An empty 2026 transaction page is recognized explicitly.

TEST COPY integration: dry-run of already reconciled copy produced no additions or
removals. Inserted one synthetic nonkeeper into the first team through the backed-up
atomic planner, verified its formulas and all UI formulas, then reconciled it away.
Both operations verified every formula, literal, and owner block. Backups:
`/tmp/keeper-integration/backups/raw-data-20260906T122121.413321Z.json` and
`/tmp/keeper-integration/backups/raw-data-20260906T122123.730140Z.json`.
No live-sheet writes. Existing Google grid formatting/validation was inspected by API.

## mutation_proof

Tests were committed before implementation. Initial red evidence:

```text
ModuleNotFoundError: No module named 'src.keeper'
ModuleNotFoundError: No module named 'src.keeper.sheet'
ImportError: cannot import name 'cli' from 'src.keeper'
ModuleNotFoundError: No module named 'src.keeper.collect'
AttributeError: module 'src.keeper.cli' has no attribute 'save_json'
FAILED test_empty_live_transaction_table - ValueError: unrecognized trade row
```

The following targeted implementation mutations were applied in the isolated
worktree, tested, and reverted. All twelve produced failures. Green after restoring
all mutations: `27 passed in 0.43s` (keeper tests). The baseline generator fixture
repair's red is the three missing-table failures above; green: `3 passed in 2.21s`.

## Drop reconcile output

```text
F                                                                        [100%]
=================================== FAILURES ===================================
_________________________ test_reconcile_ground_truth __________________________
tests/test_keeper_core.py:24: in test_reconcile_ground_truth
    assert [(k.team, k.player, str(k.first_year), str(k.traded)) for k in result] == [
E   AssertionError: assert [] == [('Tage Again...4', '0'), ...]
E     
E     Right contains 60 more items, first extra item: ('Tage Against The Machine', 'Sam Reinhart', '2024', '0')
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED tests/test_keeper_core.py::test_reconcile_ground_truth - AssertionErro...
1 failed in 0.02s
```

## Mutate caller snapshot

```text
F                                                                        [100%]
=================================== FAILURES ===================================
_________________________ test_reconcile_ground_truth __________________________
tests/test_keeper_core.py:27: in test_reconcile_ground_truth
    assert (board, snapshot) == original
E   AssertionError: assert ({'Bitch Slap..., ...], ...]}) == ({'Bitch Slap..., ...], ...]})
E     
E     At index 1 diff: {'raw_values': [['Current Year', 'MUTATED', '', '', '', 'Keeper Starting Term', '3'], [], ['Team Name', 'Owner Name', 'Player Name', 'Years Remaining', 'First Year Kept', 'Year Expiring', 'Traded?'], ['Tage Against The Machine', 'David Erner', 'Sam Reinhart', '1', '2024', '2027', '0'], ['Tage Against The Machine', 'David Erner', 'Tage Thompson', '0', '2023', '2026', '0'], ['Tage Against The Machine', 'David Erner', 'Brandon Hagel', '2', '2025', '2028', '0'], ['Tage Against The Machine', 'David Erner', 'Mitch Marner', '-1', '2022', '2025', '0'], ['Tage A...
E     
E     ...Full output truncated (2 lines hidden), use '-vv' to show
=========================== short test summary info ============================
FAILED tests/test_keeper_core.py::test_reconcile_ground_truth - AssertionErro...
1 failed in 0.03s
```

## Make trade bonus cumulative

```text
FF                                                                       [100%]
=================================== FAILURES ===================================
________________ test_trade_fixture_five_real_trades_and_replay ________________
tests/test_keeper_core.py:47: in test_trade_fixture_five_real_trades_and_replay
    assert result == rows
E   AssertionError: assert [Keeper(team=...raded=0), ...] == [Keeper(team=...raded=0), ...]
E     
E     At index 9 diff: Keeper(team='Makings of a Varsity Athlete', player='Nathan MacKinnon', first_year=2022, traded=2) != Keeper(team='Makings of a Varsity Athlete', player='Nathan MacKinnon', first_year=2022, traded=1)
E     Use -v to get more diff
____________ test_chained_trades_chronology_one_time_and_watermark _____________
tests/test_keeper_core.py:92: in test_chained_trades_chronology_one_time_and_watermark
    assert next(r for r in result if r.player == "Player One") == Keeper("C", "Player One", 2022, 1)
E   AssertionError: assert Keeper(team='...022, traded=2) == Keeper(team='...022, traded=1)
E     
E     Omitting 3 identical items, use -vv to show
E     Differing attributes:
E     ['traded']
E     
E     Drill down into differing attribute traded:
E       traded: 2 != 1
=========================== short test summary info ============================
FAILED tests/test_keeper_core.py::test_trade_fixture_five_real_trades_and_replay
FAILED tests/test_keeper_core.py::test_chained_trades_chronology_one_time_and_watermark
2 failed in 0.03s
```

## Disable seen transaction skip

```text
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_chained_trades_chronology_one_time_and_watermark _____________
tests/test_keeper_core.py:93: in test_chained_trades_chronology_one_time_and_watermark
    assert scanTrades(result, trades, season=2025, state=state) == (result, state)
src/keeper/core.py:163: in scanTrades
    raise ValueError(f"trade ownership conflict for {player}")
E   ValueError: trade ownership conflict for Player One
=========================== short test summary info ============================
FAILED tests/test_keeper_core.py::test_chained_trades_chronology_one_time_and_watermark
1 failed in 0.02s
```

## Remove validation raises

```text
.F.FFFFFFFFFF.FF.FFFFFFF.                                                [100%]
=================================== FAILURES ===================================
__________________ test_reconcile_tag_count_and_unknown_team ___________________
tests/test_keeper_core.py:33: in test_reconcile_tag_count_and_unknown_team
    with pytest.raises(ValueError, match="keeper count"):
E   Failed: DID NOT RAISE <class 'ValueError'>
____________ test_chained_trades_chronology_one_time_and_watermark _____________
tests/test_keeper_core.py:94: in test_chained_trades_chronology_one_time_and_watermark
    with pytest.raises(ValueError, match="season"):
E   Failed: DID NOT RAISE <class 'ValueError'>
_______ test_reconcile_rejects_corrupt_inputs[duplicate_board-duplicate] _______
tests/test_keeper_core.py:117: in test_reconcile_rejects_corrupt_inputs
    with pytest.raises(ValueError, match=message):
E   Failed: DID NOT RAISE <class 'ValueError'>
_______ test_reconcile_rejects_corrupt_inputs[duplicate_sheet-duplicate] _______
tests/test_keeper_core.py:117: in test_reconcile_rejects_corrupt_inputs
    with pytest.raises(ValueError, match=message):
E   Failed: DID NOT RAISE <class 'ValueError'>
_______ test_reconcile_rejects_corrupt_inputs[malformed_sheet-snapshot] ________
tests/test_keeper_core.py:118: in test_reconcile_rejects_corrupt_inputs
    reconcile(board, snapshot)
src/keeper/core.py:54: in reconcile
    old = from_snapshot(snapshot)
src/keeper/core.py:45: in from_snapshot
    if any((str(r[6]) not in ('0', '1') for r in data)):
src/keeper/core.py:45: in <genexpr>
    if any((str(r[6]) not in ('0', '1') for r in data)):
E   IndexError: list index out of range
__________ test_reconcile_rejects_corrupt_inputs[invalid_flag-Traded] __________
tests/test_keeper_core.py:117: in test_reconcile_rejects_corrupt_inputs
    with pytest.raises(ValueError, match=message):
E   Failed: DID NOT RAISE <class 'ValueError'>
_____________________ test_matching_ambiguity_is_an_error ______________________
tests/test_keeper_core.py:124: in test_matching_ambiguity_is_an_error
    with pytest.raises(ValueError, match="ambiguous"):
E   Failed: DID NOT RAISE <class 'ValueError'>
______________ test_trade_conflicts_fail_closed[sides-two teams] _______________
tests/test_keeper_core.py:165: in test_trade_conflicts_fail_closed
    with pytest.raises(ValueError, match=message):
E   Failed: DID NOT RAISE <class 'ValueError'>
_________ test_trade_conflicts_fail_closed[unknown-unknown acquiring] __________
tests/test_keeper_core.py:166: in test_trade_conflicts_fail_closed
    scanTrades(rows, trades, season=2025)
src/keeper/core.py:123: in scanTrades
    if team_key(row.team) not in (team_key(source), team_key(target)):
src/keeper/core.py:24: in team_key
    key = normalize(name)
src/keeper/core.py:19: in normalize
    return ''.join((c for c in unicodedata.normalize('NFKD', value).casefold() if c.isalnum()))
E   TypeError: normalize() argument 2 must be str, not None
__________ test_trade_conflicts_fail_closed[owner-ownership conflict] __________
tests/test_keeper_core.py:165: in test_trade_conflicts_fail_closed
    with pytest.raises(ValueError, match=message):
E   Failed: DID NOT RAISE <class 'ValueError'>
_______________ test_trade_conflicts_fail_closed[league-league] ________________
tests/test_keeper_core.py:165: in test_trade_conflicts_fail_closed
    with pytest.raises(ValueError, match=message):
E   Failed: DID NOT RAISE <class 'ValueError'>
__________________ test_dry_run_backup_apply_and_verification __________________
tests/test_keeper_sheet.py:66: in test_dry_run_backup_apply_and_verification
    with pytest.raises(ValueError, match="verification"):
E   Failed: DID NOT RAISE <class 'ValueError'>
________________ test_apply_rejects_live_stale_and_bad_formulas ________________
tests/test_keeper_sheet.py:75: in test_apply_rejects_live_stale_and_bad_formulas
    with pytest.raises(ValueError, match="TEST COPY"):
E   Failed: DID NOT RAISE <class 'ValueError'>
________________ test_bad_sheet_plan_rejected[length-snapshot] _________________
tests/test_keeper_sheet.py:129: in test_bad_sheet_plan_rejected
    make_plan(before, rows)
src/keeper/sheet.py:30: in make_plan
    if len(row) < 7 or len(formulas[i]) < 7:
E   IndexError: list index out of range
_______________ test_bad_sheet_plan_rejected[partial-incomplete] _______________
tests/test_keeper_sheet.py:129: in test_bad_sheet_plan_rejected
    make_plan(before, rows)
src/keeper/sheet.py:32: in make_plan
    if not all((isinstance(formulas[i][c], str) and formulas[i][c].startswith('=') for c in FORMULA_COLUMNS)):
src/keeper/sheet.py:32: in <genexpr>
    if not all((isinstance(formulas[i][c], str) and formulas[i][c].startswith('=') for c in FORMULA_COLUMNS)):
E   IndexError: list index out of range
_______________ test_bad_sheet_plan_rejected[blocks-contiguous] ________________
tests/test_keeper_sheet.py:128: in test_bad_sheet_plan_rejected
    with pytest.raises(ValueError, match=message):
E   Failed: DID NOT RAISE <class 'ValueError'>
______________ test_bad_sheet_plan_rejected[unknown-unknown team] ______________
tests/test_keeper_sheet.py:128: in test_bad_sheet_plan_rejected
    with pytest.raises(ValueError, match=message):
E   Failed: DID NOT RAISE <class 'ValueError'>
___________________ test_verification_owner_and_error_cells ____________________
tests/test_keeper_sheet.py:138: in test_verification_owner_and_error_cells
    with pytest.raises(ValueError, match="owner alignment"):
E   Failed: DID NOT RAISE <class 'ValueError'>
______________ test_live_markup_draft_matches_staged_keeper_board ______________
tests/test_keeper_collect.py:18: in test_live_markup_draft_matches_staged_keeper_board
    with pytest.raises(ValueError, match="season"):
E   Failed: DID NOT RAISE <class 'ValueError'>
________________ test_live_markup_trade_sample_and_fail_closed _________________
tests/test_keeper_collect.py:32: in test_live_markup_trade_sample_and_fail_closed
    parse_trades("<html>Login required</html>", 2024, 17419)
src/keeper/collect.py:26: in parse_trades
    rows = table.select('tr')
E   AttributeError: 'NoneType' object has no attribute 'select'
=========================== short test summary info ============================
FAILED tests/test_keeper_core.py::test_reconcile_tag_count_and_unknown_team
FAILED tests/test_keeper_core.py::test_chained_trades_chronology_one_time_and_watermark
FAILED tests/test_keeper_core.py::test_reconcile_rejects_corrupt_inputs[duplicate_board-duplicate]
FAILED tests/test_keeper_core.py::test_reconcile_rejects_corrupt_inputs[duplicate_sheet-duplicate]
FAILED tests/test_keeper_core.py::test_reconcile_rejects_corrupt_inputs[malformed_sheet-snapshot]
FAILED tests/test_keeper_core.py::test_reconcile_rejects_corrupt_inputs[invalid_flag-Traded]
FAILED tests/test_keeper_core.py::test_matching_ambiguity_is_an_error - Faile...
FAILED tests/test_keeper_core.py::test_trade_conflicts_fail_closed[sides-two teams]
FAILED tests/test_keeper_core.py::test_trade_conflicts_fail_closed[unknown-unknown acquiring]
FAILED tests/test_keeper_core.py::test_trade_conflicts_fail_closed[owner-ownership conflict]
FAILED tests/test_keeper_core.py::test_trade_conflicts_fail_closed[league-league]
FAILED tests/test_keeper_sheet.py::test_dry_run_backup_apply_and_verification
FAILED tests/test_keeper_sheet.py::test_apply_rejects_live_stale_and_bad_formulas
FAILED tests/test_keeper_sheet.py::test_bad_sheet_plan_rejected[length-snapshot]
FAILED tests/test_keeper_sheet.py::test_bad_sheet_plan_rejected[partial-incomplete]
FAILED tests/test_keeper_sheet.py::test_bad_sheet_plan_rejected[blocks-contiguous]
FAILED tests/test_keeper_sheet.py::test_bad_sheet_plan_rejected[unknown-unknown team]
FAILED tests/test_keeper_sheet.py::test_verification_owner_and_error_cells - ...
FAILED tests/test_keeper_collect.py::test_live_markup_draft_matches_staged_keeper_board
FAILED tests/test_keeper_collect.py::test_live_markup_trade_sample_and_fail_closed
20 failed, 5 passed in 0.32s
```

## Write into protected column

```text
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_plan_preserves_formula_columns_and_owner_blocks _____________
tests/test_keeper_sheet.py:31: in test_plan_preserves_formula_columns_and_owner_blocks
    assert {r["range"]["startColumnIndex"] for r in updates} == {2, 4, 6}
E   assert {0, 4, 6} == {2, 4, 6}
E     
E     Extra items in the left set:
E     0
E     Extra items in the right set:
E     2
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED tests/test_keeper_sheet.py::test_plan_preserves_formula_columns_and_owner_blocks
1 failed in 0.03s
```

## Disable dry-run gate

```text
FF                                                                       [100%]
=================================== FAILURES ===================================
__________________ test_dry_run_backup_apply_and_verification __________________
tests/test_keeper_sheet.py:61: in test_dry_run_backup_apply_and_verification
    assert api.writes == [] and list(tmp_path.iterdir()) == []
E   AssertionError: assert ([[{'deleteDim... ...]}}, ...]] == []
E     
E     Left contains one more item: [{'deleteDimension': {'range': {'dimension': 'ROWS', 'endIndex': 67, 'sheetId': 0, 'startIndex': 66}}}, {'deleteDimens..., {'values': [{...}]}, {'values': [{...}]}, {'values': [{...}]}, {'values': [{...}]}, {'values': [{...}]}, ...]}}, ...]
E     Use -v to get more diff)
_____________ test_cli_dry_run_and_watermark_after_verified_apply ______________
tests/test_keeper_cli.py:25: in test_cli_dry_run_and_watermark_after_verified_apply
    assert not api.writes
E   AssertionError: assert not [[{'deleteDimension': {'range': {'dimension': 'ROWS', 'endIndex': 67, 'sheetId': 0, 'startIndex': 66}}}, {'deleteDimen...': [...]}, {'values': [...]}, {'values': [...]}, {'values': [...]}, {'values': [...]}, {'values': [...]}, ...]}}, ...]]
E    +  where [[{'deleteDimension': {'range': {'dimension': 'ROWS', 'endIndex': 67, 'sheetId': 0, 'startIndex': 66}}}, {'deleteDimen...': [...]}, {'values': [...]}, {'values': [...]}, {'values': [...]}, {'values': [...]}, {'values': [...]}, ...]}}, ...]] = <tests.test_keeper_sheet.FakeSheet object at 0x7800a982a170>.writes
=========================== short test summary info ============================
FAILED tests/test_keeper_sheet.py::test_dry_run_backup_apply_and_verification
FAILED tests/test_keeper_cli.py::test_cli_dry_run_and_watermark_after_verified_apply
2 failed in 0.10s
```

## Skip backups

```text
F                                                                        [100%]
=================================== FAILURES ===================================
__________________ test_dry_run_backup_apply_and_verification __________________
tests/test_keeper_sheet.py:61: in test_dry_run_backup_apply_and_verification
    assert api.writes == [] and list(tmp_path.iterdir()) == []
E   AssertionError: assert ([[{'deleteDim... ...]}}, ...]] == []
E     
E     Left contains one more item: [{'deleteDimension': {'range': {'dimension': 'ROWS', 'endIndex': 67, 'sheetId': 0, 'startIndex': 66}}}, {'deleteDimens..., {'values': [{...}]}, {'values': [{...}]}, {'values': [{...}]}, {'values': [{...}]}, {'values': [{...}]}, ...]}}, ...]
E     Use -v to get more diff)
=========================== short test summary info ============================
FAILED tests/test_keeper_sheet.py::test_dry_run_backup_apply_and_verification
1 failed in 0.03s
```

## Skip pending recovery

```text
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_recover_verified_sheet_after_watermark_write_failure ___________
tests/test_keeper_cli.py:81: in test_recover_verified_sheet_after_watermark_write_failure
    assert len(api.writes) == 1
E   AssertionError: assert 2 == 1
E    +  where 2 = len([[{'deleteDimension': {'range': {'dimension': 'ROWS', 'endIndex': 51, 'sheetId': 0, 'startIndex': 49}}}, {'deleteDimen...alues': [...]}, {'values': [...]}, {'values': [...]}, {'values': [...]}, {'values': [...]}, {'values': [...]}, ...]}}]])
E    +    where [[{'deleteDimension': {'range': {'dimension': 'ROWS', 'endIndex': 51, 'sheetId': 0, 'startIndex': 49}}}, {'deleteDimen...alues': [...]}, {'values': [...]}, {'values': [...]}, {'values': [...]}, {'values': [...]}, {'values': [...]}, ...]}}]] = <tests.test_keeper_sheet.FakeSheet object at 0x7644859ee4d0>.writes
=========================== short test summary info ============================
FAILED tests/test_keeper_cli.py::test_recover_verified_sheet_after_watermark_write_failure
1 failed in 0.14s
```

## Drop parsed draft player

```text
F                                                                        [100%]
=================================== FAILURES ===================================
______________ test_live_markup_draft_matches_staged_keeper_board ______________
tests/test_keeper_collect.py:15: in test_live_markup_draft_matches_staged_keeper_board
    assert {t: [p["player"] for p in picks] for t, picks in result.items()} == {
E   AssertionError: assert {'Bitch Slapp...ertson'], ...} == {'Bitch Slapp...ertson'], ...}
E     
E     Omitting 11 identical items, use -vv to show
E     Differing items:
E     {'Trou Trou Train': ['Mackenzie Blackwood', 'Radko Gudas', 'Jack Hughes', 'Kirill Kaprizov']} != {'Trou Trou Train': ['Mackenzie Blackwood', 'Radko Gudas', 'Jack Hughes', 'Kirill Kaprizov', 'Leon Draisaitl']}
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED tests/test_keeper_collect.py::test_live_markup_draft_matches_staged_keeper_board
1 failed in 0.11s
```

## Drop parsed trade

```text
F                                                                        [100%]
=================================== FAILURES ===================================
________________ test_live_markup_trade_sample_and_fail_closed _________________
tests/test_keeper_collect.py:28: in test_live_markup_trade_sample_and_fail_closed
    assert [{k: t[k] for k in ("season", "league_id", "date", "teams")} for t in result] == [
E   AssertionError: assert [{'date': 'Fe...High Life'}]}] == [{'date': 'Ma...rain'}]}, ...]
E     
E     At index 0 diff: {'season': 2024, 'league_id': 17419, 'date': 'Feb 28, 4:10 am', 'teams': [{'team': 'JeanClaud VanDangles', 'received': ['Timo Meier (NJ - LW,RW)', 'Macklin Celebrini (SJ - C)', 'Round 1', 'Round 4 (traded from Miller’s High Life)']}, {'team': 'Trou Trou Train', 'received': ['Leon Draisaitl (EDM - C,LW)', 'Jack Eichel (VGK - C)', 'Round 5', 'Round 7']}]} != {'season': 2024, 'league_id': 17419, 'date': 'Mar 1, 4:10 am', 'teams': [{'team': 'Julie the Cat', 'received': ['Jeremy Swayman (BOS - G)', 'Round 3']}, {'team': 'The Bad Place', 'received': ['Artturi...
E     
E     ...Full output truncated (3 lines hidden), use '-vv' to show
=========================== short test summary info ============================
FAILED tests/test_keeper_collect.py::test_live_markup_trade_sample_and_fail_closed
1 failed in 0.07s
```

## Remove formula copies for inserts

```text
F                                                                        [100%]
=================================== FAILURES ===================================
_____________________ test_expand_and_zero_keeper_template _____________________
tests/test_keeper_sheet.py:99: in test_expand_and_zero_keeper_template
    assert {
E   assert set() == {0, 1, 3, 5}
E     
E     Extra items in the right set:
E     0
E     1
E     3
E     5
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED tests/test_keeper_sheet.py::test_expand_and_zero_keeper_template - ass...
1 failed in 0.02s
```
