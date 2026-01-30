# NHL Analytics Scraper

A comprehensive NHL data scraper that collects analytics from multiple sources for analysis, visualization, and machine learning applications.

## Features

- **Multiple Data Sources**: NHL API, Hockey Reference, Natural Stat Trick, MoneyPuck, Elite Prospects
- **Async & Rate-Limited**: Polite scraping with configurable rate limits
- **SQLite Storage**: Local database with easy export options
- **Rich CLI**: Beautiful terminal interface with progress tracking
- **Pydantic Models**: Type-safe data validation

## Quick Start

```bash
# Install dependencies
pip install -e .

# Or with uv (recommended)
uv pip install -e .

# Show current standings
nhl-scraper standings

# Scrape all data
nhl-scraper scrape-all

# Check database stats
nhl-scraper stats
```

## CLI Commands

```bash
nhl-scraper --help              # Show all commands
nhl-scraper standings           # Current NHL standings
nhl-scraper scrape-teams        # Fetch team data
nhl-scraper scrape-players      # Fetch player stats
nhl-scraper scrape-games        # Fetch game schedule
nhl-scraper scrape-all          # Run all scrapers
nhl-scraper stats               # Database statistics
```

## Data Sources

| Source | Data | Rate Limit |
|--------|------|------------|
| NHL API | Official stats, schedules, rosters | 1 req/sec |
| Hockey Reference | Historical stats, advanced metrics | 1 req/3sec |
| Natural Stat Trick | Corsi, Fenwick, xG, zone data | 1 req/5sec |
| MoneyPuck | Expected goals models, predictions | 1 req/2sec |
| Elite Prospects | Prospects, draft, international | 1 req/5sec |

## Project Structure

```
nhl-scraper/
├── src/
│   ├── scrapers/       # Data source modules
│   │   ├── base.py     # Abstract base with rate limiting
│   │   └── nhl_api.py  # Official NHL API
│   ├── models/         # Pydantic data models
│   ├── storage/        # SQLite database
│   └── cli.py          # Command-line interface
├── data/               # SQLite database (created on first run)
├── docs/               # Architecture documentation
└── tests/              # Test suite
```

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Type checking
mypy src

# Linting
ruff check src
```

## Data Model

### Core Entities
- **Player**: Bio, position, draft info, current team
- **Team**: Name, division, conference, venue
- **Game**: Schedule, scores, venue, attendance

### Stats
- **PlayerStats**: Goals, assists, +/-, TOI, advanced metrics
- **GoalieStats**: Wins, GAA, save %, GSAE
- **TeamStats**: Standings, PP%, PK%, possession metrics

## License

MIT
