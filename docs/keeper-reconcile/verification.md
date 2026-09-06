# Keeper tool verification

## Final checks

- `python3 -m pytest tests/ -q`: **143 passed**, 2 existing integration-marker warnings.
- Clean-bytecode run with `PYTHONDONTWRITEBYTECODE=1` and a fresh
  `PYTHONPYCACHEPREFIX`: **143 passed, 19 warnings in 6.94s**. The additional
  warnings are existing `stringcase`/`rauth` invalid escape sequences revealed by recompilation.
- `python3 -m ruff check src/keeper tests/test_keeper*.py`: all checks passed.
- `python3 -m mypy src/keeper --follow-imports=silent`: success, 5 source files.
- `python3 -m pip wheel . --no-deps -w /tmp/keeper-dist`: built successfully.
  Every keeper `.py`/`.mjs` in that wheel was byte-compared to the final source.
- `node --check src/keeper/collect.mjs`: passed.

Independent origin/main baseline (`0f6e758`) reproduced **59 passed, 3 failed**
with `sqlite3.OperationalError: no such table: players`. The existing generator
fixture now creates that required table and mocks external LLM narration; production
generator code is unchanged. Full-repo Ruff remains at 69 errors and strict mypy
at 139 errors in 7 files, exactly matching independent baseline checks. Issue #2
tracks that pre-existing debt; this change adds no lint/type errors.

## Integration evidence

- Staged reconcile matches all 60 ordered team/player/FYK/Traded records exactly.
- Live authenticated 2025 draft scrape matched all 60 tagged keeper names. The
  complete scrape-to-sheet CLI dry-run returned zero changed teams on the already
  reconciled TEST COPY.
- Final live 2024 archive collector returned seven trades equal to the seven
  corresponding supplied records, with collection completeness confirmed against
  the supported page contract. The other five sample records are from older seasons.
- Live markup investigation confirmed **duplicated `Next 25` links**, using
  `ul.pagingnavlist`, `li.last`, `count=25`, and disabled `F-shade` controls.
- Real Chromium with intercepted local fixture responses (fresh unauthenticated
  temporary profile, no Yahoo session) collected **2 pages / 26 trades**. The two
  committed pages use the captured pager structure and synthetic dated copies of
  a captured trade pair. The real-DOM smoke was rerun after independently breaking
  its pager selector and trade-count selector; both went red and restoration passed
  (`1 passed in 15.96s`). Local replay harness: `/tmp/test_keeper_browser_smoke.py`
  and `/tmp/keeper-real-browser-shim.mjs`.
- TEST COPY apply: inserted a synthetic nonkeeper into the first block, then
  reconciled it away. Both backed-up atomic batches passed every formula/literal,
  owner-alignment, and UI-error check. Backups are under `/tmp/keeper-integration/backups/`:
  `raw-data-20260906T122121.413321Z.json` and `raw-data-20260906T122123.730140Z.json`.
- TEST COPY trade round trip: moved Sam Reinhart from David's block to Steven's,
  set Traded=1, and verified the shrink/grow and all formulas. Restored the original
  rights; final formula snapshot matched the original exactly. Backups:
  `raw-data-20260906T123059.249246Z.json` and `raw-data-20260906T123101.619702Z.json`.
- No live-sheet writes. Native grid formatting/validation was inspected through
  Sheets API; no browser-rendered Google Sheet visual check is claimed.

## internal_review

Independent parallel Sonnet (`claude-sonnet-5`) and Opus (`claude-opus-5`) reviews
inspected pushed head `b8592a5` against `0f6e758` in separate disposable clones,
using branch refs and offline experiments. No live checkout was modified.

sonnet_summary: 1 Critical and 2 Important found; empty-team acquisition fixed,
unapplied/conflicting journal branches tested, real adapter and CLI guards tested
and individually mutated. Both Minor findings (formula offsets and compatibility
wording) were also addressed; offline Node tests address its transport observation.

opus_summary: 1 Critical and 3 Important found; exhaustive individual guard proof
replaces the earlier incomplete batch evidence; zero-keeper team identity is fixed;
real Yahoo structural pagination, duplicate controls, terminal evidence, page counts
and overlap rejection are implemented; all eight Sheets error values are checked.
Opus independently simulated four request-plan shapes with zero formula mismatches
and corroborated the test-copy backup artifacts. All blocking findings have fixes
and red/green evidence below; no author waiver or human deferral was used.

blockers_resolved: true
fix_commits: [5340930, 6c146c6, 9ad517c]
test_commits: [8e19739, 314f3c3, edc14d1, 9c43145, 72e27b5]

Non-blocking Opus observations also fixed: stable fingerprints across side-order
and NHL-label changes; leap-day parsing; physical empty-template preservation;
meaningful placeholder year. Remaining operational limits are documented in README
and tracked in issue #1: timeout process cleanup before unattended production,
friendlier held-lock/missing-tab diagnostics, historical fixture season selection,
and David's cross-team FYK ruling. Split trade pairs across pages fail closed under
the supported complete-pair page contract. The draft collector is deliberately
single-league; `--league-id` selects archived trade collection only. Full UI work and
production activation still need David's greenlight. One-time versus cumulative
trade bonus was surfaced via Nexus; the dispatched one-time default is implemented.

`bd onboard` was unavailable (`bd: command not found`); follow-ups are in GitHub
issues #1 and #2. Work stayed in the requested isolated feature worktree.

## mutation_proof

Tests were committed before implementation (initial seven test commits precede
`b8592a5`; subsequent bug regressions also have dedicated test commits). Initial
red runs included missing core/adapter/parser modules, the missing recovery writer,
seven structural-pagination failures, three missing error-code failures, and the
leap-day/placeholder regressions. Ground-truth fixtures are unchanged.

The earlier batch-only evidence was replaced after Opus exposed mutual masking.
**106 individual mutation records follow; zero survivors.** Each guarded operation
is removed or changed to the wrong behavior; thrown browser errors are independently
changed to successful exit. Every anchor was checked, each source restored, and
Python mutations used a fresh bytecode-cache prefix plus disabled bytecode writes
so same-second `.pyc` reuse could not produce false results. Separate mutations
cover each real Sheets adapter guard and the two real DOM selectors. Exact error
messages distinguish neighboring guards; formula read-back cases retain the same
owner geometry so owner validation cannot mask formula validation.

**Green for every record after restoring all sources:**

```text
143 passed, 19 warnings in 6.94s
```

The records below paste actual failing-run output and name the tests that went red.
The line numbers identify source locations when mutated; later formatting may move them.

### src/keeper/core.py:51 — raise ValueError(f'ambiguous player: {name}')

```text
..................F...........................................           [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_core.py::test_duplicate_alias_candidates_are_ambiguous
1 failed, 61 passed in 0.99s
```

### src/keeper/core.py:58 — raise ValueError(f'ambiguous player: {name}')

```text
........F.....................................................           [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_core.py::test_matching_ambiguity_is_an_error - Faile...
1 failed, 61 passed in 0.97s
```

### src/keeper/core.py:65 — raise ValueError('incomplete snapshot row')

```text
......F.......................................................           [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_core.py::test_reconcile_rejects_corrupt_inputs[malformed_sheet-snapshot]
1 failed, 61 passed in 0.96s
```

### src/keeper/core.py:67 — raise ValueError('Traded must be 0 or 1')

```text
.......F......................................................           [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_core.py::test_reconcile_rejects_corrupt_inputs[invalid_flag-Traded]
1 failed, 61 passed in 0.98s
```

### src/keeper/core.py:71 — raise ValueError('duplicate keeper on sheet')

```text
.....F........................................................           [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_core.py::test_reconcile_rejects_corrupt_inputs[duplicate_sheet-duplicate]
1 failed, 61 passed in 0.97s
```

### src/keeper/core.py:86 — raise ValueError('draft and sheet team sets differ')

```text
.F............................................................           [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_core.py::test_reconcile_tag_count_and_unknown_team
1 failed, 61 passed in 1.03s
```

### src/keeper/core.py:88 — raise ValueError('unexpected keeper count; incomplete draft?')

```text
.F............................................................           [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_core.py::test_reconcile_tag_count_and_unknown_team
1 failed, 61 passed in 0.97s
```

### src/keeper/core.py:91 — raise ValueError('duplicate drafted player')

```text
....F.........................................................           [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_core.py::test_reconcile_rejects_corrupt_inputs[duplicate_board-duplicate]
1 failed, 61 passed in 0.97s
```

### src/keeper/core.py:146 — raise ValueError('watermark season mismatch')

```text
...F..........................................................           [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_core.py::test_chained_trades_chronology_one_time_and_watermark
1 failed, 61 passed in 0.98s
```

### src/keeper/core.py:148 — raise ValueError('mixed league trade input')

```text
............F.................................................           [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_core.py::test_trade_conflicts_fail_closed[league-league]
1 failed, 61 passed in 0.98s
```

### src/keeper/core.py:161 — raise ValueError('trade must contain two teams')

```text
.........F....................................................           [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_core.py::test_trade_conflicts_fail_closed[sides-two teams]
1 failed, 61 passed in 0.97s
```

### src/keeper/core.py:172 — raise ValueError(f"unknown acquiring team: {side['team']}")

```text
..........F...................................................           [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_core.py::test_trade_conflicts_fail_closed[unknown-unknown acquiring]
1 failed, 61 passed in 0.98s
```

### src/keeper/core.py:177 — raise ValueError(f'trade ownership conflict for {player}')

```text
...........F..................................................           [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_core.py::test_trade_conflicts_fail_closed[owner-ownership conflict]
1 failed, 61 passed in 0.99s
```

### src/keeper/sheet.py:49 — raise ValueError('invalid snapshot shape')

```text
.......................F......................................           [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_sheet.py::test_bad_sheet_plan_rejected[length-snapshot]
1 failed, 61 passed in 0.97s
```

### src/keeper/sheet.py:53 — raise ValueError('incomplete sheet row')

```text
........................F.....................................           [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_sheet.py::test_bad_sheet_plan_rejected[partial-incomplete]
1 failed, 61 passed in 0.97s
```

### src/keeper/sheet.py:58 — raise ValueError('missing formula in protected column')

```text
.....................F........................................           [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_sheet.py::test_apply_rejects_live_stale_and_bad_formulas
1 failed, 61 passed in 1.00s
```

### src/keeper/sheet.py:63 — raise ValueError('non-contiguous owner blocks')

```text
.........................F....................................           [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_sheet.py::test_bad_sheet_plan_rejected[blocks-contiguous]
1 failed, 61 passed in 0.97s
```

### src/keeper/sheet.py:65 — raise ValueError('unknown team in output')

```text
..........................F...................................           [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_sheet.py::test_bad_sheet_plan_rejected[unknown-unknown team]
1 failed, 61 passed in 0.97s
```

### src/keeper/sheet.py:177 — raise ValueError('post-write formula/value verification failed; backup retained')

```text
...................................FFFF.......................           [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_sheet.py::test_formula_value_comparison_cannot_hide_behind_owner_check[cell0]
FAILED tests/test_keeper_sheet.py::test_formula_value_comparison_cannot_hide_behind_owner_check[cell1]
FAILED tests/test_keeper_sheet.py::test_formula_value_comparison_cannot_hide_behind_owner_check[cell2]
FAILED tests/test_keeper_sheet.py::test_formula_value_comparison_cannot_hide_behind_owner_check[cell3]
4 failed, 58 passed in 0.96s
```

### src/keeper/sheet.py:181 — raise ValueError('post-write owner alignment verification failed')

```text
...........................F..................................           [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_sheet.py::test_verification_owner_and_error_cells - ...
1 failed, 61 passed in 0.97s
```

### src/keeper/sheet.py:183 — raise ValueError('post-write formula error verification failed')

```text
...........................F...FFF............................           [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_sheet.py::test_verification_owner_and_error_cells - ...
FAILED tests/test_keeper_sheet.py::test_all_sheet_formula_errors_fail_verification[#NAME?]
FAILED tests/test_keeper_sheet.py::test_all_sheet_formula_errors_fail_verification[#NUM!]
FAILED tests/test_keeper_sheet.py::test_all_sheet_formula_errors_fail_verification[#NULL!]
4 failed, 58 passed in 0.98s
```

### src/keeper/sheet.py:198 — raise ValueError('apply is restricted to the TEST COPY')

```text
.....................F........................................           [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_sheet.py::test_apply_rejects_live_stale_and_bad_formulas
1 failed, 61 passed in 1.00s
```

### src/keeper/sheet.py:200 — raise ValueError('sheet changed since planning; rerun dry-run')

```text
.....................F........................................           [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_sheet.py::test_apply_rejects_live_stale_and_bad_formulas
1 failed, 61 passed in 0.97s
```

### src/keeper/sheet.py:229 — raise ValueError('Raw Data sheetId must be 0')

```text
............................F.................................           [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_sheet.py::test_sheets_helper_paths_owner_checks_and_ui_errors
1 failed, 61 passed in 0.99s
```

### src/keeper/sheet.py:249 — raise ValueError('owner blocks do not match List Of Teams And Owners')

```text
............................F.................................           [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_sheet.py::test_sheets_helper_paths_owner_checks_and_ui_errors
1 failed, 61 passed in 0.96s
```

### src/keeper/sheet.py:253 — raise ValueError('owner formula points to wrong owner cell')

```text
............................F.................................           [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_sheet.py::test_sheets_helper_paths_owner_checks_and_ui_errors
1 failed, 61 passed in 0.96s
```

### src/keeper/sheet.py:258 — raise ValueError('apply is restricted to the TEST COPY')

```text
............................F.................................           [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_sheet.py::test_sheets_helper_paths_owner_checks_and_ui_errors
1 failed, 61 passed in 0.99s
```

### src/keeper/sheet.py:266 — raise ValueError('UI formula error verification failed')

```text
............................F..FFF............................           [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_sheet.py::test_sheets_helper_paths_owner_checks_and_ui_errors
FAILED tests/test_keeper_sheet.py::test_all_sheet_formula_errors_fail_verification[#NAME?]
FAILED tests/test_keeper_sheet.py::test_all_sheet_formula_errors_fail_verification[#NUM!]
FAILED tests/test_keeper_sheet.py::test_all_sheet_formula_errors_fail_verification[#NULL!]
4 failed, 58 passed in 0.97s
```

### src/keeper/cli.py:46 — parser.error('--apply is restricted to the TEST COPY')

```text
...........................................F..................           [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_cli.py::test_cli_rejects_missing_source_and_live_apply
1 failed, 61 passed in 0.97s
```

### src/keeper/cli.py:48 — parser.error('provide --input or --profile')

```text
...........................................F..................           [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_cli.py::test_cli_rejects_missing_source_and_live_apply
1 failed, 61 passed in 1.02s
```

### src/keeper/cli.py:92 — raise ValueError('pending apply conflicts with current sheet; inspect backup')

```text
..............................................F...............           [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_cli.py::test_pending_conflict_retains_journal_and_backups
1 failed, 61 passed in 1.00s
```

### src/keeper/collect.py:12 — raise ValueError('draft season selection not confirmed')

```text
....................................................F.........           [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_collect.py::test_live_markup_draft_matches_staged_keeper_board
1 failed, 61 passed in 0.93s
```

### src/keeper/collect.py:19 — raise ValueError('unrecognized keeper row')

```text
.......................................................F......           [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_collect.py::test_changed_keeper_markup[class="name"-class="renamed"-keeper row]
1 failed, 61 passed in 0.97s
```

### src/keeper/collect.py:24 — raise ValueError('incomplete keeper board')

```text
....................................................F.........           [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_collect.py::test_live_markup_draft_matches_staged_keeper_board
1 failed, 61 passed in 0.97s
```

### src/keeper/collect.py:32 — raise ValueError('transaction table missing; auth or markup changed')

```text
.....................................................F........           [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_collect.py::test_live_markup_trade_sample_and_fail_closed
1 failed, 61 passed in 0.97s
```

### src/keeper/collect.py:41 — raise ValueError('unrecognized trade row')

```text
.....................................................F........           [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_collect.py::test_live_markup_trade_sample_and_fail_closed
1 failed, 61 passed in 0.99s
```

### src/keeper/collect.py:47 — raise ValueError('trade owner/date missing')

```text
........................................................F.....           [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_collect.py::test_changed_trade_markup[F-timestamp-removed-owner/date]
1 failed, 61 passed in 0.97s
```

### src/keeper/collect.py:57 — raise ValueError('unrecognized trade asset')

```text
.........................................................F....           [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_collect.py::test_changed_trade_markup[Round 3-Mystery asset-asset]
1 failed, 61 passed in 0.98s
```

### src/keeper/collect.py:62 — raise ValueError('trade pairing date mismatch')

```text
..........................................................F...           [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_collect.py::test_changed_trade_markup[Mar 1, 4:10 am-Mar 2, 4:10 am-pairing date]
1 failed, 61 passed in 0.97s
```

### src/keeper/collect.py:68 — raise ValueError('incomplete trade page')

```text
...........................................................F..           [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_collect.py::test_incomplete_trade_pair - Failed: DID...
1 failed, 61 passed in 0.98s
```

### src/keeper/collect.py:78 — raise ValueError('collector scope mismatch')

```text
............................................................F.           [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_collect.py::test_collection_completeness_and_nonoverlapping_pages
1 failed, 61 passed in 0.95s
```

### src/keeper/collect.py:85 — raise ValueError('incomplete transaction collection')

```text
...................................................F........F.           [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_cli.py::test_profile_collection_is_validated_before_sheet_planning
FAILED tests/test_keeper_collect.py::test_collection_completeness_and_nonoverlapping_pages
2 failed, 60 passed in 0.96s
```

### src/keeper/collect.py:87 — raise ValueError('overlapping transaction pages')

```text
............................................................F.           [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_collect.py::test_collection_completeness_and_nonoverlapping_pages
1 failed, 61 passed in 0.97s
```

### Reconcile output equals ground-truth rows

```text
F                                                                        [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_core.py::test_reconcile_ground_truth - AssertionErro...
1 failed in 0.02s
```

### Reconcile does not mutate caller snapshot

```text
F                                                                        [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_core.py::test_reconcile_ground_truth - AssertionErro...
1 failed in 0.02s
```

### New keeper FYK uses season

```text
F                                                                        [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_core.py::test_reconcile_ground_truth - AssertionErro...
1 failed in 0.02s
```

### Retained keeper FYK and flag are preserved

```text
F                                                                        [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_core.py::test_reconcile_ground_truth - AssertionErro...
1 failed in 0.02s
```

### 2025 retained pair compatibility order

```text
F                                                                        [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_core.py::test_reconcile_ground_truth - AssertionErro...
1 failed in 0.02s
```

### One-time trade bonus

```text
FF                                                                       [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_core.py::test_trade_fixture_five_real_trades_and_replay
FAILED tests/test_keeper_core.py::test_chained_trades_chronology_one_time_and_watermark
2 failed in 0.03s
```

### Seen trade skip

```text
F                                                                        [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_core.py::test_chained_trades_chronology_one_time_and_watermark
1 failed in 0.02s
```

### Trade fingerprint includes recipient identity

```text
F                                                                        [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_core.py::test_trade_identity_includes_receiving_teams
1 failed in 0.02s
```

### Trade fingerprint ignores changing display labels and order

```text
F                                                                        [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_core.py::test_trade_fingerprint_survives_current_nhl_position_labels
1 failed in 0.02s
```

### Final trade rows grouped by owner

```text
F                                                                        [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_core.py::test_trade_result_is_grouped_by_owner_order
1 failed in 0.02s
```

### Empty teams retain identity

```text
FF                                                                       [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_core.py::test_team_with_zero_keepers_can_receive_keeper
FAILED tests/test_keeper_cli.py::test_cli_preserves_empty_team_identity - Val...
2 failed in 0.18s
```

### Leap-day parsing uses season year

```text
F                                                                        [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_core.py::test_leap_day_trade_date - ValueError: day ...
1 failed in 0.02s
```

### Zero keeper block retains a physical template row

```text
F                                                                        [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_sheet.py::test_empty_block_keeps_one_physical_row_and_insert_structure
1 failed in 0.03s
```

### Insert copies formatting

```text
F                                                                        [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_sheet.py::test_empty_block_keeps_one_physical_row_and_insert_structure
1 failed in 0.03s
```

### Insert copies validation

```text
F                                                                        [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_sheet.py::test_empty_block_keeps_one_physical_row_and_insert_structure
1 failed in 0.03s
```

### Insert copies formula columns

```text
F                                                                        [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_sheet.py::test_expand_and_zero_keeper_template - ass...
1 failed in 0.03s
```

### Literal writes target only C E G

```text
F                                                                        [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_sheet.py::test_plan_preserves_formula_columns_and_owner_blocks
1 failed in 0.03s
```

### Literal update mask preserves formatting

```text
F                                                                        [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_sheet.py::test_plan_preserves_formula_columns_and_owner_blocks
1 failed in 0.03s
```

### Content writes leave headers untouched

```text
F                                                                        [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_sheet.py::test_content_requests_never_target_headers
1 failed in 0.03s
```

### Formula offset arithmetic

```text
F                                                                        [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_sheet.py::test_formula_offsets_match_sheet_row_references
1 failed in 0.03s
```

### Empty template FYK is meaningful

```text
F                                                                        [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_sheet.py::test_empty_template_uses_current_year_input
1 failed in 0.03s
```

### Apply defaults to dry-run

```text
FF                                                                       [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_sheet.py::test_dry_run_backup_apply_and_verification
FAILED tests/test_keeper_cli.py::test_cli_dry_run_and_watermark_after_verified_apply
2 failed in 0.20s
```

### Backup precedes write

```text
F                                                                        [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_sheet.py::test_backup_is_durable_before_first_write
1 failed in 0.03s
```

### Backup contains original values and formulas

```text
F                                                                        [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_sheet.py::test_dry_run_backup_apply_and_verification
1 failed in 0.04s
```

### Backup fsync failure blocks write

```text
F                                                                        [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_sheet.py::test_backup_is_durable_before_first_write
1 failed in 0.04s
```

### Dependent UI is checked before success

```text
F                                                                        [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_sheet.py::test_apply_checks_dependent_ui_before_success
1 failed in 0.04s
```

### All eight Sheets error values checked

```text
FFF                                                                      [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_sheet.py::test_all_sheet_formula_errors_fail_verification[#NAME?]
FAILED tests/test_keeper_sheet.py::test_all_sheet_formula_errors_fail_verification[#NUM!]
FAILED tests/test_keeper_sheet.py::test_all_sheet_formula_errors_fail_verification[#NULL!]
3 failed in 0.03s
```

### Overlapping invocation is locked out

```text
F                                                                        [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_cli.py::test_lock_excludes_overlapping_apply - Value...
1 failed in 0.19s
```

### Pending recovery respects dry-run

```text
F                                                                        [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_cli.py::test_pending_retry_writes_unchanged_source
1 failed in 0.20s
```

### Already-written journal recovery is idempotent

```text
F                                                                        [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_cli.py::test_recover_verified_sheet_after_watermark_write_failure
1 failed in 0.21s
```

### Unapplied journal is actually retried

```text
F                                                                        [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_cli.py::test_pending_retry_writes_unchanged_source
1 failed in 0.20s
```

### Persisted watermark is loaded

```text
F                                                                        [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_cli.py::test_watermark_is_loaded_after_manual_correction
1 failed in 0.21s
```

### State file fsync precedes replacement

```text
F                                                                        [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_cli.py::test_save_json_atomic_durable_replacement - ...
1 failed in 0.17s
```

### State directory is fsynced

```text
F                                                                        [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_cli.py::test_save_json_atomic_durable_replacement - ...
1 failed in 0.17s
```

### State replacement is atomic

```text
F                                                                        [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_cli.py::test_save_json_atomic_durable_replacement - ...
1 failed in 0.17s
```

### Watermark file is season scoped

```text
F                                                                        [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_cli.py::test_watermark_season_and_pending_sheet_scopes
1 failed in 0.19s
```

### Journal file is sheet scoped

```text
F                                                                        [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_cli.py::test_watermark_season_and_pending_sheet_scopes
1 failed in 0.23s
```

### Browser collection is validated before planning

```text
F                                                                        [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_cli.py::test_profile_collection_is_validated_before_sheet_planning
1 failed in 0.18s
```

### Parsed draft matches actual tagged players

```text
F                                                                        [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_collect.py::test_live_markup_draft_matches_staged_keeper_board
1 failed in 0.18s
```

### Parsed trade rows match recorded transactions

```text
F                                                                        [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_collect.py::test_live_markup_trade_sample_and_fail_closed
1 failed in 0.15s
```

### collect.mjs — throw Error('invalid collector arguments');

```text
.......F.........                                                        [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_transport.py::test_transport_refuses_unverified_collection[scenario7-bad-command-2025-5003-invalid collector arguments]
1 failed, 16 passed in 0.46s
```

### collect.mjs — throw Error('Yahoo login or season metadata unavailable; re-login manually');

```text
F................                                                        [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_transport.py::test_transport_refuses_unverified_collection[scenario0-reconcile-2025-5003-season metadata]
1 failed, 16 passed in 0.47s
```

### collect.mjs — throw Error('requested draft season is not available in dropdown');

```text
.F...............                                                        [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_transport.py::test_transport_refuses_unverified_collection[scenario1-reconcile-2000-5003-not available]
1 failed, 16 passed in 0.47s
```

### collect.mjs — throw Error('historical transactions require the archived --league-id');

```text
..F..............                                                        [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_transport.py::test_transport_refuses_unverified_collection[scenario2-scan-trades-2024-5003-archived --league-id]
1 failed, 16 passed in 0.48s
```

### collect.mjs — throw Error('transaction pagination incomplete');

```text
...............F.                                                        [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_transport.py::test_pagination_refuses_unproven_completeness[scenario5-pagination incomplete]
1 failed, 16 passed in 0.46s
```

### collect.mjs — throw Error('transaction season/league redirect; refusing mislabeled trades');

```text
.....F...........                                                        [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_transport.py::test_transport_refuses_unverified_collection[scenario5-scan-trades-2026-5003-redirect]
1 failed, 16 passed in 0.47s
```

### collect.mjs — throw Error('unrecognized pagination marker');

```text
...........F.....                                                        [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_transport.py::test_pagination_refuses_unproven_completeness[scenario1-pagination marker]
1 failed, 16 passed in 0.48s
```

### collect.mjs — throw Error('ambiguous pagination');

```text
....F............                                                        [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_transport.py::test_transport_refuses_unverified_collection[scenario4-scan-trades-2026-5003-ambiguous pagination]
1 failed, 16 passed in 0.47s
```

### collect.mjs — throw Error('unsupported transaction page size');

```text
............FF...                                                        [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_transport.py::test_pagination_refuses_unproven_completeness[scenario2-page size]
FAILED tests/test_keeper_transport.py::test_pagination_refuses_unproven_completeness[scenario3-page size]
2 failed, 15 passed in 0.47s
```

### collect.mjs — throw Error('missing terminal pagination evidence on full page');

```text
..........F......                                                        [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_transport.py::test_pagination_refuses_unproven_completeness[scenario0-terminal pagination]
1 failed, 16 passed in 0.47s
```

### collect.mjs — throw Error('unexpected transaction pagination target');

```text
...F.............                                                        [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_transport.py::test_transport_refuses_unverified_collection[scenario3-scan-trades-2026-5003-pagination target]
1 failed, 16 passed in 0.47s
```

### collect.mjs — throw Error('transaction pagination incomplete: cycle');

```text
......F..........                                                        [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_transport.py::test_transport_refuses_unverified_collection[scenario6-scan-trades-2026-5003-pagination incomplete]
1 failed, 16 passed in 0.47s
```

### collect.mjs — throw Error('unexpected transaction pagination offset');

```text
..............F..                                                        [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_transport.py::test_pagination_refuses_unproven_completeness[scenario4-pagination offset]
1 failed, 16 passed in 0.48s
```

### collect.mjs — Missing profile is rejected before opening browser

```text
................F                                                        [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_transport.py::test_missing_profile_never_creates_browser_session
1 failed, 16 passed in 0.47s
```

### collect.mjs — Browser profile is closed

```text
FFFFFFF.FF.......                                                        [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_transport.py::test_transport_refuses_unverified_collection[scenario0-reconcile-2025-5003-season metadata]
FAILED tests/test_keeper_transport.py::test_transport_refuses_unverified_collection[scenario1-reconcile-2000-5003-not available]
FAILED tests/test_keeper_transport.py::test_transport_refuses_unverified_collection[scenario2-scan-trades-2024-5003-archived --league-id]
FAILED tests/test_keeper_transport.py::test_transport_refuses_unverified_collection[scenario3-scan-trades-2026-5003-pagination target]
FAILED tests/test_keeper_transport.py::test_transport_refuses_unverified_collection[scenario4-scan-trades-2026-5003-ambiguous pagination]
FAILED tests/test_keeper_transport.py::test_transport_refuses_unverified_collection[scenario5-scan-trades-2026-5003-redirect]
FAILED tests/test_keeper_transport.py::test_transport_refuses_unverified_collection[scenario6-scan-trades-2026-5003-pagination incomplete]
FAILED tests/test_keeper_transport.py::test_transport_returns_captured_page_and_closes_profile
FAILED tests/test_keeper_transport.py::test_two_page_structural_pager_deduplicates_top_bottom_links
9 failed, 8 passed in 0.47s
```

### collect.mjs — Pagination continues past first page

```text
...F..F..F....FF.                                                        [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_transport.py::test_transport_refuses_unverified_collection[scenario3-scan-trades-2026-5003-pagination target]
FAILED tests/test_keeper_transport.py::test_transport_refuses_unverified_collection[scenario6-scan-trades-2026-5003-pagination incomplete]
FAILED tests/test_keeper_transport.py::test_two_page_structural_pager_deduplicates_top_bottom_links
FAILED tests/test_keeper_transport.py::test_pagination_refuses_unproven_completeness[scenario4-pagination offset]
FAILED tests/test_keeper_transport.py::test_pagination_refuses_unproven_completeness[scenario5-pagination incomplete]
5 failed, 12 passed in 0.46s
```

### collect.mjs — Duplicate top/bottom next links are deduplicated

```text
.........F.......                                                        [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_transport.py::test_two_page_structural_pager_deduplicates_top_bottom_links
1 failed, 16 passed in 0.46s
```

### Exact identity wins over close fuzzy candidate

```text
F                                                                        [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_core.py::test_exact_match_wins_and_unrelated_names_do_not_match
1 failed in 0.02s
```

### Fuzzy threshold excludes unrelated player

```text
F                                                                        [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_core.py::test_exact_match_wins_and_unrelated_names_do_not_match
1 failed in 0.02s
```

### Empty candidate set safely returns no match

```text
F                                                                        [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_core.py::test_exact_match_wins_and_unrelated_names_do_not_match
1 failed in 0.02s
```

### Draft uses explicit keeper flags

```text
F                                                                        [100%]
=========================== short test summary info ============================
FAILED tests/test_keeper_core.py::test_reconcile_tag_count_and_unknown_team
1 failed in 0.02s
```

### DOM pager selector

```text
F                                                                        [100%]
=================================== FAILURES ===================================
_____________________ test_real_browser_collects_two_pages _____________________
/tmp/test_keeper_browser_smoke.py:7: in test_real_browser_collects_two_pages
    assert result.returncode==0,result.stderr
E   AssertionError: file:///home/david/nhl-stats/.worktrees/feature/M-keeper-reconcile-tool/src/keeper/collect.mjs:65
E             throw Error('missing terminal pagination evidence on full page');
E                   ^
E     
E     Error: missing terminal pagination evidence on full page
E         at file:///home/david/nhl-stats/.worktrees/feature/M-keeper-reconcile-tool/src/keeper/collect.mjs:65:15
E         at runNextTicks (node:internal/process/task_queues:60:5)
E         at process.processImmediate (node:internal/timers:454:9)
E         at process.callbackTrampoline (node:internal/async_hooks:130:17)
E     
E     Node.js v20.20.2
E     
E   assert 1 == 0
E    +  where 1 = CompletedProcess(args=['node', '/home/david/nhl-stats/.worktrees/feature/M-keeper-reconcile-tool/src/keeper/collect.mj...de:internal/timers:454:9)\n    at process.callbackTrampoline (node:internal/async_hooks:130:17)\n\nNode.js v20.20.2\n").returncode
=========================== short test summary info ============================
FAILED ../../../../../../tmp/test_keeper_browser_smoke.py::test_real_browser_collects_two_pages
1 failed in 20.83s
```

### DOM transaction counter

```text
F                                                                        [100%]
=================================== FAILURES ===================================
_____________________ test_real_browser_collects_two_pages _____________________
/tmp/test_keeper_browser_smoke.py:7: in test_real_browser_collects_two_pages
    assert result.returncode==0,result.stderr
E   AssertionError: file:///home/david/nhl-stats/.worktrees/feature/M-keeper-reconcile-tool/src/keeper/collect.mjs:63
E             throw Error('unsupported transaction page size');
E                   ^
E     
E     Error: unsupported transaction page size
E         at file:///home/david/nhl-stats/.worktrees/feature/M-keeper-reconcile-tool/src/keeper/collect.mjs:63:15
E     
E     Node.js v20.20.2
E     
E   assert 1 == 0
E    +  where 1 = CompletedProcess(args=['node', '/home/david/nhl-stats/.worktrees/feature/M-keeper-reconcile-tool/src/keeper/collect.mj...///home/david/nhl-stats/.worktrees/feature/M-keeper-reconcile-tool/src/keeper/collect.mjs:63:15\n\nNode.js v20.20.2\n").returncode
=========================== short test summary info ============================
FAILED ../../../../../../tmp/test_keeper_browser_smoke.py::test_real_browser_collects_two_pages
1 failed in 16.02s
```
