"""Daily story selection engine."""
import json
from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum
from pathlib import Path


class StoryType(str, Enum):
    NEWS_COMBO      = "news_combo"
    EXTREME_SHOOTER = "extreme_shooter"
    MULTI_SEASON    = "multi_season"
    TEAM_RECORD     = "team_record"
    FALLBACK        = "fallback"


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
