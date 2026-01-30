# NHL Analytics Scraper - Architecture

## Overview

A comprehensive NHL data scraper that collects analytics from multiple sources for analysis, visualization, and machine learning applications.

## Data Sources

### 1. NHL Official API (Primary)
- **URL**: `https://api-web.nhle.com/` (new API), `https://statsapi.web.nhl.com/api/v1/` (legacy)
- **Data**: Live scores, schedules, rosters, official stats
- **Rate Limit**: Generous, but be polite (1 req/sec)

### 2. Hockey Reference
- **URL**: `https://www.hockey-reference.com/`
- **Data**: Historical stats, advanced metrics, career data
- **Rate Limit**: 3 sec between requests (robots.txt)

### 3. Natural Stat Trick
- **URL**: `https://www.naturalstattrick.com/`
- **Data**: Advanced analytics (Corsi, Fenwick, xG, zone entries)
- **Rate Limit**: Conservative (5 sec between requests)

### 4. MoneyPuck
- **URL**: `https://moneypuck.com/`
- **Data**: Expected goals models, win probabilities, player cards
- **Note**: Some data available as downloadable CSVs

### 5. Elite Prospects
- **URL**: `https://www.eliteprospects.com/`
- **Data**: Prospects, draft history, international leagues
- **Rate Limit**: Conservative (5 sec between requests)

### 6. CapFriendly/PuckPedia
- **URL**: `https://puckpedia.com/`
- **Data**: Salary cap data, contracts, buyouts
- **Rate Limit**: Conservative

## Data Models

### Core Entities

```
Player
├── id (NHL ID)
├── name, position, shoots, height, weight
├── birth_date, birth_city, nationality
├── current_team_id
└── draft_info (year, round, pick, team)

Team
├── id, name, abbreviation
├── division, conference
├── venue, location
└── founded_year

Game
├── id, season, game_type
├── date, home_team_id, away_team_id
├── final_score, periods[]
├── venue, attendance
└── officials[]

Season
├── id (e.g., "20232024")
├── regular_season_start/end
├── playoff_start/end
└── all_star_date
```

### Stats Entities

```
PlayerGameStats
├── player_id, game_id
├── goals, assists, points
├── plus_minus, pim, shots
├── toi, hits, blocks
├── faceoff_pct

PlayerSeasonStats
├── player_id, season_id, team_id
├── games_played, goals, assists
├── all basic + advanced stats

AdvancedPlayerStats
├── corsi_for/against/pct
├── fenwick_for/against/pct
├── expected_goals_for/against
├── zone_starts_pct
├── quality_of_competition

GoalieStats
├── player_id, game_id/season_id
├── wins, losses, otl
├── gaa, save_pct, shutouts
├── goals_saved_above_expected
```

### Historical/Draft

```
DraftPick
├── year, round, overall_pick
├── team_id, player_id
├── from_team (if traded)

Contract
├── player_id, team_id
├── start_year, end_year
├── aav, cap_hit
├── signing_bonus, performance_bonus
├── no_trade_clause, no_move_clause
```

## Architecture

```
nhl-scraper/
├── src/
│   ├── __init__.py
│   ├── scrapers/           # One module per source
│   │   ├── __init__.py
│   │   ├── base.py         # Abstract base scraper
│   │   ├── nhl_api.py      # Official NHL API
│   │   ├── hockey_ref.py   # Hockey Reference
│   │   ├── nst.py          # Natural Stat Trick
│   │   ├── moneypuck.py    # MoneyPuck
│   │   └── elite.py        # Elite Prospects
│   ├── models/             # Pydantic data models
│   │   ├── __init__.py
│   │   ├── player.py
│   │   ├── team.py
│   │   ├── game.py
│   │   └── stats.py
│   ├── storage/            # Data persistence
│   │   ├── __init__.py
│   │   ├── database.py     # SQLite/PostgreSQL
│   │   └── exports.py      # CSV/JSON export
│   └── utils/
│       ├── __init__.py
│       ├── rate_limiter.py
│       ├── cache.py
│       └── logging.py
├── tests/
├── data/                   # Local data storage
├── docs/
├── pyproject.toml
└── README.md
```

## Tech Stack

- **Python 3.11+** - Best ecosystem for scraping
- **httpx** - Modern async HTTP client
- **beautifulsoup4 + lxml** - HTML parsing
- **pydantic** - Data validation & models
- **SQLAlchemy** - Database ORM
- **SQLite** - Default storage (PostgreSQL optional)
- **tenacity** - Retry logic
- **structlog** - Structured logging

## Rate Limiting Strategy

```python
# Per-source rate limits (requests per second)
RATE_LIMITS = {
    "nhl_api": 1.0,      # 1 req/sec
    "hockey_ref": 0.33,  # 1 req/3sec
    "nst": 0.2,          # 1 req/5sec
    "moneypuck": 0.5,    # 1 req/2sec
    "elite": 0.2,        # 1 req/5sec
}
```

## Politeness Rules

1. Respect robots.txt
2. Use descriptive User-Agent
3. Cache aggressively
4. Prefer APIs over scraping when available
5. Run during off-peak hours for heavy jobs
6. Implement exponential backoff on errors

## Next Steps

1. Scaffold project with pyproject.toml
2. Implement base scraper with rate limiting
3. NHL API scraper first (most data, least restrictive)
4. Add Hockey Reference for historical depth
5. Natural Stat Trick for advanced analytics
6. Build storage layer
7. Create CLI for running scrapes
