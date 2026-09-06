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
per-team additions/removals, possible-unrecorded-trade warnings, and every proposed
Sheets request. Spelling corrections
appear as removal/addition pairs. The pure functions return team/player/FYK/trade-count;
expiry and remaining years stay spreadsheet formulas, never computed by the tool.

For authenticated browser collection, replace `--input` with `--profile PATH`:

```bash
python3 -m src.keeper.cli reconcile --season 2025 --profile "$KEEPER_YAHOO_PROFILE"
python3 -m src.keeper.cli scan-trades --season 2026 --profile "$KEEPER_YAHOO_PROFILE"
# Season-specific league IDs are resolved automatically (2024 = 17419):
python3 -m src.keeper.cli scan-trades --season 2024 \
  --profile "$KEEPER_YAHOO_PROFILE"
```

Set `KEEPER_YAHOO_PROFILE` to the existing `scratchpad/yahoo_profile` directory.
The profile is not copied or checked in. Chromium itself locks the profile: close
other users of that same profile before running. The collector defaults to
`/home/david/DrillDeck/node_modules/playwright/index.mjs` and
`~/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome`; override with
`KEEPER_PLAYWRIGHT` and `KEEPER_CHROMIUM`. Python invokes Node with a three-minute
timeout and parses its captured output before planning any write.

The collector uses the verified season-to-league map in `src/keeper/seasons.json`
for BOTH commands (2026=5003, 2025=26028, 2024=17419; complete through 2014).
An unknown season requires a verified `--league-id` override. It first visits
`/hockey/ID/draftresults` and checks that league's current draft-season metadata.
If unavailable or mismatched, it retries `/YEAR/hockey/ID/draftresults` and verifies
again. On this host, the bare 2024/2025 URLs returned Yahoo error pages while the
archive forms returned the expected seven trades / sixty keepers. Transactions
use the successfully verified URL root. No current-league previous-season dropdown
navigation is needed; the archived league's own current draft is authoritative.
Only explicit keeper badges count. Transactions use the Trades filter and Yahoo's
structural `pagingnavlist` / `li.last` controls with `count` offsets, deduplicating
identical top/bottom links. The observed contract is 25 trades per full page.
A full page must provide a next offset or an explicit disabled terminal control;
a short page terminates the crawl. Missing markers, inconsistent page sizes,
wrong offsets, changed origins/paths/filters, and cycles are rejected. Parsed
trade counts must match the browser's count and pages must not overlap. Yahoo
exposes no global total here; a future change in page capacity needs a collector
and fixture update. Within this supported contract the scanner reads the available
history, then filters the selected season and already-seen fingerprints.

## Weekly operation and trade rule

Use David's existing host scheduler once weekly October–April. Suggested command:

```bash
python3 -m src.keeper.cli scan-trades --season 2026 \
  --profile "$KEEPER_YAHOO_PROFILE" --state-dir /home/david/.local/state/nhl-keepers
```

For a reviewed, opt-in user crontab, this runs Mondays at 09:00 in the host's
local timezone during October–April (fill in the durable profile path first):

```cron
KEEPER_YAHOO_PROFILE=/absolute/path/to/yahoo_profile
0 9 * 1-4,10-12 1 cd /home/david/nhl-stats && python3 -m src.keeper.cli scan-trades --season 2026 --profile "$KEEPER_YAHOO_PROFILE" --dry-run
```

Rotate `--season` after each draft. Configure cron output delivery/log retention
through the host's existing operations setup.

This is a dry-run command; no scheduler is installed or enabled by this PR. Review
its diff and use `--apply` on the test copy. Season, authenticated profile, and live
rollout must be configured before enabling production automation. Do not put
browser cookies or the profile in GitHub Actions secrets or publish collected
HTML. No Yahoo API credentials are needed.

The confirmed bonus is **cumulative**: each newly applied keeper trade adds one to
column G, carrying FYK unchanged. A keeper with count 2 becomes count 3 after the
next trade. `Traded?` remains the column label for compatibility, but values are
nonnegative integer counts. The existing `F = E + term + G` formula already adds
that many years; no formula/header change is made.

Known fingerprints are skipped. For a previously unseen transaction whose keeper
is already under the acquiring owner, the scanner treats the row as already
reflected and preserves its count. This allows starting from a manually maintained
sheet without awarding the same bonus again. It cannot infer missing historical
bonuses from ownership alone: verify counts before bootstrapping, keep the durable
watermark, and do not replay old history onto a different roster. Chained new trades
are processed chronologically and increment once each. Duplicate keeper receipts
within one transaction are rejected.

Keeper counts vary during the season; a team with zero keepers keeps one empty
formula template row so its owner block can later receive a keeper. The placeholder's
E input uses the sheet's current year, avoiding nonsensical year-zero calculations.

Post-draft reconciliation matches players globally across the sheet. It carries
FYK/count through a team move and emits `possible unrecorded trade: PLAYER sheet-team
B -> draft-team A; FYK/count carried, verify bonus`. It does not increment G:
that belongs to the scanner, and guessing could double-count. Prefer scanning
outstanding trades before reconciling; after a flagged move, verify the bonus
manually because ownership alone now looks reflected. Output uses canonical draft
names, retains existing contracts in source-sheet order, then appends genuinely new
keepers in board order. The 2025 CSV is graded by per-owner set equality, not its
cosmetic spelling or order artifacts.

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
use a quiet editing window. The host's outer three-minute timeout can kill Node
before Chromium closes; inspect and stop any collector browser still using the
profile before retrying. Production timeout cleanup and friendlier lock/missing-tab
diagnostics are follow-ups in issue #1. Fixture mode deliberately permits historical
seasons; B1 alone is not a reliable season check during autumn, so review that input
before apply. On verification failure keep the journal and backup,
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

Column G's old 0–1 validation is widened to nonnegative integers on keeper
rows only, before numeric writes in the same atomic batch. Backups include the
previous G validation rules as well as values/formulas; readback verifies each
new rule. This is the only validation change; A/B/D/F and B1 formulas and all
headers remain intact.
