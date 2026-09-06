# Keeper reconciliation — proposal for David

Recommend enhancing the existing Google Sheet first. It already expresses keeper
terms and provides a familiar shared view for the twelve owners. A host-side
browser collector feeds a pure Python engine, then a thin sheets-cli adapter.
Yahoo's approval-gated API is not an option. Collection stays on David's host,
using his authenticated Playwright profile; expired sessions require manual login.
No new hosting service or full UI is needed for v1.

The pure engine accepts JSON snapshots and returns keeper records plus trade
watermark state. Reconcile retains existing row order, appends new draft keepers
in board order, preserves FYK/trade flags, and matches normalized player names
with explicit league aliases and conservative fuzzy matching. Ambiguous matches
fail for human resolution. In-season scans are season-scoped, chronological,
and use stable transaction fingerprints to avoid replay. The default trade bonus
is the existing one-time 0/1 flag; cumulative bonuses require David's ruling and
a separate schema/formula change.

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

## Ground-truth compatibility

The staged CSV is authoritative for team/player/FYK/trade cells, not computed
expiry values. Its selective spelling corrections are explicit aliases; it keeps
`JT Miller` and `Mathew Tkachuk`. `Bitch Slappers` maps to the sheet's
`Jean Claude VanDangles`. The 2025 fixture places Jack Hughes before Leon
Draisaitl despite their opposite source order; this narrow presentation override
is explicit compatibility code rather than inferred as a universal rule.
The snapshot's B1 formula differs from the prose spec; preserve it verbatim.
