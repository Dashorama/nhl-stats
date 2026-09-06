# Keeper reconciliation — proposal for David

Recommend enhancing the existing Google Sheet first. It already expresses keeper
terms and provides a familiar shared view for the twelve owners. A host-side
browser collector feeds a pure Python engine, then a thin sheets-cli adapter.
Yahoo's approval-gated API is not an option. Collection stays on David's host,
using his authenticated Playwright profile; expired sessions require manual login.
No new hosting service or full UI is needed for v1.

The pure engine accepts JSON snapshots and returns keeper records plus trade
watermark state. Reconcile retains existing row order, appends new draft keepers
in board order, preserves FYK/trade counts globally, and matches normalized player names
with explicit league aliases and conservative fuzzy matching. Ambiguous matches
fail for human resolution. In-season scans are season-scoped, chronological,
and use stable transaction fingerprints to avoid replay. The confirmed trade bonus is cumulative: each newly applied keeper trade adds
one to column G. The existing `F = E + term + G` formula already supports counts;
no formula change is needed. A draft team move carries the contract without adding
a bonus and emits a possible-unrecorded-trade warning for human verification.

Sheet operations default to dry-run. Apply is restricted to the supplied TEST
COPY in this version. Save values and formulas before writes; submit row
reshaping, formula copies, and C/E/G literals as one atomic Sheets batch.
Preserve owner block identities and all header formulas. Read back content,
formula columns, owner alignment and dependent tabs before advancing the local
watermark. A local lock prevents overlapping invocations; a pre-write snapshot
comparison detects intervening sheet edits. Human edits during the API request
remain a limitation: run during a quiet editing window.

Run the trade command weekly October–April on David's existing host scheduler.
Ship a documented command, not an enabled job: the host/profile/season must be
configured deliberately. Scrape selectors will need maintenance if Yahoo changes
its markup. Missing keeper tags, incomplete season selection, or unrecognized
trade rows must stop collection rather than silently clear the sheet.

A later static read-only standings page can consume a sanitized JSON export from
this same host. It would be shareable without sheet-edit access and could use the
repository's existing static-site infrastructure at no additional hosting cost.
It adds publishing, freshness indicators and UI maintenance; serverless hosting
does not eliminate the authenticated browser host. Full UI work requires David's
explicit greenlight. This proposal recommends the sheet for now, so no new app
or hosting layer is built in this change.

## Owner identity and fixture acceptance (NOVA-KRT-1/3)

Owner identity survives team renames. The explicit aliases `Bitch Slappers` (2025),
`JeanClaud VanDangles` (historical Yahoo spelling), and `Jean Claude VanDangles`
(2026 sheet) identify Jack Manire's block. Other teams use the sheet's existing
team-to-owner mapping; new renames require an explicit alias, never a fuzzy owner
match. The sheet's block order remains the owner-list order.

The staged CSV is a reference for each owner's SET of normalized player/FYK/count
records, not an oracle for spelling or row order. All output player names come from
the draft board. Known misspellings assist matching only. Existing contracts are
matched across the entire sheet, retain original sheet order within their assigned
owner block, and carry FYK/count unchanged. Players absent from the entire sheet
are appended in draft-board order with season FYK and count zero. The CSV's
Jack-Hughes-before-Draisaitl artifact is deliberately not reproduced.

B1 (`=YEAR(TODAY())-MONTH(6)`) is preserved verbatim, like all header formulas.
The existing `Traded?` header remains; its numeric values now mean trade counts.
Production scheduling and any new UI still require the separate rollout decision.
