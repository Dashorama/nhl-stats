# Verification evidence

Baseline origin/main: 59 passed, 3 failed (`sqlite3.OperationalError: no such table: players`).
The existing generator test fixture now creates its required players table and mocks
LLM narration, so tests do not depend on an external narrator. No generator production
code changed. Final full suite: `107 passed, 2 warnings in 4.35s`. Existing integration
marker warnings remain. Scoped Ruff and strict mypy passed. Full-repo Ruff (69 errors) and mypy
(139 errors) match independent origin/main baseline runs exactly; this feature
adds no lint/type errors. `pip wheel . --no-deps` built nhl-stats.

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
worktree, tested, and reverted. All nineteen produced failures. Green after restoring
all mutations: `45 keeper tests passed; full suite 107 passed in 4.35s` (keeper tests). The baseline generator fixture
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
1 failed in 0.02s
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
src/keeper/core.py:173: in scanTrades
    raise ValueError(f"trade ownership conflict for {player}")
E   ValueError: trade ownership conflict for Player One
=========================== short test summary info ============================
FAILED tests/test_keeper_core.py::test_chained_trades_chronology_one_time_and_watermark
1 failed in 0.02s
```

## Remove validation raises

```text
.F.FFFFFFFFFF..FF.FFFFFF.FF.FFFFF                                        [100%]
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
src/keeper/core.py:55: in reconcile
    old = from_snapshot(snapshot)
src/keeper/core.py:46: in from_snapshot
    if any((str(r[6]) not in ('0', '1') for r in data)):
src/keeper/core.py:46: in <genexpr>
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
src/keeper/core.py:125: in scanTrades
    if team_key(row.team) not in (team_key(source), team_key(target)):
src/keeper/core.py:25: in team_key
    key = normalize(name)
src/keeper/core.py:20: in normalize
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
src/keeper/sheet.py:33: in make_plan
    if len(row) < 7 or len(formulas[i]) < 7:
E   IndexError: list index out of range
_______________ test_bad_sheet_plan_rejected[partial-incomplete] _______________
tests/test_keeper_sheet.py:129: in test_bad_sheet_plan_rejected
    make_plan(before, rows)
src/keeper/sheet.py:35: in make_plan
    if not all((isinstance(formulas[i][c], str) and formulas[i][c].startswith('=') for c in FORMULA_COLUMNS)):
src/keeper/sheet.py:35: in <genexpr>
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
_____________ test_sheets_helper_paths_owner_checks_and_ui_errors ______________
tests/test_keeper_sheet.py:176: in test_sheets_helper_paths_owner_checks_and_ui_errors
    with pytest.raises(ValueError, match="UI formula"):
E   Failed: DID NOT RAISE <class 'ValueError'>
______________ test_live_markup_draft_matches_staged_keeper_board ______________
tests/test_keeper_collect.py:18: in test_live_markup_draft_matches_staged_keeper_board
    with pytest.raises(ValueError, match="season"):
E   Failed: DID NOT RAISE <class 'ValueError'>
________________ test_live_markup_trade_sample_and_fail_closed _________________
tests/test_keeper_collect.py:32: in test_live_markup_trade_sample_and_fail_closed
    parse_trades("<html>Login required</html>", 2024, 17419)
src/keeper/collect.py:27: in parse_trades
    rows = table.select('tr')
E   AttributeError: 'NoneType' object has no attribute 'select'
_____ test_changed_keeper_markup[class="name"-class="renamed"-keeper row] ______
tests/test_keeper_collect.py:64: in test_changed_keeper_markup
    parse_draft(html, 2025)
src/keeper/collect.py:17: in parse_draft
    result.setdefault(team.get_text(strip=True), []).append({'player': player.get_text(strip=True), 'keeper': True})
E   AttributeError: 'NoneType' object has no attribute 'get_text'
__________ test_changed_trade_markup[F-timestamp-removed-owner/date] ___________
tests/test_keeper_collect.py:78: in test_changed_trade_markup
    parse_trades(html, 2024, 17419)
src/keeper/collect.py:53: in parse_trades
    dates.append(stamp.get_text(strip=True))
E   AttributeError: 'NoneType' object has no attribute 'get_text'
____________ test_changed_trade_markup[Round 3-Mystery asset-asset] ____________
tests/test_keeper_collect.py:77: in test_changed_trade_markup
    with pytest.raises(ValueError, match=message):
E   Failed: DID NOT RAISE <class 'ValueError'>
____ test_changed_trade_markup[Mar 1, 4:10 am-Mar 2, 4:10 am-pairing date] _____
tests/test_keeper_collect.py:77: in test_changed_trade_markup
    with pytest.raises(ValueError, match=message):
E   Failed: DID NOT RAISE <class 'ValueError'>
__________________________ test_incomplete_trade_pair __________________________
tests/test_keeper_collect.py:86: in test_incomplete_trade_pair
    with pytest.raises(ValueError, match="incomplete trade"):
E   Failed: DID NOT RAISE <class 'ValueError'>
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
FAILED tests/test_keeper_sheet.py::test_sheets_helper_paths_owner_checks_and_ui_errors
FAILED tests/test_keeper_collect.py::test_live_markup_draft_matches_staged_keeper_board
FAILED tests/test_keeper_collect.py::test_live_markup_trade_sample_and_fail_closed
FAILED tests/test_keeper_collect.py::test_changed_keeper_markup[class="name"-class="renamed"-keeper row]
FAILED tests/test_keeper_collect.py::test_changed_trade_markup[F-timestamp-removed-owner/date]
FAILED tests/test_keeper_collect.py::test_changed_trade_markup[Round 3-Mystery asset-asset]
FAILED tests/test_keeper_collect.py::test_changed_trade_markup[Mar 1, 4:10 am-Mar 2, 4:10 am-pairing date]
FAILED tests/test_keeper_collect.py::test_incomplete_trade_pair - Failed: DID...
26 failed, 7 passed in 0.42s
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
E    +  where [[{'deleteDimension': {'range': {'dimension': 'ROWS', 'endIndex': 67, 'sheetId': 0, 'startIndex': 66}}}, {'deleteDimen...': [...]}, {'values': [...]}, {'values': [...]}, {'values': [...]}, {'values': [...]}, {'values': [...]}, ...]}}, ...]] = <tests.test_keeper_sheet.FakeSheet object at 0x78d7bd02a7a0>.writes
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
E    +    where [[{'deleteDimension': {'range': {'dimension': 'ROWS', 'endIndex': 51, 'sheetId': 0, 'startIndex': 49}}}, {'deleteDimen...alues': [...]}, {'values': [...]}, {'values': [...]}, {'values': [...]}, {'values': [...]}, {'values': [...]}, ...]}}]] = <tests.test_keeper_sheet.FakeSheet object at 0x72cdc962b190>.writes
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
1 failed in 0.10s
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

## Browser guards incorrectly exit successfully

```text
.FFFF.FF.                                                                [100%]
=================================== FAILURES ===================================
_ test_transport_refuses_unverified_collection[scenario1-reconcile-2000-5003-not available] _
tests/test_keeper_transport.py:70: in test_transport_refuses_unverified_collection
    assert result.returncode != 0
E   AssertionError: assert 0 != 0
E    +  where 0 = CompletedProcess(args=['node', '/home/david/nhl-stats/.worktrees/feature/M-keeper-reconcile-tool/src/keeper/collect.mj...'2000', '/tmp/pytest-of-david/pytest-274/test_transport_refuses_unverif1', '5003'], returncode=0, stdout='', stderr='').returncode
_ test_transport_refuses_unverified_collection[scenario2-scan-trades-2024-5003-archived --league-id] _
tests/test_keeper_transport.py:70: in test_transport_refuses_unverified_collection
    assert result.returncode != 0
E   AssertionError: assert 0 != 0
E    +  where 0 = CompletedProcess(args=['node', '/home/david/nhl-stats/.worktrees/feature/M-keeper-reconcile-tool/src/keeper/collect.mj...'2024', '/tmp/pytest-of-david/pytest-274/test_transport_refuses_unverif2', '5003'], returncode=0, stdout='', stderr='').returncode
_ test_transport_refuses_unverified_collection[scenario3-scan-trades-2026-5003-pagination target] _
tests/test_keeper_transport.py:70: in test_transport_refuses_unverified_collection
    assert result.returncode != 0
E   AssertionError: assert 0 != 0
E    +  where 0 = CompletedProcess(args=['node', '/home/david/nhl-stats/.worktrees/feature/M-keeper-reconcile-tool/src/keeper/collect.mj...'2026', '/tmp/pytest-of-david/pytest-274/test_transport_refuses_unverif3', '5003'], returncode=0, stdout='', stderr='').returncode
_ test_transport_refuses_unverified_collection[scenario4-scan-trades-2026-5003-ambiguous pagination] _
tests/test_keeper_transport.py:70: in test_transport_refuses_unverified_collection
    assert result.returncode != 0
E   AssertionError: assert 0 != 0
E    +  where 0 = CompletedProcess(args=['node', '/home/david/nhl-stats/.worktrees/feature/M-keeper-reconcile-tool/src/keeper/collect.mj...'2026', '/tmp/pytest-of-david/pytest-274/test_transport_refuses_unverif4', '5003'], returncode=0, stdout='', stderr='').returncode
_ test_transport_refuses_unverified_collection[scenario6-scan-trades-2026-5003-pagination incomplete] _
tests/test_keeper_transport.py:70: in test_transport_refuses_unverified_collection
    assert result.returncode != 0
E   AssertionError: assert 0 != 0
E    +  where 0 = CompletedProcess(args=['node', '/home/david/nhl-stats/.worktrees/feature/M-keeper-reconcile-tool/src/keeper/collect.mj...'2026', '/tmp/pytest-of-david/pytest-274/test_transport_refuses_unverif6', '5003'], returncode=0, stdout='', stderr='').returncode
_ test_transport_refuses_unverified_collection[scenario7-bad-command-2025-5003-invalid collector arguments] _
tests/test_keeper_transport.py:70: in test_transport_refuses_unverified_collection
    assert result.returncode != 0
E   AssertionError: assert 0 != 0
E    +  where 0 = CompletedProcess(args=['node', '/home/david/nhl-stats/.worktrees/feature/M-keeper-reconcile-tool/src/keeper/collect.mj...'2025', '/tmp/pytest-of-david/pytest-274/test_transport_refuses_unverif7', '5003'], returncode=0, stdout='', stderr='').returncode
=========================== short test summary info ============================
FAILED tests/test_keeper_transport.py::test_transport_refuses_unverified_collection[scenario1-reconcile-2000-5003-not available]
FAILED tests/test_keeper_transport.py::test_transport_refuses_unverified_collection[scenario2-scan-trades-2024-5003-archived --league-id]
FAILED tests/test_keeper_transport.py::test_transport_refuses_unverified_collection[scenario3-scan-trades-2026-5003-pagination target]
FAILED tests/test_keeper_transport.py::test_transport_refuses_unverified_collection[scenario4-scan-trades-2026-5003-ambiguous pagination]
FAILED tests/test_keeper_transport.py::test_transport_refuses_unverified_collection[scenario6-scan-trades-2026-5003-pagination incomplete]
FAILED tests/test_keeper_transport.py::test_transport_refuses_unverified_collection[scenario7-bad-command-2025-5003-invalid collector arguments]
6 failed, 3 passed in 0.25s
```

## Browser fails to close profile

```text
FFFFFFF.F                                                                [100%]
=================================== FAILURES ===================================
_ test_transport_refuses_unverified_collection[scenario0-reconcile-2025-5003-season metadata] _
tests/test_keeper_transport.py:74: in test_transport_refuses_unverified_collection
    assert closed.exists()
E   AssertionError: assert False
E    +  where False = exists()
E    +    where exists = PosixPath('/tmp/pytest-of-david/pytest-275/test_transport_refuses_unverif0/closed').exists
_ test_transport_refuses_unverified_collection[scenario1-reconcile-2000-5003-not available] _
tests/test_keeper_transport.py:74: in test_transport_refuses_unverified_collection
    assert closed.exists()
E   AssertionError: assert False
E    +  where False = exists()
E    +    where exists = PosixPath('/tmp/pytest-of-david/pytest-275/test_transport_refuses_unverif1/closed').exists
_ test_transport_refuses_unverified_collection[scenario2-scan-trades-2024-5003-archived --league-id] _
tests/test_keeper_transport.py:74: in test_transport_refuses_unverified_collection
    assert closed.exists()
E   AssertionError: assert False
E    +  where False = exists()
E    +    where exists = PosixPath('/tmp/pytest-of-david/pytest-275/test_transport_refuses_unverif2/closed').exists
_ test_transport_refuses_unverified_collection[scenario3-scan-trades-2026-5003-pagination target] _
tests/test_keeper_transport.py:74: in test_transport_refuses_unverified_collection
    assert closed.exists()
E   AssertionError: assert False
E    +  where False = exists()
E    +    where exists = PosixPath('/tmp/pytest-of-david/pytest-275/test_transport_refuses_unverif3/closed').exists
_ test_transport_refuses_unverified_collection[scenario4-scan-trades-2026-5003-ambiguous pagination] _
tests/test_keeper_transport.py:74: in test_transport_refuses_unverified_collection
    assert closed.exists()
E   AssertionError: assert False
E    +  where False = exists()
E    +    where exists = PosixPath('/tmp/pytest-of-david/pytest-275/test_transport_refuses_unverif4/closed').exists
_ test_transport_refuses_unverified_collection[scenario5-scan-trades-2026-5003-redirect] _
tests/test_keeper_transport.py:74: in test_transport_refuses_unverified_collection
    assert closed.exists()
E   AssertionError: assert False
E    +  where False = exists()
E    +    where exists = PosixPath('/tmp/pytest-of-david/pytest-275/test_transport_refuses_unverif5/closed').exists
_ test_transport_refuses_unverified_collection[scenario6-scan-trades-2026-5003-pagination incomplete] _
tests/test_keeper_transport.py:74: in test_transport_refuses_unverified_collection
    assert closed.exists()
E   AssertionError: assert False
E    +  where False = exists()
E    +    where exists = PosixPath('/tmp/pytest-of-david/pytest-275/test_transport_refuses_unverif6/closed').exists
___________ test_transport_returns_captured_page_and_closes_profile ____________
tests/test_keeper_transport.py:111: in test_transport_returns_captured_page_and_closes_profile
    assert closed.read_text() == "closed"
/usr/lib/python3.10/pathlib.py:1134: in read_text
    with self.open(mode='r', encoding=encoding, errors=errors) as f:
/usr/lib/python3.10/pathlib.py:1119: in open
    return self._accessor.open(self, mode, buffering, encoding, errors,
E   FileNotFoundError: [Errno 2] No such file or directory: '/tmp/pytest-of-david/pytest-275/test_transport_returns_capture0/closed'
=========================== short test summary info ============================
FAILED tests/test_keeper_transport.py::test_transport_refuses_unverified_collection[scenario0-reconcile-2025-5003-season metadata]
FAILED tests/test_keeper_transport.py::test_transport_refuses_unverified_collection[scenario1-reconcile-2000-5003-not available]
FAILED tests/test_keeper_transport.py::test_transport_refuses_unverified_collection[scenario2-scan-trades-2024-5003-archived --league-id]
FAILED tests/test_keeper_transport.py::test_transport_refuses_unverified_collection[scenario3-scan-trades-2026-5003-pagination target]
FAILED tests/test_keeper_transport.py::test_transport_refuses_unverified_collection[scenario4-scan-trades-2026-5003-ambiguous pagination]
FAILED tests/test_keeper_transport.py::test_transport_refuses_unverified_collection[scenario5-scan-trades-2026-5003-redirect]
FAILED tests/test_keeper_transport.py::test_transport_refuses_unverified_collection[scenario6-scan-trades-2026-5003-pagination incomplete]
FAILED tests/test_keeper_transport.py::test_transport_returns_captured_page_and_closes_profile
8 failed, 1 passed in 0.28s
```

## Ignore explicit empty transaction page

```text
F                                                                        [100%]
=================================== FAILURES ===================================
______________________ test_empty_live_transaction_table _______________________
tests/test_keeper_collect.py:45: in test_empty_live_transaction_table
    parse_trades(
src/keeper/collect.py:35: in parse_trades
    raise ValueError("empty page unsupported")
E   ValueError: empty page unsupported
=========================== short test summary info ============================
FAILED tests/test_keeper_collect.py::test_empty_live_transaction_table - Valu...
1 failed in 0.06s
```

## Fingerprint includes mutable NHL labels again

```text
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_trade_fingerprint_survives_current_nhl_position_labels __________
tests/test_keeper_core.py:176: in test_trade_fingerprint_survives_current_nhl_position_labels
    assert trade_key(updated) == trade_key(trade)
E   AssertionError: assert '31df662cc741...ebe569134f551' == 'e8d798b748d2...a0c14af1b057c'
E     
E     - e8d798b748d21561aff1a9178b4420301d0cd916f243f3446b1a0c14af1b057c
E     + 31df662cc741e21abf237b0e0848236dd9a7d67720014af7dd2ebe569134f551
=========================== short test summary info ============================
FAILED tests/test_keeper_core.py::test_trade_fingerprint_survives_current_nhl_position_labels
1 failed in 0.02s
```

## Write before backup

```text
F                                                                        [100%]
=================================== FAILURES ===================================
__________________ test_backup_is_durable_before_first_write ___________________
tests/test_keeper_sheet.py:208: in test_backup_is_durable_before_first_write
    apply_plan(api, TEST_SHEET, before, plan, tmp_path, apply=True)
src/keeper/sheet.py:204: in apply_plan
    api.write(plan["requests"])
tests/test_keeper_sheet.py:204: in check_backup
    assert json.loads(next(tmp_path.glob("*.json")).read_text()) == before
E   StopIteration
=========================== short test summary info ============================
FAILED tests/test_keeper_sheet.py::test_backup_is_durable_before_first_write
1 failed in 0.03s
```

## Ignore backup fsync

```text
F                                                                        [100%]
=================================== FAILURES ===================================
__________________ test_backup_is_durable_before_first_write ___________________
tests/test_keeper_sheet.py:215: in test_backup_is_durable_before_first_write
    with pytest.raises(OSError, match="backup fsync"):
E   Failed: DID NOT RAISE <class 'OSError'>
=========================== short test summary info ============================
FAILED tests/test_keeper_sheet.py::test_backup_is_durable_before_first_write
1 failed in 0.03s
```

## Disable CLI argument safety errors

```text
F                                                                        [100%]
=================================== FAILURES ===================================
________________ test_cli_rejects_missing_source_and_live_apply ________________
tests/test_keeper_cli.py:91: in test_cli_rejects_missing_source_and_live_apply
    cli.main(["reconcile", "--season", "2025", "--state-dir", str(tmp_path)])
src/keeper/cli.py:58: in main
    output = subprocess.run(
/usr/lib/python3.10/subprocess.py:526: in run
    raise CalledProcessError(retcode, process.args,
E   subprocess.CalledProcessError: Command '['node', '/home/david/nhl-stats/.worktrees/feature/M-keeper-reconcile-tool/src/keeper/collect.mjs', 'reconcile', '2025', 'None', '5003']' returned non-zero exit status 1.
=========================== short test summary info ============================
FAILED tests/test_keeper_cli.py::test_cli_rejects_missing_source_and_live_apply
1 failed in 0.11s
```

## Additional live integration

The complete `--profile` CLI scrape-to-sheet dry-run succeeded with zero changed
teams. A synthetic 2026 keeper trade then moved Sam Reinhart from David's block
to Steven's block, setting Traded=1 and resizing both blocks. All formula/owner/UI
checks passed. Restoration to original rights also passed; the final formula
snapshot matched the original exactly. Backups:
`/tmp/keeper-integration/backups/raw-data-20260906T123059.249246Z.json` and
`/tmp/keeper-integration/backups/raw-data-20260906T123101.619702Z.json`.

Production activation and weekly scheduler follow-up: GitHub issue #1.
`bd onboard` could not run (`bd: command not found`); tracking is on GitHub.

## Sonnet review fixes

Independent Sonnet review of b8592a5 completed: 1 Critical, 2 Important,
2 Minor, 1 Info. C1 (empty team cannot acquire keeper) is fixed by passing the
complete team list from the sheet to the pure scanner. I1 (uncovered pre-write
crash retry and intervening-edit conflict) now has behavioral regression tests.
I2 (uncovered real adapter/CLI guards) now has a stub-helper test that instantiates
Sheets, plus independent mutations of each guard. M1 has independent formula-offset
assertions. M2's documentation now accurately calls the order exception inline
compatibility code. N1 is covered by nine offline Node-entrypoint tests.

Each fix's proof follows. Restored keeper suite: `50 passed in 0.84s`.

## C1 lose empty-team identity

```text
FF                                                                       [100%]
=================================== FAILURES ===================================
________________ test_team_with_zero_keepers_can_receive_keeper ________________
tests/test_keeper_core.py:190: in test_team_with_zero_keepers_can_receive_keeper
    result, _ = scanTrades(rows, [trade], season=2026, known_teams=["A", "B"])
src/keeper/core.py:169: in scanTrades
    raise ValueError(f"unknown acquiring team: {side['team']}")
E   ValueError: unknown acquiring team: B
____________________ test_cli_preserves_empty_team_identity ____________________
tests/test_keeper_cli.py:131: in test_cli_preserves_empty_team_identity
    cli.main(
src/keeper/cli.py:114: in main
    rows, state = scanTrades(
src/keeper/core.py:169: in scanTrades
    raise ValueError(f"unknown acquiring team: {side['team']}")
E   ValueError: unknown acquiring team: Hanstuetzle and Guentzel
=========================== short test summary info ============================
FAILED tests/test_keeper_core.py::test_team_with_zero_keepers_can_receive_keeper
FAILED tests/test_keeper_cli.py::test_cli_preserves_empty_team_identity - Val...
2 failed in 0.09s
```

## I1 falsely declare journal recovered

```text
FF                                                                       [100%]
=================================== FAILURES ===================================
__________________ test_pending_retry_writes_unchanged_source __________________
tests/test_keeper_cli.py:181: in test_pending_retry_writes_unchanged_source
    assert len(api.writes) == 1
E   assert 0 == 1
E    +  where 0 = len([])
E    +    where [] = <tests.test_keeper_sheet.FakeSheet object at 0x74c1ba934280>.writes
______________ test_pending_conflict_retains_journal_and_backups _______________
tests/test_keeper_cli.py:194: in test_pending_conflict_retains_journal_and_backups
    with pytest.raises(ValueError, match="conflicts"):
E   Failed: DID NOT RAISE <class 'ValueError'>
=========================== short test summary info ============================
FAILED tests/test_keeper_cli.py::test_pending_retry_writes_unchanged_source
FAILED tests/test_keeper_cli.py::test_pending_conflict_retains_journal_and_backups
2 failed in 0.12s
```

## I2 disable Raw Data sheetId must be 0

```text
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_sheets_helper_paths_owner_checks_and_ui_errors ______________
tests/test_keeper_sheet.py:190: in test_sheets_helper_paths_owner_checks_and_ui_errors
    with pytest.raises(ValueError, match="sheetId"):
E   Failed: DID NOT RAISE <class 'ValueError'>
=========================== short test summary info ============================
FAILED tests/test_keeper_sheet.py::test_sheets_helper_paths_owner_checks_and_ui_errors
1 failed in 0.02s
```

## I2 disable owner blocks do not match List Of Teams And Owners

```text
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_sheets_helper_paths_owner_checks_and_ui_errors ______________
tests/test_keeper_sheet.py:181: in test_sheets_helper_paths_owner_checks_and_ui_errors
    api.read()
src/keeper/sheet.py:254: in read
    owner_index = owners.index([row[0], row[1]]) + 2
E   ValueError: ['Tage Against The Machine', 'David Erner'] is not in list

During handling of the above exception, another exception occurred:
tests/test_keeper_sheet.py:180: in test_sheets_helper_paths_owner_checks_and_ui_errors
    with pytest.raises(ValueError, match="owner blocks"):
E   AssertionError: Regex pattern did not match.
E     Expected regex: 'owner blocks'
E     Actual message: "['Tage Against The Machine', 'David Erner'] is not in list"
=========================== short test summary info ============================
FAILED tests/test_keeper_sheet.py::test_sheets_helper_paths_owner_checks_and_ui_errors
1 failed in 0.03s
```

## I2 disable owner formula points to wrong owner cell

```text
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_sheets_helper_paths_owner_checks_and_ui_errors ______________
tests/test_keeper_sheet.py:184: in test_sheets_helper_paths_owner_checks_and_ui_errors
    with pytest.raises(ValueError, match="wrong owner cell"):
E   Failed: DID NOT RAISE <class 'ValueError'>
=========================== short test summary info ============================
FAILED tests/test_keeper_sheet.py::test_sheets_helper_paths_owner_checks_and_ui_errors
1 failed in 0.02s
```

## I2 disable UI formula error verification failed

```text
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_sheets_helper_paths_owner_checks_and_ui_errors ______________
tests/test_keeper_sheet.py:176: in test_sheets_helper_paths_owner_checks_and_ui_errors
    with pytest.raises(ValueError, match="UI formula"):
E   Failed: DID NOT RAISE <class 'ValueError'>
=========================== short test summary info ============================
FAILED tests/test_keeper_sheet.py::test_sheets_helper_paths_owner_checks_and_ui_errors
1 failed in 0.02s
```

## I2 remove adapter live-sheet restriction

```text
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_sheets_helper_paths_owner_checks_and_ui_errors ______________
tests/test_keeper_sheet.py:187: in test_sheets_helper_paths_owner_checks_and_ui_errors
    with pytest.raises(ValueError, match="TEST COPY"):
E   Failed: DID NOT RAISE <class 'ValueError'>
=========================== short test summary info ============================
FAILED tests/test_keeper_sheet.py::test_sheets_helper_paths_owner_checks_and_ui_errors
1 failed in 0.02s
```

## M1 incorrect formula offsets

```text
F                                                                        [100%]
=================================== FAILURES ===================================
_______________ test_formula_offsets_match_sheet_row_references ________________
tests/test_keeper_sheet.py:223: in test_formula_offsets_match_sheet_row_references
    assert shifted("=F10-$B$1-1", -3) == "=F7-$B$1-1"
E   AssertionError: assert '=F10-$B$1-1' == '=F7-$B$1-1'
E     
E     - =F7-$B$1-1
E     ?   ^
E     + =F10-$B$1-1
E     ?   ^^
=========================== short test summary info ============================
FAILED tests/test_keeper_sheet.py::test_formula_offsets_match_sheet_row_references
1 failed in 0.02s
```
