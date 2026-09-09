# NHL Stats — Operations Guide

## Overview

This project scrapes NHL data from multiple sources and stores it in a local SQLite database. Data collection runs on a schedule via cron on the WSL2 host machine.

**Future migration:** This setup is intended to be replaced by a centralized job scheduler (see "Migration" section below). The cron jobs are deliberately simple to make migration straightforward.

## Data Sources and Update Frequency

| Source | Command | Frequency | Runtime | What it does |
|--------|---------|-----------|---------|-------------|
| NHL API — games | `update --daily` | Daily | ~30s | Fetches game schedule and scores for current season |
| NHL API — boxscores | `update --daily` | Daily | ~2min for new games | Per-player stats for completed games not yet in DB |
| NHL API — play-by-play | `update --daily` | Daily | ~3min for new games | Every event (shot, hit, faceoff) with coordinates, current season only |
| NHL API — shift charts | `update --daily` | Daily | ~2min for new games | Per-player shifts for the same new games |
| Data integrity checks | `update`, `validate` | Every run | ~5s | Fails the run if the corpus or the joins regress |
| NHL API — game logs | `update --daily` | Daily | ~15min (all players) | Per-game stats for each player |
| NHL API — teams | `update` | Weekly | ~5s | Team standings and metadata |
| NHL API — players | `update` | Weekly | ~10s | Player list from leaders endpoint |
| NHL rosters | `update` | Weekly | ~30s | Full roster for all 32 teams |
| MoneyPuck — advanced stats | `update` | Weekly | ~15s | Corsi, Fenwick, xG, zone starts per player |
| MoneyPuck — shot data | `update` | Weekly | ~30s download + ~5s insert | Shot-level xG, coordinates, angles for current season |

## Schedule

| Job | Cron expression | Time | Description |
|-----|----------------|------|-------------|
| Daily update | `0 10 * * *` | 10:00 UTC / 6:00am ET | Games, boxscores, PBP, game logs |
| Full update | `0 12 * * 0` | 12:00 UTC / 8:00am ET Sunday | Everything including MoneyPuck data |

**Why these times:** NHL games end by ~midnight ET. By 6am ET all scores are final and the NHL API has updated. Sunday full update catches weekly MoneyPuck data refreshes.

**There is no scheduled scrape in GitHub Actions.** A `scheduled-scrape.yml` workflow
used to exist but could never have worked — it invoked a command (`nhl-scraper`) that
this project does not install, against a runner with no database to write to. It was
removed; cron on the WSL2 host is the only scheduler.

## Backfills

Historical collection is separate from the nightly run, so a nightly stays a few
minutes long. Every backfill is idempotent and safe to re-run:

```bash
# Repair games.season / games.game_date on stored rows (re-scrapes schedules)
python -m src.cli backfill-games

# Re-ingest MoneyPuck shot data so situation, is_home and game_id are correct
python -m src.cli backfill-shots --start-season 2018

# Collect play-by-play and shift charts for past seasons (resumable)
python -m src.cli backfill-pbp --start-season 2018 --rate 4

# Check the result
python -m src.cli validate
```

`backfill-pbp` skips games that already have events, so an interrupted run
resumes simply by running it again. Expect roughly 10,000 games for 2018-2025,
about 45 minutes at `--rate 4`, and around 1GB of additional database size for
play-by-play plus 1.5GB for shifts.

## Data integrity

`python -m src.cli validate` exits non-zero when any of these regress:

| Check | What it catches |
|-------|-----------------|
| `games_season_populated` | `games.season` going NULL again |
| `games_date_populated` | `games.game_date` going NULL again |
| `shots_situation_populated` | MoneyPuck renaming or dropping the fields situation is derived from |
| `shots_join_games` | A shot id that joins to no game (the MoneyPuck 5-digit id leaking back in) |
| `shots_join_play_by_play` | Shots and play-by-play drifting into different id spaces |
| `unique_ingest_keys` | A missing unique index, i.e. ingest is no longer idempotent |
| `pbp_corpus` | A season missing from play-by-play, or collected below 95% |

The corpus assertion only requires seasons whose stored schedule is complete, so
a season still being played never trips it.

## File Layout

```
nhl-stats/
├── scripts/
│   ├── update.sh              # Wrapper: activates venv, runs CLI, logs output
│   ├── install-cron.sh        # Installs cron entries (idempotent)
│   └── uninstall-cron.sh      # Removes cron entries
├── data/
│   ├── nhl.db                 # SQLite database (~300MB)
│   └── logs/
│       └── update-YYYY-MM-DD.log  # Daily log files
└── src/cli.py                 # CLI with `update` command
```

## Manual Operations

```bash
# Run a full update manually
cd /home/david/nhl-stats
source .venv/bin/activate
python -m src.cli update

# Run daily update only
python -m src.cli update --daily

# Check database stats
python -m src.cli stats

# View recent logs
ls -la data/logs/
tail -50 data/logs/update-$(date +%Y-%m-%d).log

# Check cron status
crontab -l | grep nhl-stats
```

## Migration to Central Scheduler

When moving to containerized job management:

1. **Remove cron jobs:** Run `./scripts/uninstall-cron.sh`
2. **Replicate these two jobs:**
   - Daily at 10:00 UTC: `cd /home/david/nhl-stats && ./scripts/update.sh --daily`
   - Weekly Sunday at 12:00 UTC: `cd /home/david/nhl-stats && ./scripts/update.sh`
3. **Requirements:** Python 3.10+, venv at `.venv/`, ~300MB disk for SQLite DB
4. **Health check:** `python -m src.cli validate` exits 0 (and `stats` returns table counts > 0)
5. **Log location:** `data/logs/update-YYYY-MM-DD.log`
6. **Exit codes:** 0 = success, 1 = partial failure (some sources errored), 2 = total failure

The wrapper script (`scripts/update.sh`) is the only entry point — the scheduler just needs to call it with the right args and capture the exit code.

## Troubleshooting

- **"0 new boxscores"**: Normal if no games were played yesterday
- **MoneyPuck timeout**: Their ZIP files are large. The scraper has 120s timeout. Retry on next scheduled run.
- **NHL API 404**: Happens occasionally during API maintenance. Errors are logged but don't block other sources.
- **DB locked**: Only one update should run at a time. Cron schedule ensures no overlap (daily at 10:00, weekly at 12:00 Sunday only).
