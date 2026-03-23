#!/usr/bin/env python3
"""Scrape NHL EDGE tracking stats for all current-season skaters.

Fetches max skating speed, top shot speed, offensive zone time, and total
distance skated from the NHL EDGE API. Writes results to data/edge_stats.json.
"""
import asyncio
import json
import sys
from pathlib import Path

import httpx

PROJECT_DIR = Path(__file__).parent.parent
DB_PATH = PROJECT_DIR / "data/nhl.db"
OUTPUT_PATH = PROJECT_DIR / "data/edge_stats.json"
SEASON = "20242025"
GAME_TYPE = 2
CONCURRENCY = 10  # simultaneous requests


def _get_player_ids() -> list[int]:
    """Return all player IDs who have shots in the current MoneyPuck season."""
    import sqlite3
    conn = sqlite3.connect(str(DB_PATH))
    rows = conn.execute(
        "SELECT DISTINCT shooter_id FROM shots WHERE season='2024' AND shooter_id IS NOT NULL"
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


def _parse(player_id: int, data: dict) -> dict | None:
    """Extract the fields we care about from a skater_detail response."""
    try:
        ss = data.get("skatingSpeed", {})
        speed_max = ss.get("speedMax", {})

        ts = data.get("topShotSpeed", {})

        zt = data.get("zoneTimeDetails", {})

        dist = data.get("totalDistanceSkated", {})

        return {
            "player_id": player_id,
            "max_speed_mph": round(speed_max.get("imperial", 0), 2),
            "max_speed_pct": round((speed_max.get("percentile") or 0) * 100, 1),
            "shot_speed_mph": round(ts.get("imperial", 0), 2),
            "shot_speed_pct": round((ts.get("percentile") or 0) * 100, 1),
            "oz_pct": round((zt.get("offensiveZonePctg") or 0) * 100, 1),
            "oz_percentile": round((zt.get("offensiveZonePercentile") or 0) * 100, 1),
            "distance_mi": round(dist.get("imperial", 0), 1),
            "distance_pct": round((dist.get("percentile") or 0) * 100, 1),
        }
    except Exception:
        return None


async def _fetch_one(client: httpx.AsyncClient, sem: asyncio.Semaphore, player_id: int) -> dict | None:
    url = f"https://api-web.nhle.com/v1/edge/skater-detail/{player_id}/{SEASON}/{GAME_TYPE}"
    async with sem:
        try:
            r = await client.get(url, timeout=15)
            if r.status_code == 404:
                return None  # player has no EDGE data (e.g. goalies, pre-tracking era)
            r.raise_for_status()
            return _parse(player_id, r.json())
        except Exception as e:
            print(f"[scrape_edge] {player_id} failed: {e}", file=sys.stderr)
            return None


async def main() -> None:
    player_ids = _get_player_ids()
    print(f"[scrape_edge] fetching EDGE data for {len(player_ids)} players...")

    sem = asyncio.Semaphore(CONCURRENCY)
    async with httpx.AsyncClient(headers={"User-Agent": "Mozilla/5.0"}, follow_redirects=True) as client:
        tasks = [_fetch_one(client, sem, pid) for pid in player_ids]
        results = await asyncio.gather(*tasks)

    stats = {str(r["player_id"]): r for r in results if r is not None}
    OUTPUT_PATH.write_text(json.dumps(stats, indent=2))
    print(f"[scrape_edge] wrote {len(stats)} records to {OUTPUT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
