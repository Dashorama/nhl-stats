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
