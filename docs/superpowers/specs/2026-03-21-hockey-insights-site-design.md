# Hockey Insights Site — Design Spec

**Date:** 2026-03-21
**Status:** Approved

## Overview

A daily-updated public website for "smart casual" hockey fans. The core premise: surface the most interesting stories hiding in shot quality (xG) and performance data, written accessibly rather than dumped as raw stats. Updated automatically every day by the existing nhl-stats scraping pipeline. Accompanied by automated Bluesky posts driving traffic back to the site.

Target audience: fans who care about hockey seriously but don't want to read a Corsi tutorial. The gap between analytics nerds (Natural Stat Trick, MoneyPuck) and bland official content (NHL EDGE).

---

## Architecture

**Frontend:** Next.js app deployed to Vercel, starting in static generation mode. Pages are pre-built at deploy time from JSON data files — no database queries at runtime, no server to manage. Free to run.

**Upgrade path (future):** When interactivity is needed (player search, on-demand comparisons), add a Vercel API route pointing at a cloud-hosted SQLite-compatible DB (Turso). This will require migrating data fetching from static JSON to API calls — not a trivial change, but well-understood.

**Backend pipeline:** Python scripts added to the existing `scripts/` directory. The cron job calls a new orchestrator script (`scripts/publish.sh`) after `update.sh` completes. `publish.sh` is separate from `update.sh` so scraper failures and publish failures are isolated.

---

## Daily Pipeline

The cron schedule adds a second daily job running `publish.sh` after `update.sh`:

```
10:00 UTC  →  update.sh   (existing: scrape game data)
10:30 UTC  →  publish.sh  (new: generate + deploy + post)
```

`publish.sh` runs each step independently with per-step error handling. A failing step is logged and skipped; subsequent steps continue unless they explicitly depend on the failed step:

```bash
# publish.sh (pseudocode structure)

run_step "scrape_injuries"   scripts/scrape_injuries.py   || INJURIES_FAILED=1
run_step "fetch_rss"         scripts/fetch_rss.py         || RSS_FAILED=1
run_step "generate"          scripts/generate.py          || exit 1  # deploy is pointless without this
run_step "build"             cd site && npm run build     || exit 1
run_step "deploy"            vercel deploy --prebuilt     || exit 1
run_step "post_social"       scripts/social.py            # failures logged, never block
```

`generate.py` receives the failure flags from earlier steps and adjusts story selection accordingly (e.g., `--injuries-unavailable` skips player stories).

**Vercel deploy mechanics:**
- The Next.js site lives at `site/` in the repo
- `generate.py` writes JSON data files to `site/public/data/` (served as static files) and to `site/src/data/` (read by `getStaticProps` at build time)
- `npm run build` runs `next build` inside `site/`, producing `.next/`
- `vercel deploy --prebuilt` ships the `.next/` artifact; auth via `VERCEL_TOKEN` env var in cron environment
- The cron machine therefore needs Node.js, npm, and `vercel` CLI installed alongside Python

---

## File Layout

```
nhl-stats/
  data/
    nhl.db                        # existing SQLite DB
    logs/                         # existing cron logs
    story_history.json            # local state: 7-day story dedup tracker (NOT a build artifact)
  scripts/
    update.sh                     # existing scraper orchestrator
    publish.sh                    # new: generate + deploy + post
    scrape_injuries.py            # new
    fetch_rss.py                  # new
    generate.py                   # new
    social.py                     # new
  site/                           # new: Next.js app
    public/
      data/                       # static JSON served at runtime
        leaderboard.json
        story.json
        chart-YYYY-MM-DD.png     # chart image for current story
    src/
      data/                       # JSON read by getStaticProps at build time
        players/
          {player_id}.json        # e.g., 8478402.json (NHL numeric ID)
        teams/
          {team_abbrev}.json      # e.g., TOR.json
      app/
        page.tsx                  # home page
        players/[id]/page.tsx     # player profile
        teams/[abbrev]/page.tsx   # team page
```

---

## Injuries Table

New `injuries` table in `nhl.db`:

```sql
CREATE TABLE injuries (
    player_id     INTEGER,
    player_name   TEXT,
    status        TEXT,    -- 'IR', 'LTIR', 'DTD', 'SUSPENDED', 'HEALTHY'
    detail        TEXT,    -- e.g., "upper body injury"
    scraped_at    DATETIME,
    updated_at    DATETIME
);
```

Source: NHL roster API (`/v1/roster/{team}/current`), which returns each player with a `rosterStatus` field. Players with status `'IR'`, `'LTIR'`, or `'SUSPENDED'` are excluded from player-specific story selection. `'DTD'` (day-to-day) players are included but flagged. `'HEALTHY'` is the normal state.

The existing `rosters` table already has `roster_status` — the new `injuries` table is a daily snapshot focused on availability, not roster membership.

The existing `players` table (schema unchanged) is the source of truth for player identity. `generate.py` joins `players` with `injuries` on `player_id` to resolve display names and apply availability exclusions. No schema changes to `players` are required.

---

## Pages

### Home page (`/`)
Updated on every deploy. Two sections:

**Story of the day** — one featured narrative, written as a readable paragraph (not a table). Auto-generated from story templates (see Story Selection below).

If an injury scraper error flag is set, only team-level story types are considered. During the off-season or extended schedule gaps, the home page retains the previous day's story — no "no content" state.

**Leaderboards** — three compact lists, current season only, min. 50 shots:
- Shooters running hottest above expected goals
- Shooters most unlucky below expected goals
- Teams most over/underperforming their xG-implied win%

Leaderboard entries link to player/team pages. Players on IR/LTIR are excluded from leaderboards.

### Player pages (`/players/[id]`)
URL uses the NHL numeric player ID (e.g., `/players/8478402`). Generated for all players in the `players` table with at least one season of shot data.

- Career xG vs actual goals by season (bar/line chart)
- Current season shot breakdown by type
- Auto-generated one-line verdict based on career GAx trend

### Team pages (`/teams/[abbrev]`)
One per team, URL uses team abbreviation (e.g., `/teams/TOR`).

- xG for vs against across current season
- Win% vs xG-implied win%

---

## Story Selection

`generate.py` scores candidate stories from a fixed set of templates and picks the highest-scoring one that hasn't run in the last 7 days (tracked in a `story_history` JSON file). This prevents the same player appearing every day while their streak lasts.

**Story types (priority order):**

| Priority | Type | Trigger condition |
|---|---|---|
| 1 | News + data combo | Player/team in top RSS headlines AND has notable xG deviation |
| 2 | Extreme current-season shooter | GAx > +12 or < -10, min 80 shots, player available |
| 3 | Multi-season sustainability | Career sh/expected ratio > 1.3 or < 0.8, current season > 60 shots |
| 4 | Team record vs xG | Win% vs xG-implied win% diverges by > 10 percentage points |
| 5 | Fallback | Highest absolute GAx among available players |

If injuries are unavailable, types 1–3 are skipped and type 4 runs. If no team story qualifies either (rare), the previous day's story is reused.

---

## Chart Images

`generate.py` writes one PNG per day to `site/public/data/chart-YYYY-MM-DD.png`. The `story.json` file references the chart by filename:

```json
{
  "date": "2026-03-21",
  "headline": "Draisaitl is scoring at a historically unsustainable rate",
  "body": "...",
  "chart": "chart-2026-03-21.png",
  "subject_type": "player",
  "subject_id": 8478402
}
```

Old chart PNGs older than 30 days are deleted by `publish.sh` to keep storage tidy.

The chart image is also used for the Bluesky post. The Bluesky upload is a two-step process: upload the PNG blob first (`com.atproto.repo.uploadBlob`) to get a blob reference, then create the post record embedding that reference. If the blob upload fails, the social post is skipped (chart is required for social posts in MVP).

---

## News Integration

**Layer 1 — Hard filter (injury/availability):** `scrape_injuries.py` polls the NHL API daily and writes to the `injuries` table. `generate.py` reads this table to exclude unavailable players.

**Layer 2 — Context enrichment (RSS headlines):** `fetch_rss.py` pulls recent headlines from TSN, Sportsnet, and NHL.com RSS feeds and writes them to `site/public/data/headlines.json`. Relevance matching is simple: player name or team name appears in the headline title. False positives (player name in unrelated context) are accepted — this is a best-effort enrichment, not a semantic filter.

Headlines displayed on the home page link to the original article. Source name (TSN, Sportsnet, etc.) is shown alongside. Headlines older than 48 hours are excluded.

---

## Social Media

**Platform:** Bluesky only. API is free, no approval process, hockey analytics community is active there. Twitter/X excluded ($100/month API cost).

**Cadence:** One post per day. Text derived from story headline + one-sentence context. Chart image attached (required; post skipped if chart unavailable).

**Post format:**
> [Subject] is [doing thing] — [key number]. [One sentence historical context]. [link]

**Skip conditions** (post skipped, not queued):
- Injury scraper errored — skipped even for team-level stories as a conservative safety measure (simpler than reasoning about which story types are truly player-free)
- Chart generation failed
- Story generation failed
- No new story (off-season gap)

Failures are logged. Social posting never blocks the site deploy.

---

## Error Handling & Degradation

| Failure | Behavior |
|---|---|
| Game scraper fails | Site stays up with yesterday's data |
| Injury scraper fails | Skip player stories; team stories proceed; skip social post |
| RSS fetch fails | Story runs without news context; no headlines shown |
| Chart generation fails | Story publishes text-only; social post skipped |
| `next build` fails | Previous Vercel deployment stays live; alert logged |
| Vercel deploy fails | Previous version stays live; alert logged |
| Bluesky blob upload fails | Social post skipped; logged |
| Bluesky post creation fails | Logged; not retried |
| No qualifying story | Previous day's story shown; no social post |

The site always stays up. Social posting fails silently.

---

## Testing

Story generation is the highest-priority test target — it has the most conditional logic and the most ways to produce wrong output:
- Correct story type selection across all five types
- Injured players excluded from player-specific stories
- 7-day deduplication works correctly
- Fallback to team stories when injuries unavailable
- Fallback to previous story when no team story qualifies
- Output JSON is well-formed for all story templates

Injury scraper gets fixture-based unit tests for the "API returns empty" and "API returns error" paths, since this is a hard gate for social posting.

Other scrapers and the deploy pipeline are validated by the daily run.

---

## Out of Scope (MVP)

- Player search / filtering (requires API route + cloud DB migration)
- Twitter/X posting
- User accounts or saved views
- Historical story archive
- Mobile app
- Paid features
- Semantic RSS relevance matching (simple name matching is sufficient for MVP)
