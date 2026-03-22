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
