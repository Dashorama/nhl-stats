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
