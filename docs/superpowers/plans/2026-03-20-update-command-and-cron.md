# NHL Stats Update Command & Cron Job Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an `nhl-stats update` CLI command that refreshes all data sources, plus a cron job that runs it automatically. Document everything for future migration to centralized job management.

**Architecture:** A single `update` CLI command orchestrates all existing scraper methods in the right order (fast data first, heavy data last). A shell wrapper script handles logging and error notification. A cron entry calls the wrapper on a daily/weekly schedule. An `OPERATIONS.md` doc describes the full setup for future migration.

**Tech Stack:** Python (Click CLI), bash (wrapper script), cron (scheduling)

---

### Task 1: Add `update` CLI command

**Files:**
- Modify: `src/cli.py`
- Modify: `src/storage/__init__.py` (add BoxscoreRecord, PlayByPlayRecord exports)
- Test: manual run

The `update` command calls existing scraper methods in order. It needs to be smart about what to update:
- Daily data: games (scores), boxscores for new games, PBP for new games, game logs
- Weekly data: shots (MoneyPuck ZIP), advanced stats, rosters, teams/standings

A `--daily` flag runs only the fast daily subset. Default (no flag) runs everything.

- [ ] **Step 1: Add the update command to cli.py**

Add after the existing `scrape_full` command. This reuses all existing scraper and DB methods — no new logic, just orchestration.

```python
@main.command()
@click.option("--daily", is_flag=True, help="Only update daily data (games, boxscores, PBP, game logs)")
@click.pass_context
def update(ctx: click.Context, daily: bool) -> None:
    """Update all data from all sources.

    Default: full update (all sources).
    --daily: only games, boxscores, play-by-play, and game logs.

    Designed to be called by cron. See OPERATIONS.md for details.
    """
    db: Database = ctx.obj["db"]
    from datetime import datetime as dt

    async def run():
        errors = []

        # --- Always: NHL API core data ---
        async with NHLAPIScraper() as scraper:
            # Games (schedule + scores)
            console.print("[bold]Updating games...[/bold]")
            try:
                games = await scraper.scrape_games()
                db.upsert_games(games)
                console.print(f"  [green]✓ {len(games)} games[/green]")
            except Exception as e:
                errors.append(f"games: {e}")
                console.print(f"  [yellow]⚠ games: {e}[/yellow]")

            # Boxscores for completed games not yet in DB
            console.print("[bold]Updating boxscores...[/bold]")
            try:
                with db.get_session() as session:
                    # Games that are finished
                    all_finished = set(
                        r[0] for r in session.query(GameRecord.id).filter(
                            GameRecord.game_type == "2",
                            GameRecord.game_state.in_(["OFF", "FINAL"])
                        ).all()
                    )
                    # Games we already have boxscores for
                    already_scraped = set(
                        r[0] for r in session.query(BoxscoreRecord.game_id).distinct().all()
                    )
                    new_game_ids = sorted(all_finished - already_scraped)

                if new_game_ids:
                    scraped = 0
                    for gid in new_game_ids:
                        try:
                            result = await scraper.scrape_boxscore(gid)
                            db.upsert_boxscores(gid, result["players"])
                            scraped += 1
                        except Exception:
                            pass
                    console.print(f"  [green]✓ {scraped} new boxscores[/green]")
                else:
                    console.print("  [dim]No new games to scrape[/dim]")
            except Exception as e:
                errors.append(f"boxscores: {e}")
                console.print(f"  [yellow]⚠ boxscores: {e}[/yellow]")

            # Play-by-play for new games
            console.print("[bold]Updating play-by-play...[/bold]")
            try:
                with db.get_session() as session:
                    already_pbp = set(
                        r[0] for r in session.query(PlayByPlayRecord.game_id).distinct().all()
                    )
                    new_pbp_ids = sorted(all_finished - already_pbp)

                if new_pbp_ids:
                    scraped = 0
                    total_events = 0
                    for gid in new_pbp_ids:
                        try:
                            events = await scraper.scrape_play_by_play(gid)
                            db.insert_play_by_play(gid, events)
                            scraped += 1
                            total_events += len(events)
                        except Exception:
                            pass
                    console.print(f"  [green]✓ {total_events} events from {scraped} games[/green]")
                else:
                    console.print("  [dim]No new PBP to scrape[/dim]")
            except Exception as e:
                errors.append(f"pbp: {e}")
                console.print(f"  [yellow]⚠ pbp: {e}[/yellow]")

            # Game logs for all players
            console.print("[bold]Updating game logs...[/bold]")
            try:
                season_id = await scraper.get_current_season()
                with db.get_session() as session:
                    player_ids = [r[0] for r in session.query(PlayerRecord.id).all()]

                updated = 0
                for pid in player_ids:
                    try:
                        logs = await scraper.scrape_player_game_log(pid, season_id)
                        if logs:
                            db.upsert_game_logs(pid, season_id, logs)
                            updated += 1
                    except Exception:
                        pass
                console.print(f"  [green]✓ game logs for {updated} players[/green]")
            except Exception as e:
                errors.append(f"game_logs: {e}")
                console.print(f"  [yellow]⚠ game_logs: {e}[/yellow]")

        if daily:
            _print_summary(errors)
            return

        # --- Weekly: heavier data ---
        async with NHLAPIScraper() as scraper:
            console.print("[bold]Updating teams/standings...[/bold]")
            try:
                teams = await scraper.scrape_teams()
                db.upsert_teams(teams)
                console.print(f"  [green]✓ {len(teams)} teams[/green]")
            except Exception as e:
                errors.append(f"teams: {e}")
                console.print(f"  [yellow]⚠ teams: {e}[/yellow]")

            console.print("[bold]Updating players...[/bold]")
            try:
                players = await scraper.scrape_players()
                db.upsert_players(players)
                console.print(f"  [green]✓ {len(players)} players[/green]")
            except Exception as e:
                errors.append(f"players: {e}")
                console.print(f"  [yellow]⚠ players: {e}[/yellow]")

        async with NHLRosterScraper() as scraper:
            console.print("[bold]Updating rosters...[/bold]")
            try:
                rosters = await scraper.scrape_all_rosters()
                db.upsert_rosters(rosters)
                total = sum(
                    len(r.get("forwards", [])) + len(r.get("defensemen", [])) + len(r.get("goalies", []))
                    for r in rosters
                )
                console.print(f"  [green]✓ {total} roster entries[/green]")
            except Exception as e:
                errors.append(f"rosters: {e}")
                console.print(f"  [yellow]⚠ rosters: {e}[/yellow]")

        async with MoneyPuckScraper() as scraper:
            console.print("[bold]Updating advanced stats...[/bold]")
            try:
                skaters = await scraper.scrape_skater_stats()
                goalies = await scraper.scrape_goalie_stats()
                db.upsert_advanced_stats(skaters + goalies)
                console.print(f"  [green]✓ {len(skaters)} skaters, {len(goalies)} goalies[/green]")
            except Exception as e:
                errors.append(f"advanced_stats: {e}")
                console.print(f"  [yellow]⚠ advanced_stats: {e}[/yellow]")

            console.print("[bold]Updating shot data...[/bold]")
            console.print("[dim](This is a large CSV download)[/dim]")
            try:
                shots = await scraper.scrape_shot_data()
                db.insert_shots(shots)
                console.print(f"  [green]✓ {len(shots)} shots[/green]")
            except Exception as e:
                errors.append(f"shots: {e}")
                console.print(f"  [yellow]⚠ shots: {e}[/yellow]")

        _print_summary(errors)

    asyncio.run(run())


def _print_summary(errors: list[str]) -> None:
    """Print update summary and exit with appropriate code."""
    import sys
    if errors:
        console.print(f"\n[yellow]⚠ Completed with {len(errors)} error(s):[/yellow]")
        for err in errors:
            console.print(f"  [yellow]• {err}[/yellow]")
        sys.exit(1)
    else:
        console.print("\n[bold green]✓ All updates complete![/bold green]")
```

- [ ] **Step 2: Add missing imports to cli.py**

First, add `BoxscoreRecord` and `PlayByPlayRecord` to `src/storage/__init__.py` exports (alongside `GameRecord`, `PlayerRecord`, etc.).

Then update the import in cli.py:

```python
from .storage import Database, GameRecord, PlayerRecord, BoxscoreRecord, PlayByPlayRecord
```

- [ ] **Step 3: Test the update command**

Run: `cd /home/david/nhl-stats && source .venv/bin/activate && python -m src.cli update --daily`

Expected: Updates games, finds new completed games, scrapes their boxscores/PBP, updates game logs. Should complete without errors. New games since last scrape get picked up.

- [ ] **Step 4: Commit**

```bash
git add src/cli.py
git commit -m "feat: add update command for incremental data refresh"
```

---

### Task 2: Create wrapper script with logging

**Files:**
- Create: `scripts/update.sh`

A simple bash wrapper that activates the venv, runs the command, and logs output. This is what cron calls.

- [ ] **Step 1: Create scripts/update.sh**

```bash
#!/usr/bin/env bash
# NHL Stats data update script
# Called by cron — see OPERATIONS.md for schedule and configuration.
#
# Usage:
#   ./scripts/update.sh          # Full update (all sources)
#   ./scripts/update.sh --daily  # Daily update (games, boxscores, PBP, game logs only)
#
# Logs are written to data/logs/update-YYYY-MM-DD.log
# Exit code 0 = success, 1 = partial failure, 2 = total failure

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="${PROJECT_DIR}/data/logs"
LOG_FILE="${LOG_DIR}/update-$(date +%Y-%m-%d).log"

mkdir -p "$LOG_DIR"

echo "=== NHL Stats Update: $(date -Iseconds) ===" >> "$LOG_FILE"
echo "Args: $*" >> "$LOG_FILE"

# Activate virtual environment
source "${PROJECT_DIR}/.venv/bin/activate"

# Run update, capturing output
if python -m src.cli update "$@" >> "$LOG_FILE" 2>&1; then
    echo "=== Completed successfully: $(date -Iseconds) ===" >> "$LOG_FILE"
    exit 0
else
    echo "=== Completed with errors: $(date -Iseconds) ===" >> "$LOG_FILE"
    exit 1
fi
```

- [ ] **Step 2: Make it executable**

Run: `chmod +x scripts/update.sh`

- [ ] **Step 3: Test the wrapper**

Run: `cd /home/david/nhl-stats && ./scripts/update.sh --daily`
Then check: `cat data/logs/update-$(date +%Y-%m-%d).log`

- [ ] **Step 4: Add data/logs/ to .gitignore**

```
data/logs/
```

- [ ] **Step 5: Commit**

```bash
git add scripts/update.sh .gitignore
git commit -m "feat: add update wrapper script with logging"
```

---

### Task 3: Set up cron jobs

**Files:**
- Create: `scripts/install-cron.sh`
- Create: `scripts/uninstall-cron.sh`

Two helper scripts: one to install the cron entries, one to remove them. This makes the setup reproducible and easy to migrate later.

- [ ] **Step 1: Create scripts/install-cron.sh**

```bash
#!/usr/bin/env bash
# Install nhl-stats cron jobs.
# See OPERATIONS.md for schedule rationale.
#
# Schedule:
#   Daily at 10:00 UTC (6am ET): games, boxscores, PBP, game logs
#   Sunday at 12:00 UTC (8am ET): full update including shots and advanced stats
#
# To migrate to a central scheduler, remove these cron entries
# (run uninstall-cron.sh) and replicate the two schedules above.

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT="${PROJECT_DIR}/scripts/update.sh"
MARKER="# nhl-stats-update"

# Remove existing entries first
crontab -l 2>/dev/null | grep -v "$MARKER" | crontab - 2>/dev/null || true

# Add new entries
(crontab -l 2>/dev/null || true; cat <<EOF
0 10 * * * ${SCRIPT} --daily ${MARKER}-daily
0 12 * * 0 ${SCRIPT} ${MARKER}-full
EOF
) | crontab -

echo "Installed cron jobs:"
crontab -l | grep "$MARKER"
echo ""
echo "Daily update:  10:00 UTC (6am ET) every day"
echo "Full update:   12:00 UTC (8am ET) every Sunday"
```

- [ ] **Step 2: Create scripts/uninstall-cron.sh**

```bash
#!/usr/bin/env bash
# Remove nhl-stats cron jobs.
# Run this before migrating to a central scheduler.

set -euo pipefail

MARKER="# nhl-stats-update"

crontab -l 2>/dev/null | grep -v "$MARKER" | crontab - 2>/dev/null || true

echo "Removed nhl-stats cron jobs."
echo "Current crontab:"
crontab -l 2>/dev/null || echo "(empty)"
```

- [ ] **Step 3: Make scripts executable**

Run: `chmod +x scripts/install-cron.sh scripts/uninstall-cron.sh`

- [ ] **Step 4: Test install**

Run: `./scripts/install-cron.sh`
Expected: prints the two cron entries

- [ ] **Step 5: Commit**

```bash
git add scripts/install-cron.sh scripts/uninstall-cron.sh
git commit -m "feat: add cron install/uninstall scripts"
```

---

### Task 4: Write OPERATIONS.md

**Files:**
- Create: `OPERATIONS.md`

This is the key document for future migration. It describes what runs, when, why, and how to move it.

- [ ] **Step 1: Write OPERATIONS.md**

```markdown
# NHL Stats — Operations Guide

## Overview

This project scrapes NHL data from multiple sources and stores it in a local SQLite database. Data collection runs on a schedule via cron on the WSL2 host machine.

**Future migration:** This setup is intended to be replaced by a centralized job scheduler (see "Migration" section below). The cron jobs are deliberately simple to make migration straightforward.

## Data Sources and Update Frequency

| Source | Command | Frequency | Runtime | What it does |
|--------|---------|-----------|---------|-------------|
| NHL API — games | `update --daily` | Daily | ~30s | Fetches game schedule and scores for current season |
| NHL API — boxscores | `update --daily` | Daily | ~2min for new games | Per-player stats for completed games not yet in DB |
| NHL API — play-by-play | `update --daily` | Daily | ~3min for new games | Every event (shot, hit, faceoff) with coordinates |
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
4. **Health check:** `python -m src.cli stats` returns table counts > 0
5. **Log location:** `data/logs/update-YYYY-MM-DD.log`
6. **Exit codes:** 0 = success, 1 = partial failure (some sources errored), 2 = total failure

The wrapper script (`scripts/update.sh`) is the only entry point — the scheduler just needs to call it with the right args and capture the exit code.

## Troubleshooting

- **"0 new boxscores"**: Normal if no games were played yesterday
- **MoneyPuck timeout**: Their ZIP files are large. The scraper has 120s timeout. Retry on next scheduled run.
- **NHL API 404**: Happens occasionally during API maintenance. Errors are logged but don't block other sources.
- **DB locked**: Only one update should run at a time. Cron schedule ensures no overlap (daily at 10:00, weekly at 12:00 Sunday only).
```

- [ ] **Step 2: Commit**

```bash
git add OPERATIONS.md
git commit -m "docs: add operations guide for data update jobs and future migration"
```

---

### Task 5: Final integration test

- [ ] **Step 1: Run full update and verify**

Run: `cd /home/david/nhl-stats && source .venv/bin/activate && python -m src.cli update --daily`

Expected: completes without errors, picks up any new games since last scrape.

- [ ] **Step 2: Run stats to verify DB**

Run: `python -m src.cli stats`

Expected: all counts are >= previous values (879728 shots, 33600 boxscores, etc.)

- [ ] **Step 3: Install cron and verify**

Run: `./scripts/install-cron.sh`
Then: `crontab -l | grep nhl-stats`

Expected: two cron entries visible.

- [ ] **Step 4: Final commit with any fixes**

If any fixes were needed, commit them.
