#!/usr/bin/env python3
"""Fetch recent NHL news headlines from RSS feeds and write headlines.json."""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import feedparser

FEEDS = {
    "Sportsnet":        "https://www.sportsnet.ca/hockey/nhl/feed/",
    "ESPN":             "https://www.espn.com/espn/rss/nhl/news",
    "NHL Trade Rumors": "https://www.nhltraderumors.me/feeds/posts/default",
    "Last Word":        "https://lastwordonsports.com/hockey/feed/",
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
                # Extract structured team/player tags from <category> elements.
                # Skip generic content-type labels from Sportsnet and similar.
                _SKIP = {"Hockey", "NHL", "Predictions", "News", "Analysis",
                         "Game coverage - story", "Game coverage - recap",
                         "Game coverage - preview", "news", "Sports"}
                tags = [t.term for t in entry.get("tags", []) if t.term not in _SKIP
                        and not t.term.endswith("Predictions") and not t.term.endswith("predictions")]
                headlines.append({
                    "title": entry.get("title", ""),
                    "url": entry.get("link", ""),
                    "source": source,
                    "tags": tags,  # team/player names from feed categories
                })
        except Exception as e:
            print(f"[fetch_rss] {source} failed: {e}", file=sys.stderr)
    return headlines


def filter_headlines(headlines: list[dict], subject_name: str, team_abbrev: str = "") -> list[dict]:
    """Return up to 2 headlines relevant to subject_name or team.

    Prefers tag-based matching (structured) over title string matching.
    """
    name_lower = subject_name.lower()
    matched = []
    for h in headlines:
        # Tag match: structured team/player name in feed categories
        tag_hit = any(name_lower in t.lower() for t in h.get("tags", []))
        # Title match: fallback name search in headline text
        title_hit = name_lower in h["title"].lower()
        if tag_hit or title_hit:
            matched.append(h)
    return matched[:2]


def main():
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    headlines = fetch_all_headlines()
    OUTPUT_PATH.write_text(json.dumps(
        {"headlines": headlines, "fetched_at": datetime.utcnow().isoformat()},
        indent=2
    ))
    by_source = {}
    for h in headlines:
        by_source[h["source"]] = by_source.get(h["source"], 0) + 1
    print(f"[fetch_rss] wrote {len(headlines)} headlines: {by_source}")


if __name__ == "__main__":
    main()
