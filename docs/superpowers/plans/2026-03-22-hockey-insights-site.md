# Hockey Insights Site Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a daily-updated public website for "smart casual" hockey fans that surfaces xG-based insights as readable narratives, with automated Bluesky posts and a Next.js frontend deployed to Vercel.

**Architecture:** Python pipeline scripts generate JSON data files daily from `nhl.db`, Next.js reads those files at build time to produce a static site, and Vercel hosts it. A `publish.sh` orchestrator runs after the existing `update.sh` cron job: scrape injuries → fetch RSS → generate JSON + chart → `vercel deploy` (Vercel builds in cloud) → post to Bluesky. Failures degrade gracefully without blocking the deploy.

**Tech Stack:** Python 3.11 (httpx, feedparser, matplotlib, atproto), SQLAlchemy (existing ORM), Next.js 14 (App Router, TypeScript, Tailwind CSS), Vercel CLI, pytest + pytest-asyncio

**Spec:** `docs/superpowers/specs/2026-03-21-hockey-insights-site-design.md`

---

## File Map

### New Python files

| File | Responsibility |
|---|---|
| `src/scrapers/nhl_injuries.py` | Scrape NHL roster API for player availability — standalone, does NOT extend BaseScraper |
| `scripts/fetch_rss.py` | Fetch TSN / Sportsnet / NHL.com RSS, write `site/public/data/headlines.json` |
| `scripts/story_selector.py` | Story selection engine: scores candidates, applies injury filter, deduplicates |
| `scripts/generate.py` | Query `nhl.db` with raw sqlite3, invoke StorySelector, generate chart PNG, write all JSON files |
| `scripts/social.py` | Upload chart to Bluesky, create post |
| `scripts/publish.sh` | Orchestrate all of the above + `vercel deploy` |

### New SQLAlchemy model

`InjuryRecord` added to `src/storage/database.py` alongside existing ORM models. `Database` gets three new methods: `upsert_injuries()`, `get_unavailable_players()`.

### New test files

| File | What it tests |
|---|---|
| `tests/test_nhl_injuries.py` | DB methods: upsert, overwrite, empty set; scraper: response parsing, error handling |
| `tests/test_story_selector.py` | All 5 story types, injury exclusion, 7-day dedup, fallback chains, required output keys |
| `tests/test_generate.py` | JSON output shapes, chart file written, `story_history.json` updated |
| `tests/test_social.py` | Mocked Bluesky client: correct text + image passed; skip when chart missing |

### New Next.js site (`site/`)

| File | Responsibility |
|---|---|
| `site/src/lib/data.ts` | Type-safe JSON loaders: `loadStory()`, `loadLeaderboard()`, `loadPlayer()`, `loadTeam()` |
| `site/src/components/StoryCard.tsx` | Featured story with chart image and optional news headlines |
| `site/src/components/Leaderboard.tsx` | `ShooterLeaderboard` and `TeamLeaderboard` components |
| `site/src/app/page.tsx` | Home page: story card + three leaderboards |
| `site/src/app/players/[id]/page.tsx` | Player profile: career xG table + verdict |
| `site/src/app/teams/[abbrev]/page.tsx` | Team page: xG for/against + win% vs xG-implied win% |

### Modified files

| File | Change |
|---|---|
| `src/storage/database.py` | Add `InjuryRecord` model, `upsert_injuries()`, `get_unavailable_players()` |
| `src/scrapers/__init__.py` | Export `NHLInjuriesScraper` |
| `src/cli.py` | Add `injuries` command |
| `scripts/install-cron.sh` | Add `publish.sh` at 10:30 UTC |
| `scripts/uninstall-cron.sh` | Remove `publish.sh` entry |
| `.gitignore` | Add `site/.next/`, `site/node_modules/` |

---

## JSON Data Contracts

These files are the interface between Python and Next.js. Both sides must agree on shape.

**`site/public/data/story.json`** (read at runtime by Next.js static pages)
```json
{
  "date": "2026-03-22",
  "story_type": "extreme_shooter",
  "headline": "Draisaitl is scoring at a historically unsustainable rate",
  "body": "Leon Draisaitl has scored 63 goals against an expected 37.4 this season...",
  "chart": "chart-2026-03-22.png",
  "subject_type": "player",
  "subject_id": 8478402,
  "subject_name": "Leon Draisaitl",
  "social_text": "Leon Draisaitl is scoring at 1.68x his expected goals — the highest rate of his career.",
  "headlines": [
    {"title": "Oilers recall forward", "url": "https://tsn.ca/...", "source": "TSN"}
  ]
}
```

**`site/public/data/leaderboard.json`**
```json
{
  "date": "2026-03-22",
  "hot_shooters": [
    {"player_id": 8478402, "player_name": "Leon Draisaitl", "goals": 63,
     "xg": 37.4, "gax": 25.6, "shots": 436, "team_abbrev": "EDM"}
  ],
  "cold_shooters": [...],
  "teams": [
    {"abbrev": "BUF", "name": "Buffalo Sabres", "win_pct": 0.623, "xg_win_pct": 0.495, "diff": 0.128}
  ]
}
```

**`site/src/data/players/{player_id}.json`** (read by `generateStaticParams` at build time)
```json
{
  "player_id": 8478402,
  "player_name": "Leon Draisaitl",
  "position": "C",
  "team_abbrev": "EDM",
  "seasons": [
    {"season": "2018", "goals": 50, "xg": 30.5, "gax": 19.5, "shots": 311, "sh_vs_expected": 1.64}
  ],
  "verdict": "Career average 40% above expected — watch for regression.",
  "injury_status": "HEALTHY"
}
```

**`site/src/data/teams/{abbrev}.json`**
```json
{
  "abbrev": "EDM",
  "name": "Edmonton Oilers",
  "conference": "Western",
  "division": "Pacific",
  "current_season": {
    "win_pct": 0.524,
    "xg_win_pct": 0.512,
    "xgf": 245.3,
    "xga": 221.1,
    "games_played": 72
  }
}
```

---

## Season Format Constants

Two tables use different formats. Always use these named constants — never hardcode:

```python
MONEYPUCK_SEASON = "2024"    # MoneyPuck shots table: "2024" = 2024-25 season
NHL_API_SEASON = "20242025"  # NHL API games table: "20242025"
```

---

## Task 1: Injuries table + scraper

**Files:**
- Modify: `src/storage/database.py`
- Create: `src/scrapers/nhl_injuries.py`
- Modify: `src/scrapers/__init__.py`
- Modify: `src/cli.py`
- Create: `tests/test_nhl_injuries.py`

- [ ] **Step 1: Write failing tests for the new DB methods**

Create `tests/test_nhl_injuries.py`:

```python
"""Tests for injury DB methods and scraper."""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch
from src.storage.database import Database


@pytest.fixture
def db(tmp_path):
    return Database(str(tmp_path / "test.db"))


def test_upsert_and_get_unavailable(db):
    records = [
        {"player_id": 1, "player_name": "Player A", "team_abbrev": "EDM",
         "status": "IR", "detail": "upper body"},
        {"player_id": 2, "player_name": "Player B", "team_abbrev": "TOR",
         "status": "HEALTHY", "detail": None},
        {"player_id": 3, "player_name": "Player C", "team_abbrev": "BOS",
         "status": "SUSPENDED", "detail": "match penalty"},
    ]
    db.upsert_injuries(records)
    unavailable = db.get_unavailable_players()
    assert 1 in unavailable    # IR → unavailable
    assert 2 not in unavailable  # HEALTHY → available
    assert 3 in unavailable    # SUSPENDED → unavailable


def test_upsert_overwrites_status(db):
    db.upsert_injuries([{"player_id": 1, "player_name": "Player A",
                         "team_abbrev": "EDM", "status": "IR", "detail": None}])
    db.upsert_injuries([{"player_id": 1, "player_name": "Player A",
                         "team_abbrev": "EDM", "status": "HEALTHY", "detail": None}])
    assert 1 not in db.get_unavailable_players()


def test_empty_db_returns_empty_set(db):
    assert db.get_unavailable_players() == set()


def test_dtd_player_is_available(db):
    db.upsert_injuries([{"player_id": 5, "player_name": "DTD Guy",
                         "team_abbrev": "MTL", "status": "DTD", "detail": None}])
    assert 5 not in db.get_unavailable_players()
```

- [ ] **Step 2: Run to confirm fail**

```bash
cd /home/david/nhl-stats
pytest tests/test_nhl_injuries.py -v
```

Expected: FAIL — `Database` has no `upsert_injuries` method yet.

- [ ] **Step 3: Add `InjuryRecord` model and DB methods to `src/storage/database.py`**

Add the model class after the existing model classes (before the `Database` class definition):

```python
class InjuryRecord(Base):
    """Player injury/availability snapshot."""

    __tablename__ = "injuries"

    player_id = Column(Integer, primary_key=True)
    player_name = Column(String(100))
    team_abbrev = Column(String(3))
    status = Column(String(20))   # 'IR', 'LTIR', 'DTD', 'SUSPENDED', 'HEALTHY'
    detail = Column(String(200))
    updated_at = Column(DateTime, default=datetime.utcnow)
```

Because `Base.metadata.create_all(self.engine)` is called in `Database.__init__`, the new table will be created automatically when a `Database` object is instantiated — no migration step needed.

Add these two methods to the `Database` class, following the existing `with self.get_session() as session:` pattern:

```python
def upsert_injuries(self, records: list[dict]) -> int:
    """Insert or update player availability records."""
    with self.get_session() as session:
        count = 0
        for r in records:
            existing = session.get(InjuryRecord, r["player_id"])
            if existing:
                existing.player_name = r["player_name"]
                existing.team_abbrev = r["team_abbrev"]
                existing.status = r["status"]
                existing.detail = r.get("detail")
                existing.updated_at = datetime.utcnow()
            else:
                session.add(InjuryRecord(
                    player_id=r["player_id"],
                    player_name=r["player_name"],
                    team_abbrev=r["team_abbrev"],
                    status=r["status"],
                    detail=r.get("detail"),
                    updated_at=datetime.utcnow(),
                ))
            count += 1
        session.commit()
    return count

def get_unavailable_players(self) -> set[int]:
    """Return player IDs that are IR, LTIR, or SUSPENDED."""
    with self.get_session() as session:
        rows = session.query(InjuryRecord).filter(
            InjuryRecord.status.in_(["IR", "LTIR", "SUSPENDED"])
        ).all()
        return {r.player_id for r in rows}
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
pytest tests/test_nhl_injuries.py -v
```

Expected: 4 PASSED

- [ ] **Step 5: Write the injury scraper**

`NHLInjuriesScraper` is **not** a `BaseScraper` subclass — it doesn't fit the player/team/games abstract interface and has no rate-limiter needs at this call volume. It's a standalone async class using `httpx` directly.

Create `src/scrapers/nhl_injuries.py`:

```python
"""Scraper for NHL player injury/availability status."""
import asyncio
from datetime import datetime

import httpx
import structlog

from ..storage.database import Database

logger = structlog.get_logger()

SOURCE_NAME = "nhl_injuries"
BASE_URL = "https://api-web.nhle.com/v1"

NHL_TEAMS = [
    "ANA","BOS","BUF","CAR","CBJ","CGY","CHI","COL","DAL","DET",
    "EDM","FLA","LAK","MIN","MTL","NJD","NSH","NYI","NYR","OTT",
    "PHI","PIT","SEA","SJS","STL","TBL","TOR","UTA","VAN","VGK",
    "WSH","WPG",
]

# NHL API rosterStatus → our status codes
STATUS_MAP = {
    "IR": "IR",
    "INJURED_RESERVE": "IR",
    "LONG_TERM_INJURED_RESERVE": "LTIR",
    "LTIR": "LTIR",
    "DAY_TO_DAY": "DTD",
    "ACTIVE": "HEALTHY",
    "SUSPENDED": "SUSPENDED",
}


class NHLInjuriesScraper:
    async def scrape_all(self, db: Database) -> dict:
        records = []
        errors = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            for team in NHL_TEAMS:
                try:
                    resp = await client.get(f"{BASE_URL}/roster/{team}/current")
                    resp.raise_for_status()
                    data = resp.json()
                    for group in ("forwards", "defensemen", "goalies"):
                        for player in data.get(group, []):
                            roster_status = player.get("rosterStatus", "ACTIVE")
                            status = STATUS_MAP.get(roster_status, "HEALTHY")
                            records.append({
                                "player_id": player["id"],
                                "player_name": (
                                    f"{player['firstName']['default']} "
                                    f"{player['lastName']['default']}"
                                ),
                                "team_abbrev": team,
                                "status": status,
                                "detail": None,
                            })
                except Exception as e:
                    logger.error("injury_scrape_failed", team=team, error=str(e))
                    errors.append(team)

        if records:
            db.upsert_injuries(records)

        logger.info("scraped_injuries", players=len(records), errors=len(errors))
        return {"players": len(records), "errors": errors}
```

- [ ] **Step 6: Export from `src/scrapers/__init__.py`**

Add to imports and `__all__`:

```python
from .nhl_injuries import NHLInjuriesScraper
```

- [ ] **Step 7: Add `injuries` CLI command to `src/cli.py`**

Following the pattern of existing commands:

```python
@main.command()
def injuries():
    """Update player injury/availability status."""
    import asyncio as _asyncio
    from .scrapers.nhl_injuries import NHLInjuriesScraper
    db = Database(get_db_path())
    errors = []
    try:
        scraper = NHLInjuriesScraper()
        result = _asyncio.run(scraper.scrape_all(db))
        click.echo(f"  ✓ {result['players']} players")
        if result["errors"]:
            errors.append(f"teams failed: {result['errors']}")
    except Exception as e:
        errors.append(f"injuries: {e}")
    _print_summary(errors)
```

- [ ] **Step 8: Smoke test the CLI command**

```bash
source .venv/bin/activate
python -m src.cli injuries
```

Expected: `✓ N players`

- [ ] **Step 9: Commit**

```bash
git add src/storage/database.py src/scrapers/nhl_injuries.py \
        src/scrapers/__init__.py src/cli.py tests/test_nhl_injuries.py
git commit -m "feat: add injuries scraper and DB table"
```

---

## Task 2: RSS headline fetcher

**Files:**
- Create: `scripts/fetch_rss.py`
- Create: `tests/test_fetch_rss.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_fetch_rss.py`:

```python
"""Tests for RSS headline fetcher."""
import pytest
from scripts.fetch_rss import filter_headlines


def test_filter_by_name():
    headlines = [
        {"title": "Oilers recall player", "url": "https://tsn.ca/1", "source": "TSN"},
        {"title": "Maple Leafs sign defenseman", "url": "https://tsn.ca/2", "source": "TSN"},
    ]
    result = filter_headlines(headlines, subject_name="Oilers")
    assert len(result) == 1
    assert result[0]["title"] == "Oilers recall player"


def test_filter_case_insensitive():
    headlines = [{"title": "DRAISAITL scores hat trick", "url": "https://x.com", "source": "NHL"}]
    result = filter_headlines(headlines, subject_name="Draisaitl")
    assert len(result) == 1


def test_filter_returns_max_two():
    headlines = [
        {"title": "Oilers win 1", "url": "a", "source": "TSN"},
        {"title": "Oilers win 2", "url": "b", "source": "TSN"},
        {"title": "Oilers win 3", "url": "c", "source": "TSN"},
    ]
    result = filter_headlines(headlines, subject_name="Oilers")
    assert len(result) == 2


def test_filter_no_match_returns_empty():
    headlines = [{"title": "NHL trade deadline recap", "url": "x", "source": "TSN"}]
    result = filter_headlines(headlines, subject_name="Canucks")
    assert result == []
```

- [ ] **Step 2: Run to confirm fail**

```bash
PYTHONPATH=. pytest tests/test_fetch_rss.py -v
```

Expected: ImportError

- [ ] **Step 3: Write `scripts/fetch_rss.py`**

```python
#!/usr/bin/env python3
"""Fetch recent NHL news headlines from RSS feeds and write headlines.json."""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import feedparser

FEEDS = {
    "TSN":       "https://www.tsn.ca/rss/nhl",
    "Sportsnet": "https://www.sportsnet.ca/feed/",
    "NHL":       "https://www.nhl.com/rss/news.xml",
}
MAX_AGE_HOURS = 48
OUTPUT_PATH = Path(__file__).parent.parent / "site/public/data/headlines.json"


def fetch_all_headlines() -> list[dict]:
    headlines = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=MAX_AGE_HOURS)
    for source, url in FEEDS.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                pub = entry.get("published_parsed")
                if pub:
                    pub_dt = datetime(*pub[:6], tzinfo=timezone.utc)
                    if pub_dt < cutoff:
                        continue
                headlines.append({
                    "title": entry.get("title", ""),
                    "url": entry.get("link", ""),
                    "source": source,
                })
        except Exception as e:
            print(f"[fetch_rss] {source} failed: {e}", file=sys.stderr)
    return headlines


def filter_headlines(headlines: list[dict], subject_name: str) -> list[dict]:
    """Return up to 2 headlines mentioning subject_name (case-insensitive)."""
    name_lower = subject_name.lower()
    return [h for h in headlines if name_lower in h["title"].lower()][:2]


def main():
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    headlines = fetch_all_headlines()
    OUTPUT_PATH.write_text(json.dumps(
        {"headlines": headlines, "fetched_at": datetime.utcnow().isoformat()},
        indent=2
    ))
    print(f"[fetch_rss] wrote {len(headlines)} headlines")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to confirm pass**

```bash
PYTHONPATH=. pytest tests/test_fetch_rss.py -v
```

Expected: 4 PASSED

- [ ] **Step 5: Install feedparser and smoke test**

```bash
pip install feedparser
PYTHONPATH=. python scripts/fetch_rss.py
```

Expected: `[fetch_rss] wrote N headlines`

- [ ] **Step 6: Commit**

```bash
git add scripts/fetch_rss.py tests/test_fetch_rss.py
git commit -m "feat: add RSS headline fetcher"
```

---

## Task 3: Story selection engine

**Files:**
- Create: `scripts/story_selector.py`
- Create: `tests/test_story_selector.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_story_selector.py`:

```python
"""Tests for story selection logic."""
import json
import pytest
from datetime import date
from scripts.story_selector import StorySelector, StoryType


SHOOTERS = [
    {"player_id": 1, "player_name": "Hot Shooter", "team_abbrev": "EDM",
     "goals": 63, "xg": 37.4, "gax": 25.6, "shots": 436, "sh_vs_expected": 1.68},
    {"player_id": 2, "player_name": "Cold Shooter", "team_abbrev": "TOR",
     "goals": 10, "xg": 25.0, "gax": -15.0, "shots": 200, "sh_vs_expected": 0.40},
    {"player_id": 3, "player_name": "Normal Player", "team_abbrev": "BOS",
     "goals": 30, "xg": 28.0, "gax": 2.0, "shots": 300, "sh_vs_expected": 1.07},
]

TEAMS = [
    {"abbrev": "BUF", "name": "Buffalo Sabres", "win_pct": 0.623, "xg_win_pct": 0.495, "diff": 0.128},
    {"abbrev": "VGK", "name": "Vegas Golden Knights", "win_pct": 0.449, "xg_win_pct": 0.535, "diff": -0.086},
]

CAREER_STATS = {
    1: [{"season": "2022", "sh_vs_expected": 1.50},
        {"season": "2023", "sh_vs_expected": 1.45},
        {"season": "2024", "sh_vs_expected": 1.68}],
    2: [{"season": "2022", "sh_vs_expected": 0.82},
        {"season": "2023", "sh_vs_expected": 0.75},
        {"season": "2024", "sh_vs_expected": 0.40}],
}

HEADLINES = [{"title": "Hot Shooter scores hat trick", "url": "https://tsn.ca/x", "source": "TSN"}]


@pytest.fixture
def selector(tmp_path):
    return StorySelector(
        shooters=SHOOTERS, teams=TEAMS, career_stats=CAREER_STATS,
        headlines=HEADLINES, unavailable_players=set(),
        history_path=str(tmp_path / "story_history.json"),
    )


def test_news_combo_is_highest_priority(selector):
    story = selector.select()
    assert story["story_type"] == StoryType.NEWS_COMBO
    assert story["subject_id"] == 1


def test_extreme_shooter_when_no_headlines(tmp_path):
    sel = StorySelector(
        shooters=SHOOTERS, teams=TEAMS, career_stats=CAREER_STATS,
        headlines=[], unavailable_players=set(),
        history_path=str(tmp_path / "h.json"),
    )
    story = sel.select()
    assert story["story_type"] == StoryType.EXTREME_SHOOTER


def test_injured_player_excluded(tmp_path):
    sel = StorySelector(
        shooters=SHOOTERS, teams=TEAMS, career_stats=CAREER_STATS,
        headlines=[], unavailable_players={1},  # Hot Shooter unavailable
        history_path=str(tmp_path / "h.json"),
    )
    story = sel.select()
    assert story.get("subject_id") != 1


def test_team_story_when_all_players_unavailable(tmp_path):
    sel = StorySelector(
        shooters=SHOOTERS, teams=TEAMS, career_stats=CAREER_STATS,
        headlines=[], unavailable_players={1, 2, 3},
        history_path=str(tmp_path / "h.json"),
    )
    story = sel.select()
    assert story["story_type"] == StoryType.TEAM_RECORD


def test_dedup_skips_recent_subject(tmp_path):
    history_path = tmp_path / "h.json"
    history_path.write_text(json.dumps({"stories": [
        {"date": str(date.today()), "subject_id": 1, "story_type": "extreme_shooter"}
    ]}))
    sel = StorySelector(
        shooters=SHOOTERS, teams=TEAMS, career_stats=CAREER_STATS,
        headlines=[], unavailable_players=set(),
        history_path=str(history_path),
    )
    story = sel.select()
    assert story.get("subject_id") != 1


def test_output_has_required_keys(selector):
    story = selector.select()
    for key in ("story_type", "headline", "body", "subject_type",
                "subject_id", "subject_name", "social_text", "headlines"):
        assert key in story, f"Missing key: {key}"


def test_record_writes_history(tmp_path):
    history_path = tmp_path / "h.json"
    sel = StorySelector(
        shooters=SHOOTERS, teams=TEAMS, career_stats=CAREER_STATS,
        headlines=[], unavailable_players=set(),
        history_path=str(history_path),
    )
    story = sel.select()
    sel.record(story)
    history = json.loads(history_path.read_text())
    assert len(history["stories"]) == 1
    assert history["stories"][0]["subject_id"] == story["subject_id"]
```

- [ ] **Step 2: Run to confirm fail**

```bash
PYTHONPATH=. pytest tests/test_story_selector.py -v
```

Expected: ImportError

- [ ] **Step 3: Implement `scripts/story_selector.py`**

```python
"""Daily story selection engine."""
import json
from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum
from pathlib import Path


class StoryType(str, Enum):
    NEWS_COMBO     = "news_combo"
    EXTREME_SHOOTER = "extreme_shooter"
    MULTI_SEASON   = "multi_season"
    TEAM_RECORD    = "team_record"
    FALLBACK       = "fallback"


@dataclass
class StorySelector:
    shooters: list[dict]
    teams: list[dict]
    career_stats: dict[int, list[dict]]
    headlines: list[dict]
    unavailable_players: set[int]
    history_path: str

    def _recent_subjects(self) -> set:
        try:
            history = json.loads(Path(self.history_path).read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            return set()
        cutoff = date.today() - timedelta(days=7)
        return {
            e["subject_id"]
            for e in history.get("stories", [])
            if date.fromisoformat(e["date"]) > cutoff
        }

    def _available(self, recent: set) -> list[dict]:
        return [
            s for s in self.shooters
            if s["player_id"] not in self.unavailable_players
            and s["player_id"] not in recent
        ]

    def _try_news_combo(self, available: list[dict]) -> dict | None:
        headline_text = " ".join(h["title"].lower() for h in self.headlines)
        for player in sorted(available, key=lambda p: abs(p["gax"]), reverse=True):
            last_name = player["player_name"].split()[-1].lower()
            if last_name in headline_text and abs(player["gax"]) >= 8:
                matched = [h for h in self.headlines if last_name in h["title"].lower()][:2]
                return self._player_story(player, StoryType.NEWS_COMBO, matched)
        return None

    def _try_extreme_shooter(self, available: list[dict]) -> dict | None:
        candidates = [p for p in available
                      if (p["gax"] > 12 or p["gax"] < -10) and p["shots"] >= 80]
        if not candidates:
            return None
        best = max(candidates, key=lambda p: abs(p["gax"]))
        return self._player_story(best, StoryType.EXTREME_SHOOTER)

    def _try_multi_season(self, available: list[dict]) -> dict | None:
        for player in sorted(available, key=lambda p: abs(p["gax"]), reverse=True):
            if player["shots"] < 60:
                continue
            history = self.career_stats.get(player["player_id"], [])
            if len(history) < 2:
                continue
            avg = sum(s["sh_vs_expected"] for s in history) / len(history)
            if avg > 1.3 or avg < 0.8:
                return self._player_story(player, StoryType.MULTI_SEASON)
        return None

    def _try_team_record(self, recent: set) -> dict | None:
        candidates = [t for t in self.teams
                      if abs(t["diff"]) > 0.10 and t["abbrev"] not in recent]
        if not candidates:
            return None
        best = max(candidates, key=lambda t: abs(t["diff"]))
        direction = "overperforming" if best["diff"] > 0 else "underperforming"
        return {
            "story_type": StoryType.TEAM_RECORD,
            "subject_type": "team",
            "subject_id": best["abbrev"],
            "subject_name": best["name"],
            "headline": f"{best['name']} are {direction} their underlying numbers",
            "body": (
                f"The {best['name']} have a {best['win_pct']:.1%} win rate, "
                f"but their shot quality suggests they should be around {best['xg_win_pct']:.1%}. "
                f"That {abs(best['diff']):.1%} gap is one of the largest in the league."
            ),
            "social_text": (
                f"The {best['name']} are {direction} their expected win rate by "
                f"{abs(best['diff']):.1%} — one of the biggest gaps in the NHL."
            ),
            "headlines": [],
        }

    def _player_story(self, player: dict, story_type: StoryType,
                      matched_headlines: list | None = None) -> dict:
        direction = "above" if player["gax"] > 0 else "below"
        pct = abs(player["sh_vs_expected"] - 1) * 100
        verdict = "won't last" if player["gax"] > 0 else "should improve"
        return {
            "story_type": story_type,
            "subject_type": "player",
            "subject_id": player["player_id"],
            "subject_name": player["player_name"],
            "headline": f"{player['player_name']} is scoring {pct:.0f}% {direction} expectations",
            "body": (
                f"{player['player_name']} has scored {player['goals']} goals against an expected "
                f"{player['xg']:.1f} this season ({player['gax']:+.1f} goals above expected). "
                f"Historical data suggests deviations this large tend to normalize."
            ),
            "social_text": (
                f"{player['player_name']} is scoring at {player['sh_vs_expected']:.2f}x expected "
                f"({player['gax']:+.1f} GAx). History says this {verdict}."
            ),
            "headlines": matched_headlines or [],
        }

    def _fallback(self, available: list[dict], recent: set) -> dict:
        if available:
            best = max(available, key=lambda p: abs(p["gax"]))
            return self._player_story(best, StoryType.FALLBACK)
        team_story = self._try_team_record(set())
        if team_story:
            return team_story
        return {
            "story_type": StoryType.FALLBACK,
            "subject_type": "none",
            "subject_id": None,
            "subject_name": "",
            "headline": "No story today",
            "body": "",
            "social_text": "",
            "headlines": [],
        }

    def select(self) -> dict:
        recent = self._recent_subjects()
        available = self._available(recent)
        return (
            self._try_news_combo(available)
            or self._try_extreme_shooter(available)
            or self._try_multi_season(available)
            or self._try_team_record(recent)
            or self._fallback(available, recent)
        )

    def record(self, story: dict) -> None:
        path = Path(self.history_path)
        try:
            history = json.loads(path.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            history = {"stories": []}
        history["stories"].append({
            "date": str(date.today()),
            "subject_id": story["subject_id"],
            "story_type": str(story["story_type"]),
        })
        cutoff = date.today() - timedelta(days=30)
        history["stories"] = [
            e for e in history["stories"]
            if date.fromisoformat(e["date"]) > cutoff
        ]
        path.write_text(json.dumps(history, indent=2))
```

- [ ] **Step 4: Run tests to confirm pass**

```bash
PYTHONPATH=. pytest tests/test_story_selector.py -v
```

Expected: 7 PASSED

- [ ] **Step 5: Commit**

```bash
git add scripts/story_selector.py tests/test_story_selector.py
git commit -m "feat: add story selection engine"
```

---

## Task 4: Data generator (`generate.py`)

**Files:**
- Create: `scripts/generate.py`
- Create: `tests/test_generate.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_generate.py`:

```python
"""Tests for generate.py output."""
import json
import pytest
from pathlib import Path
from unittest.mock import patch
from scripts.generate import Generator

MONEYPUCK_SEASON = "2024"


@pytest.fixture
def gen(tmp_path):
    site_dir = tmp_path / "site"
    data_dir = tmp_path / "data"
    data_dir.mkdir()  # required: story_history.json written here
    (site_dir / "public" / "data").mkdir(parents=True)
    (site_dir / "src" / "data" / "players").mkdir(parents=True)
    (site_dir / "src" / "data" / "teams").mkdir(parents=True)
    return Generator(
        db_path=str(tmp_path / "test.db"),
        site_dir=str(site_dir),
        history_path=str(data_dir / "story_history.json"),
    )


def _mock_gen(gen):
    """Patch all DB query methods to return empty/safe data."""
    return (
        patch.object(gen, "_query_leaderboard",
                     return_value={"hot_shooters": [], "cold_shooters": [], "teams": []}),
        patch.object(gen, "_query_story_data",
                     return_value={"shooters": [], "teams": [], "career_stats": {}, "unavailable": set()}),
        patch.object(gen, "_generate_chart", return_value="chart-2026-03-22.png"),
    )


def test_leaderboard_json_has_required_keys(gen):
    with *_mock_gen(gen):
        gen.run(injuries_available=False, headlines=[])
    lb = json.loads((Path(gen.site_dir) / "public/data/leaderboard.json").read_text())
    for key in ("date", "hot_shooters", "cold_shooters", "teams"):
        assert key in lb


def test_story_json_has_required_keys(gen):
    with *_mock_gen(gen):
        gen.run(injuries_available=False, headlines=[])
    story = json.loads((Path(gen.site_dir) / "public/data/story.json").read_text())
    for key in ("date", "story_type", "headline", "body", "chart", "subject_type", "social_text"):
        assert key in story


def test_history_written_after_run(gen):
    with *_mock_gen(gen):
        gen.run(injuries_available=False, headlines=[])
    assert Path(gen.history_path).exists()
```

- [ ] **Step 2: Run to confirm fail**

```bash
PYTHONPATH=. pytest tests/test_generate.py -v
```

Expected: ImportError

- [ ] **Step 3: Write `scripts/generate.py`**

```python
#!/usr/bin/env python3
"""Query nhl.db, select daily story, generate chart PNG, write all JSON data files."""
import json
import sqlite3
import sys
from contextlib import contextmanager
from datetime import date
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from scripts.story_selector import StorySelector

PROJECT_DIR = Path(__file__).parent.parent
DEFAULT_DB      = PROJECT_DIR / "data/nhl.db"
DEFAULT_SITE    = PROJECT_DIR / "site"
DEFAULT_HISTORY = PROJECT_DIR / "data/story_history.json"

# Season format constants — see plan header
MONEYPUCK_SEASON = "2024"    # shots table: "2024" = 2024-25 season
NHL_API_SEASON   = "20242025"  # games table: "20242025"


class Generator:
    def __init__(self, db_path=None, site_dir=None, history_path=None):
        self.db_path     = str(db_path or DEFAULT_DB)
        self.site_dir    = Path(site_dir or DEFAULT_SITE)
        self.history_path = str(history_path or DEFAULT_HISTORY)

    @contextmanager
    def _db(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _unavailable_players(self) -> set[int]:
        with self._db() as conn:
            try:
                rows = conn.execute(
                    "SELECT player_id FROM injuries WHERE status IN ('IR','LTIR','SUSPENDED')"
                ).fetchall()
                return {r[0] for r in rows}
            except sqlite3.OperationalError:
                return set()  # injuries table doesn't exist yet

    def _query_leaderboard(self) -> dict:
        unavailable = self._unavailable_players()
        with self._db() as conn:
            rows = conn.execute("""
                SELECT shooter_id, shooter_name, team,
                       SUM(goal)             AS goals,
                       SUM(x_goal)           AS xg,
                       SUM(goal)-SUM(x_goal) AS gax,
                       COUNT(*)              AS shots
                FROM shots WHERE season=?
                GROUP BY shooter_id, shooter_name
                HAVING shots >= 50
                ORDER BY gax DESC
            """, (MONEYPUCK_SEASON,)).fetchall()

            team_rows = conn.execute("""
                SELECT home_team AS team,
                       SUM(CASE WHEN home_score > away_score THEN 1.0 ELSE 0.0 END) / COUNT(*) AS win_pct,
                       COUNT(*) AS gp
                FROM games
                WHERE season=? AND game_type=2 AND game_state='OFF'
                GROUP BY home_team
            """, (NHL_API_SEASON,)).fetchall()

            xg_rows = conn.execute("""
                SELECT team,
                       SUM(x_goal) AS xgf,
                       COUNT(*) AS shots
                FROM shots WHERE season=?
                GROUP BY team
            """, (MONEYPUCK_SEASON,)).fetchall()

        # Build team xG-implied win% (rough: xGF / (xGF + xGA))
        xgf_map = {r["team"]: r["xgf"] for r in xg_rows}
        teams = []
        for r in team_rows:
            abbrev = r["team"]
            xgf = xgf_map.get(abbrev, 0)
            # Approximate xGA from opponents' shots
            total_xg = sum(xgf_map.values())
            xga = (total_xg - xgf) / max(len(xgf_map) - 1, 1) if xgf_map else 0
            xg_win_pct = xgf / (xgf + xga) if (xgf + xga) > 0 else 0.5
            diff = r["win_pct"] - xg_win_pct
            teams.append({
                "abbrev": abbrev,
                "name": abbrev,  # name filled in from teams table below
                "win_pct": round(r["win_pct"], 3),
                "xg_win_pct": round(xg_win_pct, 3),
                "diff": round(diff, 3),
            })

        # Fill in team names
        with self._db() as conn:
            name_map = {r["abbrev"]: r["name"] for r in conn.execute(
                "SELECT abbrev, name FROM teams"
            ).fetchall()}
        for t in teams:
            t["name"] = name_map.get(t["abbrev"], t["abbrev"])

        all_shooters = [
            {
                "player_id": r["shooter_id"],
                "player_name": r["shooter_name"],
                "team_abbrev": r["team"],
                "goals": r["goals"],
                "xg": round(r["xg"], 1),
                "gax": round(r["gax"], 1),
                "shots": r["shots"],
            }
            for r in rows if r["shooter_id"] not in unavailable
        ]
        hot  = [s for s in all_shooters if s["gax"] > 0][:10]
        cold = sorted([s for s in all_shooters if s["gax"] < 0], key=lambda x: x["gax"])[:10]
        return {"hot_shooters": hot, "cold_shooters": cold, "teams": sorted(teams, key=lambda t: abs(t["diff"]), reverse=True)[:10]}

    def _query_story_data(self) -> dict:
        unavailable = self._unavailable_players()
        with self._db() as conn:
            rows = conn.execute("""
                SELECT shooter_id, shooter_name, team,
                       SUM(goal)             AS goals,
                       SUM(x_goal)           AS xg,
                       SUM(goal)-SUM(x_goal) AS gax,
                       COUNT(*)              AS shots,
                       CAST(SUM(goal) AS FLOAT)/NULLIF(SUM(x_goal),0) AS sh_vs_exp
                FROM shots WHERE season=?
                GROUP BY shooter_id, shooter_name
                HAVING shots >= 50
            """, (MONEYPUCK_SEASON,)).fetchall()

        shooters = [
            {"player_id": r["shooter_id"], "player_name": r["shooter_name"],
             "team_abbrev": r["team"], "goals": r["goals"],
             "xg": round(r["xg"], 1), "gax": round(r["gax"], 1),
             "shots": r["shots"],
             "sh_vs_expected": round(r["sh_vs_exp"] or 1.0, 2)}
            for r in rows
        ]

        career: dict[int, list] = {}
        with self._db() as conn:
            for s in shooters:
                hist = conn.execute("""
                    SELECT season,
                           CAST(SUM(goal) AS FLOAT)/NULLIF(SUM(x_goal),0) AS sh_vs_exp
                    FROM shots WHERE shooter_id=? GROUP BY season ORDER BY season
                """, (s["player_id"],)).fetchall()
                career[s["player_id"]] = [
                    {"season": r["season"], "sh_vs_expected": round(r["sh_vs_exp"] or 1.0, 2)}
                    for r in hist
                ]

        leaderboard = self._query_leaderboard()
        return {
            "shooters": shooters,
            "teams": leaderboard["teams"],
            "career_stats": career,
            "unavailable": unavailable,
        }

    def _generate_chart(self, story: dict) -> str:
        chart_name = f"chart-{date.today()}.png"
        chart_path = self.site_dir / "public/data" / chart_name

        fig, ax = plt.subplots(figsize=(8, 4.5))
        if story["subject_type"] == "player":
            player_id = story["subject_id"]
            with self._db() as conn:
                rows = conn.execute("""
                    SELECT season, SUM(goal) AS g, SUM(x_goal) AS xg
                    FROM shots WHERE shooter_id=? GROUP BY season ORDER BY season
                """, (player_id,)).fetchall()
            seasons = [r["season"] for r in rows]
            goals   = [r["g"] for r in rows]
            xg      = [round(r["xg"], 1) for r in rows]
            x = range(len(seasons))
            ax.bar([i - 0.2 for i in x], goals, width=0.4, label="Goals",          color="#1a73e8")
            ax.bar([i + 0.2 for i in x], xg,    width=0.4, label="Expected Goals", color="#e8a21a")
            ax.set_xticks(list(x))
            ax.set_xticklabels([f"'{s[-2:]}" for s in seasons])
            ax.legend()
            ax.set_title(story["subject_name"])
            ax.set_ylabel("Goals")
        else:
            ax.text(0.5, 0.5, story["headline"], ha="center", va="center", wrap=True)
            ax.axis("off")

        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        plt.tight_layout()
        plt.savefig(chart_path, dpi=120, bbox_inches="tight")
        plt.close()
        return chart_name

    def _write_player_files(self, story_data: dict):
        out_dir = self.site_dir / "src/data/players"
        out_dir.mkdir(parents=True, exist_ok=True)
        for s in story_data["shooters"]:
            career = story_data["career_stats"].get(s["player_id"], [])
            if career:
                avg = sum(c["sh_vs_expected"] for c in career) / len(career)
                pct = abs(avg - 1) * 100
                direction = "above" if avg > 1 else "below"
                verdict = (f"Career average {pct:.0f}% {direction} expected — "
                           f"{'watch for regression' if avg > 1 else 'due for improvement'}.")
            else:
                verdict = ""
            status = "IR" if s["player_id"] in story_data.get("unavailable", set()) else "HEALTHY"
            (out_dir / f"{s['player_id']}.json").write_text(json.dumps(
                {**s, "seasons": career, "verdict": verdict, "injury_status": status}, indent=2
            ))

    def _write_team_files(self):
        out_dir = self.site_dir / "src/data/teams"
        out_dir.mkdir(parents=True, exist_ok=True)
        with self._db() as conn:
            teams = conn.execute(
                "SELECT abbrev, name, conference, division FROM teams"
            ).fetchall()
        for t in teams:
            (out_dir / f"{t['abbrev']}.json").write_text(json.dumps({
                "abbrev": t["abbrev"], "name": t["name"],
                "conference": t["conference"], "division": t["division"],
                "current_season": {},
            }, indent=2))

    def _cleanup_old_charts(self):
        pub_dir = self.site_dir / "public/data"
        cutoff = date.today().toordinal() - 30
        for f in pub_dir.glob("chart-*.png"):
            try:
                chart_date = date.fromisoformat(f.stem.replace("chart-", ""))
                if chart_date.toordinal() < cutoff:
                    f.unlink()
            except ValueError:
                pass

    def run(self, injuries_available: bool, headlines: list) -> dict:
        pub_dir = self.site_dir / "public/data"
        pub_dir.mkdir(parents=True, exist_ok=True)

        leaderboard = self._query_leaderboard()
        story_data  = self._query_story_data()

        selector = StorySelector(
            shooters=story_data["shooters"],
            teams=story_data["teams"],
            career_stats=story_data["career_stats"],
            headlines=headlines if injuries_available else [],
            unavailable_players=story_data["unavailable"] if injuries_available else set(),
            history_path=self.history_path,
        )
        story = selector.select()
        chart_name = self._generate_chart(story)
        story["chart"] = chart_name
        story["date"]  = str(date.today())
        story["story_type"] = str(story["story_type"])

        (pub_dir / "leaderboard.json").write_text(
            json.dumps({**leaderboard, "date": str(date.today())}, indent=2))
        (pub_dir / "story.json").write_text(json.dumps(story, indent=2))

        self._write_player_files(story_data)
        self._write_team_files()
        selector.record(story)
        self._cleanup_old_charts()

        print(f"[generate] {story['story_type']}: {story['headline']}")
        return story


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--injuries-unavailable", action="store_true")
    args = parser.parse_args()

    headlines_path = DEFAULT_SITE / "public/data/headlines.json"
    headlines = []
    if headlines_path.exists():
        data = json.loads(headlines_path.read_text())
        headlines = data.get("headlines", [])

    g = Generator()
    story = g.run(injuries_available=not args.injuries_unavailable, headlines=headlines)
    sys.exit(0)
```

- [ ] **Step 4: Install matplotlib and run tests**

```bash
pip install matplotlib
PYTHONPATH=. pytest tests/test_generate.py -v
```

Expected: 3 PASSED

- [ ] **Step 5: Smoke test against real DB**

```bash
PYTHONPATH=. python scripts/generate.py
ls site/public/data/
```

Expected: `leaderboard.json  story.json  chart-2026-*.png  headlines.json`

- [ ] **Step 6: Commit**

```bash
git add scripts/generate.py tests/test_generate.py
git commit -m "feat: add data generator"
```

---

## Task 5: Bluesky social poster

**Files:**
- Create: `scripts/social.py`
- Create: `tests/test_social.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_social.py`:

```python
"""Tests for Bluesky social poster."""
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from scripts.social import build_post_text, should_skip


def test_build_post_text_includes_social_text_and_url():
    story = {"social_text": "Draisaitl is hot.", "headline": "H"}
    text = build_post_text(story, site_url="https://example.com")
    assert "Draisaitl is hot." in text
    assert "https://example.com" in text


def test_should_skip_when_no_chart(tmp_path):
    story_path = tmp_path / "story.json"
    story_path.write_text(json.dumps({"chart": "chart-2026-03-22.png", "social_text": "x"}))
    chart_path = tmp_path / "chart-2026-03-22.png"
    # chart file does NOT exist
    assert should_skip(story_path, chart_path) is True


def test_should_skip_when_no_story_file(tmp_path):
    story_path = tmp_path / "story.json"
    chart_path = tmp_path / "chart.png"
    assert should_skip(story_path, chart_path) is True


def test_should_not_skip_when_all_present(tmp_path):
    story_path = tmp_path / "story.json"
    story_path.write_text(json.dumps({"chart": "chart.png", "social_text": "x", "headline": "H"}))
    chart_path = tmp_path / "chart.png"
    chart_path.write_bytes(b"fake png")
    assert should_skip(story_path, chart_path) is False
```

- [ ] **Step 2: Run to confirm fail**

```bash
PYTHONPATH=. pytest tests/test_social.py -v
```

Expected: ImportError

- [ ] **Step 3: Write `scripts/social.py`**

```python
#!/usr/bin/env python3
"""Post daily story to Bluesky."""
import json
import os
import sys
from pathlib import Path

from atproto import Client

PROJECT_DIR = Path(__file__).parent.parent
STORY_PATH  = PROJECT_DIR / "site/public/data/story.json"
SITE_URL    = os.environ.get("SITE_URL", "https://your-site.vercel.app")


def build_post_text(story: dict, site_url: str) -> str:
    return f"{story['social_text']}\n\n{site_url}"


def should_skip(story_path: Path, chart_path: Path) -> bool:
    if not story_path.exists():
        print("[social] no story.json, skipping", file=sys.stderr)
        return True
    if not chart_path.exists():
        print("[social] chart not found, skipping", file=sys.stderr)
        return True
    return False


def post(story: dict, chart_path: Path) -> None:
    client = Client()
    client.login(os.environ["BLUESKY_HANDLE"], os.environ["BLUESKY_APP_PASSWORD"])
    text = build_post_text(story, SITE_URL)
    with chart_path.open("rb") as f:
        img_data = f.read()
    result = client.send_image(text=text, image=img_data, image_alt=story["headline"])
    print(f"[social] posted: {result.uri}")


def main():
    story = json.loads(STORY_PATH.read_text())
    chart_path = PROJECT_DIR / "site/public/data" / story.get("chart", "")
    if should_skip(STORY_PATH, chart_path):
        sys.exit(0)
    try:
        post(story, chart_path)
    except Exception as e:
        print(f"[social] failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to confirm pass**

```bash
pip install atproto
PYTHONPATH=. pytest tests/test_social.py -v
```

Expected: 4 PASSED

- [ ] **Step 5: Commit**

```bash
git add scripts/social.py tests/test_social.py
git commit -m "feat: add Bluesky social poster"
```

---

## Task 6: `publish.sh` orchestrator

**Files:**
- Create: `scripts/publish.sh`
- Modify: `scripts/install-cron.sh`
- Modify: `scripts/uninstall-cron.sh`

The Vercel deploy uses `vercel deploy` (no `--prebuilt`) — Vercel receives the project directory including the generated JSON files and builds in the cloud. The cron machine needs only Python + Vercel CLI; Node.js is not required.

- [ ] **Step 1: Write `scripts/publish.sh`**

```bash
#!/usr/bin/env bash
# Publish pipeline: generate site data, deploy to Vercel, post to Bluesky.
# Runs after update.sh (cron 10:30 UTC). Each step fails independently.
#
# Required env vars: VERCEL_TOKEN, BLUESKY_HANDLE, BLUESKY_APP_PASSWORD, SITE_URL

set -uo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_FILE="${PROJECT_DIR}/data/logs/publish-$(date +%Y-%m-%d).log"
mkdir -p "${PROJECT_DIR}/data/logs"

log() { echo "[$(date -Iseconds)] $*" | tee -a "$LOG_FILE"; }

INJURIES_FLAG=""
SKIP_SOCIAL=""

log "=== Publish pipeline start ==="
source "${PROJECT_DIR}/.venv/bin/activate"

# Step 1: Scrape injuries (gates social posting on failure)
log "Scraping injuries..."
if python -m src.cli injuries >> "$LOG_FILE" 2>&1; then
    log "  injuries OK"
else
    log "  injuries FAILED — player stories and social post disabled"
    INJURIES_FLAG="--injuries-unavailable"
    SKIP_SOCIAL="1"
fi

# Step 2: Fetch RSS (non-fatal)
log "Fetching RSS..."
PYTHONPATH="${PROJECT_DIR}" python "${PROJECT_DIR}/scripts/fetch_rss.py" >> "$LOG_FILE" 2>&1 \
    || log "  RSS fetch failed (non-fatal)"

# Step 3: Generate data files (fatal — deploy without this is pointless)
log "Generating data files..."
if ! PYTHONPATH="${PROJECT_DIR}" python "${PROJECT_DIR}/scripts/generate.py" $INJURIES_FLAG >> "$LOG_FILE" 2>&1; then
    log "  generate FAILED — aborting"
    exit 1
fi

# Step 4: Deploy to Vercel (fatal)
log "Deploying to Vercel..."
if ! (cd "${PROJECT_DIR}/site" && vercel deploy --token "${VERCEL_TOKEN}" --yes >> "$LOG_FILE" 2>&1); then
    log "  deploy FAILED"
    exit 1
fi
log "  deploy OK"

# Step 5: Post to Bluesky (non-fatal; skipped if injuries unavailable)
if [ -n "$SKIP_SOCIAL" ]; then
    log "  Bluesky skipped (injury data unavailable)"
else
    log "Posting to Bluesky..."
    PYTHONPATH="${PROJECT_DIR}" SITE_URL="${SITE_URL:-}" \
        python "${PROJECT_DIR}/scripts/social.py" >> "$LOG_FILE" 2>&1 \
        && log "  Bluesky OK" \
        || log "  Bluesky failed (non-fatal)"
fi

log "=== Publish pipeline complete ==="
```

```bash
chmod +x scripts/publish.sh
```

- [ ] **Step 2: Update `install-cron.sh`** — add a second cron entry after the existing daily entry:

```bash
# Publish pipeline — 30 minutes after daily update
PUBLISH_JOB="30 10 * * * cd ${PROJECT_DIR} && bash scripts/publish.sh >> ${LOG_DIR}/cron.log 2>&1 # nhl-stats-publish"
(crontab -l 2>/dev/null | grep -v "nhl-stats-publish"; echo "$PUBLISH_JOB") | crontab -
```

- [ ] **Step 3: Update `uninstall-cron.sh`** — also strip the `nhl-stats-publish` line:

```bash
crontab -l 2>/dev/null | grep -v "nhl-stats-publish" | crontab -
```

- [ ] **Step 4: Commit**

```bash
git add scripts/publish.sh scripts/install-cron.sh scripts/uninstall-cron.sh
git commit -m "feat: add publish.sh pipeline orchestrator"
```

---

## Task 7: Next.js site scaffold + shared components

**Files:**
- Create: `site/` (entire Next.js project)

- [ ] **Step 1: Scaffold the Next.js app (non-interactively)**

```bash
cd /home/david/nhl-stats
npx create-next-app@latest site \
  --typescript \
  --tailwind \
  --app \
  --yes
```

The `--yes` flag skips all interactive prompts. This creates `site/src/app/` (with `src` directory) and `site/src/lib/` etc.

- [ ] **Step 2: Update `.gitignore`**

```bash
echo "site/.next/" >> .gitignore
echo "site/node_modules/" >> .gitignore
```

- [ ] **Step 3: Verify it builds**

```bash
cd site && npm run build && cd ..
```

Expected: successful build

- [ ] **Step 4: Write `site/src/lib/data.ts`**

```typescript
import path from "path";
import fs from "fs";

export interface Shooter {
  player_id: number;
  player_name: string;
  team_abbrev: string;
  goals: number;
  xg: number;
  gax: number;
  shots: number;
}

export interface TeamEntry {
  abbrev: string;
  name: string;
  win_pct: number;
  xg_win_pct: number;
  diff: number;
}

export interface Leaderboard {
  date: string;
  hot_shooters: Shooter[];
  cold_shooters: Shooter[];
  teams: TeamEntry[];
}

export interface Headline {
  title: string;
  url: string;
  source: string;
}

export interface Story {
  date: string;
  story_type: string;
  headline: string;
  body: string;
  chart: string;
  subject_type: string;
  subject_id: number | string | null;
  subject_name: string;
  social_text: string;
  headlines: Headline[];
}

export interface PlayerSeason {
  season: string;
  goals: number;
  xg: number;
  gax: number;
  shots: number;
  sh_vs_expected: number;
}

export interface Player {
  player_id: number;
  player_name: string;
  position: string;
  team_abbrev: string;
  seasons: PlayerSeason[];
  verdict: string;
  injury_status: string;
}

export interface Team {
  abbrev: string;
  name: string;
  conference: string;
  division: string;
  current_season: {
    win_pct?: number;
    xg_win_pct?: number;
    xgf?: number;
    xga?: number;
    games_played?: number;
  };
}

function readJson<T>(filePath: string): T {
  return JSON.parse(fs.readFileSync(filePath, "utf-8")) as T;
}

const PUBLIC_DATA = path.join(process.cwd(), "public", "data");
const SRC_DATA    = path.join(process.cwd(), "src", "data");

export function loadStory(): Story {
  return readJson<Story>(path.join(PUBLIC_DATA, "story.json"));
}

export function loadLeaderboard(): Leaderboard {
  return readJson<Leaderboard>(path.join(PUBLIC_DATA, "leaderboard.json"));
}

export function loadAllPlayerIds(): string[] {
  const dir = path.join(SRC_DATA, "players");
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir).filter(f => f.endsWith(".json")).map(f => f.replace(".json", ""));
}

export function loadPlayer(id: string): Player {
  return readJson<Player>(path.join(SRC_DATA, "players", `${id}.json`));
}

export function loadAllTeamAbbrevs(): string[] {
  const dir = path.join(SRC_DATA, "teams");
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir).filter(f => f.endsWith(".json")).map(f => f.replace(".json", ""));
}

export function loadTeam(abbrev: string): Team {
  return readJson<Team>(path.join(SRC_DATA, "teams", `${abbrev}.json`));
}
```

- [ ] **Step 5: Write `site/src/components/StoryCard.tsx`**

```tsx
import { Story } from "@/lib/data";

export function StoryCard({ story }: { story: Story }) {
  return (
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 mb-8">
      <p className="text-xs font-semibold uppercase tracking-widest text-blue-600 mb-2">
        Story of the Day · {story.date}
      </p>
      <h2 className="text-2xl font-bold text-gray-900 mb-4">{story.headline}</h2>
      {story.chart && (
        <div className="mb-4 rounded-xl overflow-hidden">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={`/data/${story.chart}`} alt={story.headline} className="w-full" />
        </div>
      )}
      <p className="text-gray-700 leading-relaxed mb-4">{story.body}</p>
      {story.headlines.length > 0 && (
        <div className="border-t border-gray-100 pt-4 mt-4">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
            Related
          </p>
          {story.headlines.map((h, i) => (
            <a key={i} href={h.url} target="_blank" rel="noopener noreferrer"
               className="block text-sm text-blue-600 hover:underline mb-1">
              {h.title}{" "}
              <span className="text-gray-400">— {h.source}</span>
            </a>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 6: Write `site/src/components/Leaderboard.tsx`**

```tsx
import Link from "next/link";
import { Shooter, TeamEntry } from "@/lib/data";

export function ShooterLeaderboard({
  title, players,
}: {
  title: string;
  players: Shooter[];
}) {
  return (
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
      <h3 className="font-bold text-gray-900 mb-3 text-sm uppercase tracking-wide">{title}</h3>
      <ul className="space-y-2">
        {players.slice(0, 8).map(p => (
          <li key={p.player_id} className="flex items-center justify-between text-sm">
            <Link href={`/players/${p.player_id}`}
                  className="text-blue-700 hover:underline font-medium">
              {p.player_name}
            </Link>
            <span className="text-gray-500 font-mono">
              {p.gax > 0 ? "+" : ""}{p.gax} GAx
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function TeamLeaderboard({ teams }: { teams: TeamEntry[] }) {
  return (
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
      <h3 className="font-bold text-gray-900 mb-3 text-sm uppercase tracking-wide">
        Record vs. Numbers
      </h3>
      <ul className="space-y-2">
        {teams.slice(0, 8).map(t => (
          <li key={t.abbrev} className="flex items-center justify-between text-sm">
            <Link href={`/teams/${t.abbrev}`}
                  className="text-blue-700 hover:underline font-medium">
              {t.name}
            </Link>
            <span className="font-mono text-gray-700">
              {t.diff > 0 ? "+" : ""}{(t.diff * 100).toFixed(1)}%
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
```

- [ ] **Step 7: Commit**

```bash
git add site/ .gitignore
git commit -m "feat: scaffold Next.js site with components and data loaders"
```

---

## Task 8: Home page

**Files:**
- Modify: `site/src/app/page.tsx`

- [ ] **Step 1: Generate real data files**

```bash
cd /home/david/nhl-stats
PYTHONPATH=. python scripts/fetch_rss.py
PYTHONPATH=. python scripts/generate.py
```

Expected: JSON files written to `site/public/data/` and `site/src/data/`

- [ ] **Step 2: Replace default `site/src/app/page.tsx`**

```tsx
import { loadStory, loadLeaderboard } from "@/lib/data";
import { StoryCard } from "@/components/StoryCard";
import { ShooterLeaderboard, TeamLeaderboard } from "@/components/Leaderboard";

export const dynamic = "force-static";

export default function Home() {
  const story = loadStory();
  const leaderboard = loadLeaderboard();

  return (
    <main className="max-w-4xl mx-auto px-4 py-10">
      <header className="mb-10">
        <h1 className="text-4xl font-black text-gray-900 tracking-tight">
          Hockey Numbers
        </h1>
        <p className="text-gray-500 mt-1">
          Daily xG insights. Updated every morning.
        </p>
      </header>

      <StoryCard story={story} />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <ShooterLeaderboard title="Running Hot" players={leaderboard.hot_shooters} />
        <ShooterLeaderboard title="Running Cold" players={leaderboard.cold_shooters} />
        <TeamLeaderboard teams={leaderboard.teams} />
      </div>
    </main>
  );
}
```

- [ ] **Step 3: Build and verify locally**

```bash
cd site && npm run build
```

Expected: successful build, no TypeScript errors

- [ ] **Step 4: Commit**

```bash
git add site/src/app/page.tsx
git commit -m "feat: add home page"
```

---

## Task 9: Player and team pages

**Files:**
- Create: `site/src/app/players/[id]/page.tsx`
- Create: `site/src/app/teams/[abbrev]/page.tsx`

- [ ] **Step 1: Write player page**

Create `site/src/app/players/[id]/page.tsx`:

```tsx
import { loadPlayer, loadAllPlayerIds } from "@/lib/data";

export async function generateStaticParams() {
  return loadAllPlayerIds().map(id => ({ id }));
}

export default function PlayerPage({ params }: { params: { id: string } }) {
  const player = loadPlayer(params.id);

  return (
    <main className="max-w-3xl mx-auto px-4 py-10">
      <p className="text-sm text-gray-500 mb-1">
        {player.team_abbrev} · {player.position}
      </p>
      <h1 className="text-3xl font-black text-gray-900 mb-2">{player.player_name}</h1>

      {player.injury_status !== "HEALTHY" && (
        <span className="inline-block bg-amber-100 text-amber-800 text-xs font-semibold px-2 py-1 rounded mb-4">
          {player.injury_status}
        </span>
      )}

      {player.verdict && (
        <p className="text-gray-600 mb-6 italic">{player.verdict}</p>
      )}

      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
        <h2 className="font-bold text-gray-700 mb-4 text-sm uppercase tracking-wide">
          Goals vs. Expected Goals by Season
        </h2>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-gray-400 text-left border-b">
              <th className="pb-2">Season</th>
              <th className="pb-2 text-right">Goals</th>
              <th className="pb-2 text-right">xG</th>
              <th className="pb-2 text-right">GAx</th>
              <th className="pb-2 text-right">Sh/Exp</th>
            </tr>
          </thead>
          <tbody>
            {player.seasons.map(s => (
              <tr key={s.season} className="border-b border-gray-50">
                <td className="py-2 text-gray-700">{s.season}</td>
                <td className="py-2 text-right font-mono">{s.goals}</td>
                <td className="py-2 text-right font-mono text-gray-500">{s.xg}</td>
                <td className="py-2 text-right font-mono">
                  {s.gax > 0 ? "+" : ""}{s.gax}
                </td>
                <td className="py-2 text-right font-mono text-gray-500">{s.sh_vs_expected}x</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}
```

- [ ] **Step 2: Write team page**

Create `site/src/app/teams/[abbrev]/page.tsx`:

```tsx
import { loadTeam, loadAllTeamAbbrevs } from "@/lib/data";

export async function generateStaticParams() {
  return loadAllTeamAbbrevs().map(abbrev => ({ abbrev }));
}

export default function TeamPage({ params }: { params: { abbrev: string } }) {
  const team = loadTeam(params.abbrev);
  const s = team.current_season;

  return (
    <main className="max-w-3xl mx-auto px-4 py-10">
      <p className="text-sm text-gray-500 mb-1">
        {team.conference} · {team.division}
      </p>
      <h1 className="text-3xl font-black text-gray-900 mb-6">{team.name}</h1>

      {s.win_pct != null && s.xg_win_pct != null && (
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 mb-6">
          <h2 className="font-bold text-gray-700 mb-4 text-sm uppercase tracking-wide">
            Record vs. Expected
          </h2>
          <div className="grid grid-cols-3 gap-4 text-center">
            <div>
              <p className="text-3xl font-black text-gray-900">
                {(s.win_pct * 100).toFixed(1)}%
              </p>
              <p className="text-xs text-gray-400 mt-1">Actual Win %</p>
            </div>
            <div>
              <p className="text-3xl font-black text-gray-500">
                {(s.xg_win_pct * 100).toFixed(1)}%
              </p>
              <p className="text-xs text-gray-400 mt-1">xG-Implied</p>
            </div>
            <div>
              {(() => {
                const diff = s.win_pct - s.xg_win_pct;
                return (
                  <p className="text-3xl font-black text-gray-900">
                    {diff > 0 ? "+" : ""}{(diff * 100).toFixed(1)}%
                  </p>
                );
              })()}
              <p className="text-xs text-gray-400 mt-1">Difference</p>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
```

- [ ] **Step 3: Build and verify routes**

```bash
cd site && npm run build 2>&1 | grep -E "players|teams|Route|page"
```

Expected: `/players/[id]` and `/teams/[abbrev]` in the build output with page count matching player/team JSON files.

- [ ] **Step 4: Commit**

```bash
git add site/src/app/players site/src/app/teams
git commit -m "feat: add player and team static pages"
```

---

## Task 10: Vercel deploy and cron setup

- [ ] **Step 1: Install Vercel CLI** (on cron machine if not present)

```bash
npm install -g vercel
```

- [ ] **Step 2: Create Vercel project**

```bash
cd /home/david/nhl-stats/site
vercel link
```

Follow prompts to link to a new or existing Vercel project. This creates `.vercel/project.json` (already gitignored by Vercel).

- [ ] **Step 3: Set environment variables in cron environment**

Generate a Vercel token at vercel.com → Settings → Tokens.
Create a Bluesky app password at bsky.app → Settings → App Passwords.

Add to `/home/david/.env.nhl-stats` (sourced by cron):

```bash
export VERCEL_TOKEN="your_vercel_token"
export BLUESKY_HANDLE="yourhandle.bsky.social"
export BLUESKY_APP_PASSWORD="xxxx-xxxx-xxxx-xxxx"
export SITE_URL="https://your-project.vercel.app"
```

Update `publish.sh` to source this file at the top (before the `log` function):

```bash
[ -f "${HOME}/.env.nhl-stats" ] && source "${HOME}/.env.nhl-stats"
```

- [ ] **Step 4: Test full pipeline end-to-end (dry run without posting)**

```bash
cd /home/david/nhl-stats
# Comment out the social step in publish.sh temporarily, or set SKIP_SOCIAL
SKIP_SOCIAL=1 bash scripts/publish.sh
```

Check `data/logs/publish-*.log` for errors.

- [ ] **Step 5: Run publish.sh for real**

```bash
bash scripts/publish.sh
```

Expected: all steps pass, Vercel deployment URL printed, Bluesky post visible.

- [ ] **Step 6: Update cron**

```bash
bash scripts/install-cron.sh
crontab -l
```

Expected: both `nhl-stats-update-daily` and `nhl-stats-publish` entries present.

- [ ] **Step 7: Push to GitHub**

```bash
git push origin main
```

---

## Verification Checklist

After Task 10, confirm all of the following before declaring done:

- [ ] `crontab -l` shows both cron entries
- [ ] `data/story_history.json` exists and contains today's entry
- [ ] `site/public/data/story.json` exists and has all required keys (date, headline, body, chart, social_text)
- [ ] `site/public/data/leaderboard.json` has non-empty `hot_shooters`, `cold_shooters`, `teams`
- [ ] Player JSON files exist under `site/src/data/players/`
- [ ] Team JSON files exist under `site/src/data/teams/`
- [ ] Vercel deployment URL is live and renders the home page with real data
- [ ] Story chart image is visible on home page
- [ ] Clicking a player name navigates to their profile page
- [ ] Bluesky account shows today's post with chart image attached
- [ ] `data/logs/publish-YYYY-MM-DD.log` shows all steps completed successfully
- [ ] Wait for next 10:30 UTC run and verify log again
