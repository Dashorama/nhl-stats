# RB Keeper League tools

Read [the design proposal](design.md) first. Full UI work awaits David's explicit
greenlight. v1 supports the existing sheet and restricts **all apply operations to
TEST COPY** `1E8P5w5ensWavBPQBO66sMmqAmFBGP0c11AhT91FPxbk`. The live sheet has not
been written during development. Production enabling is a separate reviewed change.

## Run

From the repository root, with the project's Python dependencies installed:

```bash
python3 -m src.keeper.cli reconcile --season 2025 \
  --input tests/fixtures/keeper_reconcile/keepers_2025.json
# Explicitly apply the printed plan to TEST COPY:
python3 -m src.keeper.cli reconcile --season 2025 \
  --input tests/fixtures/keeper_reconcile/keepers_2025.json --apply
# Fixture-driven trade scan (historical sample; do not replay old seasons on a new roster):
python3 -m src.keeper.cli scan-trades --season 2024 \
  --input tests/fixtures/keeper_reconcile/trades.json
```

No `--apply` means dry-run; explicit `--dry-run` is also supported. Output contains
per-team additions/removals plus every proposed Sheets request. Spelling corrections
appear as removal/addition pairs. The pure functions return team/player/FYK/Traded;
expiry and remaining years stay spreadsheet formulas, never computed by the tool.

For authenticated browser collection, replace `--input` with `--profile PATH`:

```bash
python3 -m src.keeper.cli reconcile --season 2025 --profile "$KEEPER_YAHOO_PROFILE"
python3 -m src.keeper.cli scan-trades --season 2026 --profile "$KEEPER_YAHOO_PROFILE"
# Archived league IDs differ; the recorded 2024 league is 17419:
python3 -m src.keeper.cli scan-trades --season 2024 --league-id 17419 \
  --profile "$KEEPER_YAHOO_PROFILE"
```

Set `KEEPER_YAHOO_PROFILE` to the existing `scratchpad/yahoo_profile` directory.
The profile is not copied or checked in. Chromium itself locks the profile: close
other users of that same profile before running. The collector defaults to
`/home/david/DrillDeck/node_modules/playwright/index.mjs` and
`~/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome`; override with
`KEEPER_PLAYWRIGHT` and `KEEPER_CHROMIUM`. Python invokes Node with a three-minute
timeout and parses its captured output before planning any write.

The current/previous draft dropdown labels establish season identity. The browser
uses the dropdown's `draft_results_period` URL parameter because delayed Yahoo
YUI initialization can leave a programmatic selection without a change handler.
Only explicit keeper badges count. Transactions use the Trades filter and follow
Next links, with origin/path/filter checks. Unsupported markup fails closed.
Collectors read the full available trade history; the pure scanner filters the
selected season and already-seen fingerprints. This favors correctness after a
missed week over minimizing a handful of page loads.

## Weekly operation and trade rule

Use David's existing host scheduler once weekly October–April. Suggested command:

```bash
python3 -m src.keeper.cli scan-trades --season 2026 \
  --profile "$KEEPER_YAHOO_PROFILE" --state-dir /home/david/.local/state/nhl-keepers
```

This is a dry-run command; no scheduler is installed or enabled by this PR. Review
its diff and use `--apply` on the test copy. Season, authenticated profile, and live
rollout must be configured before enabling production automation. Do not put
browser cookies or the profile in GitHub Actions secrets or publish collected
HTML. No Yahoo API credentials are needed.

The bonus is one-time: `Traded? = 1`, preserving FYK. A second trade does not add
another year. David's open ruling is one-time versus cumulative; cumulative needs
a separate column/formula change and must not be implemented silently. Keeper
counts vary during the season; a team with zero keepers keeps one empty formula
template row so its owner block can later receive a keeper.

## Backups, recovery, and shared editing

State defaults to `~/.local/state/nhl-keepers`. Keep the same state directory for
all invocations; its sheet-specific lock prevents overlap only among clients
using that directory. Watermarks are sheet-and-season scoped. Do not delete them
between weekly runs. Before each write, the tool re-reads the sheet, checks it
against the plan, and fsyncs a timestamped values-plus-formulas backup. The batch
atomically resizes owner blocks, copies formula/format/validation templates for
inserted rows, and writes only C/E/G literals. Headers, including B1, are untouched.

A durable `pending-<sheet>.json` journal covers a crash or lost HTTP response
between the sheet batch and watermark persistence. Run the same command with
`--apply` to recover: it verifies an already-applied result, or retries an unchanged
source snapshot. Any conflicting sheet content requires inspecting the retained
backup; it never automatically overwrites such conflicts. A recovered command
exits after recovery; run it once more for newly collected trades.

Verification checks every A/B/D/F formula, C/E/G value, owner alignment, and formula
errors in Raw Data and UI. For visual layout, existing formatting is retained;
the integration pass inspects Sheets grid metadata rather than claiming a browser
render. Human edits during the final API call cannot be locked by this local tool;
use a quiet editing window. On verification failure keep the journal and backup,
inspect the test sheet, and resolve the exact mismatch before retrying.

## Manual re-login (one persistent browser script)

Auto re-login is out of scope. Launch one headed persistent context, keep that
script alive through username → password → Pixel-7 approval, then verify the
league page before closing. Do not split the sequence into fresh browser scripts
or pass credentials on the command line. Example interactive script:

```js
import { chromium } from '/home/david/DrillDeck/node_modules/playwright/index.mjs';
import { createInterface } from 'node:readline/promises';
const browser = await chromium.launchPersistentContext(process.env.KEEPER_YAHOO_PROFILE, {
  headless: false,
  executablePath: process.env.KEEPER_CHROMIUM ||
    '/home/david/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome',
});
try {
  const page = await browser.newPage();
  await page.goto('https://hockey.fantasysports.yahoo.com/hockey/5003/draftresults');
  const terminal = createInterface({input: process.stdin, output: process.stdout});
  await terminal.question('Complete username, password and Pixel-7 push in this browser; press Enter when the league page is visible.');
  terminal.close();
  await page.locator('#yfa-draftresults-select').waitFor();
} finally { await browser.close(); }
```

Use a headed display available on David's host. The script never reads or logs the
password; David enters it directly into Yahoo. Then rerun the dry-run command.

## Validation

```bash
python3 -m pytest tests/ -q
python3 -m ruff check src/keeper tests/test_keeper*.py
python3 -m pip wheel . --no-deps -w /tmp/keeper-dist
```

Fixtures are unchanged ground truth. Sanitized HTML fixtures contain only draft
select/table markup and trade tables, not account navigation, session cookies,
or login tokens. See [verification evidence](verification.md) for mutation proof,
live scrape comparison, formula-preserving test-copy round trips, and review.
