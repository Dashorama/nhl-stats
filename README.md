# NHL Stats

A comprehensive NHL statistics and analytics tool that collects data from multiple sources for analysis, visualization, and machine learning applications.

## Features

- **Multiple Data Sources**: NHL API, MoneyPuck, PuckPedia
- **Complete Data Coverage**: Rosters, stats, contracts, advanced analytics
- **Async & Rate-Limited**: Polite scraping with configurable rate limits
- **SQLite Storage**: Local database with easy export options
- **Rich CLI**: Beautiful terminal interface with progress tracking
- **Pydantic Models**: Type-safe data validation

## Quick Start

```bash
# Create venv and install
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e .

# Show current standings
nhl-stats standings

# Show team roster
nhl-stats show-roster TOR

# Scrape all data from all sources
nhl-stats scrape-full

# Check database stats
nhl-stats stats
```

## CLI Commands

### Basic Scraping
```bash
nhl-stats scrape-teams           # Fetch team data from NHL API
nhl-stats scrape-players         # Fetch player stats from NHL API
nhl-stats scrape-games           # Fetch game schedule
nhl-stats scrape-all             # Run all NHL API scrapers
```

### Extended Scraping
```bash
nhl-stats scrape-rosters [--team TOR]    # Full rosters from NHL API
nhl-stats scrape-advanced [--season 2024] # Advanced stats from MoneyPuck
nhl-stats scrape-contracts [--team TOR]   # Contract data from PuckPedia
nhl-stats scrape-full                     # ALL data from ALL sources
```

### Backfills & Validation
```bash
nhl-stats backfill-games                      # Repair games.season / game_date
nhl-stats backfill-shots --start-season 2018  # Re-ingest MoneyPuck shots (fixes situation, game_id)
nhl-stats backfill-pbp --start-season 2018    # Play-by-play + shift charts, resumable
nhl-stats validate                            # Integrity checks; exits non-zero on failure
```

Use `--db PATH` (or `NHL_STATS_DB_PATH`) to point any command at another database.

### Display Commands
```bash
nhl-stats standings              # Current NHL standings
nhl-stats show-roster TOR        # Display team roster table
nhl-stats show-player 8478402    # Player details by ID
nhl-stats stats                  # Database statistics
```

## Data Sources

| Source | Data | Rate Limit |
|--------|------|------------|
| NHL API | Official stats, schedules, rosters | 1-2 req/sec |
| MoneyPuck | Corsi, Fenwick, xG, zone starts, high-danger | 0.5 req/sec |
| PuckPedia | Contracts, cap hits, UFA/RFA status, clauses | 0.3 req/sec |

## Project Structure

```
nhl-stats/
├── src/
│   ├── scrapers/           # Data source modules
│   │   ├── base.py         # Abstract base with rate limiting
│   │   ├── nhl_api.py      # Official NHL API (basic)
│   │   ├── nhl_roster.py   # NHL API (full rosters, player details)
│   │   ├── moneypuck.py    # MoneyPuck advanced stats (CSV)
│   │   └── puckpedia.py    # PuckPedia contracts (HTML scraping)
│   ├── models/             # Pydantic data models
│   │   ├── player.py       # Player, PlayerStats, GoalieStats
│   │   ├── team.py         # Team, TeamStandings
│   │   ├── game.py         # Game, GameStats
│   │   ├── contract.py     # PlayerContract, ContractClause
│   │   ├── roster.py       # RosterPlayer, TeamRoster
│   │   └── advanced_stats.py # AdvancedSkaterStats, AdvancedGoalieStats
│   ├── storage/            # SQLite database
│   │   └── database.py     # 6 tables: players, teams, games, contracts, advanced_stats, rosters
│   └── cli.py              # Command-line interface
├── data/                   # SQLite database (created on first run)
├── docs/                   # Architecture documentation
│   └── EXPANSION_DESIGN.md # Design doc for expanded features
└── tests/                  # Test suite
```

## Data Models

### Core Entities
- **Player**: Bio, position, draft info, current team
- **Team**: Name, division, conference, venue
- **Game**: Schedule, scores, venue, attendance

### Rosters
- **RosterPlayer**: Full roster entry with position, jersey, bio
- **TeamRoster**: Complete team roster grouped by position

### Contracts
- **PlayerContract**: Salary, cap hit, term, UFA/RFA status
- **ContractClause**: NMC/NTC details

### Stats
- **PlayerStats**: Goals, assists, +/-, TOI, basic metrics
- **GoalieStats**: Wins, GAA, save %, starts
- **AdvancedSkaterStats**: Corsi, Fenwick, xG, zone starts, high-danger, PDO
- **AdvancedGoalieStats**: GSAE, save % by danger level, rebounds

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Type checking
mypy src

# Linting
ruff check src
```

## Example Usage

```python
import asyncio
from src.scrapers import NHLRosterScraper, MoneyPuckScraper

async def main():
    # Get full roster for a team
    async with NHLRosterScraper() as scraper:
        roster = await scraper.scrape_roster("TOR")
        for player in roster["forwards"]:
            print(f"{player['jersey_number']} - {player['first_name']} {player['last_name']}")
    
    # Get advanced stats
    async with MoneyPuckScraper() as scraper:
        stats = await scraper.scrape_skater_stats("2024")
        # Find top Corsi players
        top_corsi = sorted(stats, key=lambda x: x.get("corsi_pct") or 0, reverse=True)[:10]

asyncio.run(main())
```

## Database Schema

```sql
-- 6 tables with full indexing
players (id, first_name, last_name, position, team, ...)
teams (abbrev, name, conference, division, ...)
games (id, season, date, home_team, away_team, scores, ...)
contracts (player_name, team, cap_hit, aav, years, expiry_status, ...)
advanced_stats (player_id, season, corsi_*, fenwick_*, xg_*, ...)
rosters (team, player_id, season, jersey_number, position, status, ...)
```

## License

MIT
