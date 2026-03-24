"""Daily story selection engine."""
import json
import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class StoryType(str, Enum):
    NEWS_COMBO      = "news_combo"
    EXTREME_SHOOTER = "extreme_shooter"
    MULTI_SEASON    = "multi_season"
    FACEOFF_KING    = "faceoff_king"
    STYLE_SHIFT     = "style_shift"
    SPEED_DEMON     = "speed_demon"
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
    faceoff_stats: dict[int, dict] | None = None
    edge_stats: dict[int, dict] | None = None

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

    def _headlines_for_player(self, player: dict) -> list[dict]:
        """Return headlines relevant to a player, preferring tag matches over title matches."""
        name_lower = player["player_name"].lower()
        last_name = name_lower.split()[-1]
        matched = []
        for h in self.headlines:
            tags_lower = [t.lower() for t in h.get("tags", [])]
            tag_hit = any(last_name in t for t in tags_lower) or any(name_lower in t for t in tags_lower)
            title_hit = last_name in h["title"].lower()
            if tag_hit or title_hit:
                # Prefer tag hits (more precise) by sorting them first
                matched.append((0 if tag_hit else 1, h))
        matched.sort(key=lambda x: x[0])
        return [h for _, h in matched[:2]]

    def _try_news_combo(self, available: list[dict]) -> dict | None:
        # Build a quick index: team name → headlines with that tag
        team_tagged: dict[str, list[dict]] = {}
        for h in self.headlines:
            for tag in h.get("tags", []):
                team_tagged.setdefault(tag, []).append(h)

        headline_text = " ".join(h["title"].lower() for h in self.headlines)
        for player in sorted(available, key=lambda p: abs(p["gax"]), reverse=True):
            if abs(player["gax"]) < 8:
                continue
            matched = self._headlines_for_player(player)
            if matched:
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

    def _try_faceoff_king(self, recent: set) -> dict | None:
        """Find a player dominating (or struggling in) the faceoff circle."""
        if not self.faceoff_stats:
            return None
        candidates = []
        for pid, fo in self.faceoff_stats.items():
            if pid in self.unavailable_players or pid in recent:
                continue
            total = fo.get("fo_wins", 0) + fo.get("fo_losses", 0)
            pct = fo.get("fo_pct")
            if total < 300 or pct is None:
                continue
            # Look for extreme zone splits or overall dominance
            oz = fo.get("fo_oz_pct") or pct
            dz = fo.get("fo_dz_pct") or pct
            zone_gap = abs(oz - dz)
            if pct >= 56.0 or pct <= 43.0 or zone_gap >= 12.0:
                candidates.append((pid, fo, pct, zone_gap))
        if not candidates:
            return None
        # Prefer most extreme overall, breaking ties with zone gap
        best_pid, best_fo, best_pct, best_gap = max(
            candidates, key=lambda x: (abs(x[2] - 50.0), x[3])
        )
        # Find player name from shooters list, or fall back
        name = str(best_pid)
        for s in self.shooters:
            if s["player_id"] == best_pid:
                name = s["player_name"]
                break
        direction = "dominating" if best_pct > 50 else "struggling in"
        oz_pct = best_fo.get("fo_oz_pct")
        dz_pct = best_fo.get("fo_dz_pct")
        zone_detail = ""
        if oz_pct is not None and dz_pct is not None and abs(oz_pct - dz_pct) >= 8:
            stronger, weaker = ("offensive", "defensive") if oz_pct > dz_pct else ("defensive", "offensive")
            zone_detail = (
                f" Notably, he wins {max(oz_pct, dz_pct):.1f}% in the {stronger} zone "
                f"but just {min(oz_pct, dz_pct):.1f}% in the {weaker} zone."
            )
        total = best_fo["fo_wins"] + best_fo["fo_losses"]
        return {
            "story_type": StoryType.FACEOFF_KING,
            "subject_type": "player",
            "subject_id": best_pid,
            "subject_name": name,
            "headline": f"{name} is {direction} the faceoff circle at {best_pct:.1f}%",
            "body": (
                f"{name} has won {best_fo['fo_wins']} of {total} faceoffs this season "
                f"({best_pct:.1f}%).{zone_detail}"
            ),
            "social_text": (
                f"{name} is winning {best_pct:.1f}% of faceoffs this season — "
                f"{'one of the best rates in the NHL.' if best_pct > 50 else 'among the lowest in the league.'}"
            ),
            "headlines": [],
        }

    def _try_style_shift(self, available: list[dict]) -> dict | None:
        """Find a player whose shooting style changed dramatically this season vs career."""
        for player in sorted(available, key=lambda p: p["shots"], reverse=True):
            if player["shots"] < 80:
                continue
            history = self.career_stats.get(player["player_id"], [])
            if len(history) < 2:
                continue
            # Compare current season to career average for style metrics
            prior = [s for s in history if s["season"] != history[-1]["season"]]
            if not prior:
                continue
            current = history[-1]
            for metric, label, unit in [
                ("hd_shot_pct", "high-danger shot rate", "%"),
                ("rush_rate", "rush shot rate", "%"),
                ("rebound_rate", "rebound shot rate", "%"),
            ]:
                curr_val = current.get(metric)
                prior_vals = [s.get(metric) for s in prior if s.get(metric) is not None]
                if curr_val is None or not prior_vals:
                    continue
                avg_prior = sum(prior_vals) / len(prior_vals)
                if avg_prior < 1.0:  # avoid division by near-zero
                    continue
                change_pct = ((curr_val - avg_prior) / avg_prior) * 100
                if abs(change_pct) >= 30:
                    direction = "up" if change_pct > 0 else "down"
                    return {
                        "story_type": StoryType.STYLE_SHIFT,
                        "subject_type": "player",
                        "subject_id": player["player_id"],
                        "subject_name": player["player_name"],
                        "headline": (
                            f"{player['player_name']}'s {label} is way {direction} this season"
                        ),
                        "body": (
                            f"{player['player_name']}'s {label} has shifted to {curr_val:.1f}{unit} "
                            f"this season, {direction} from a career average of {avg_prior:.1f}{unit}. "
                            f"That's a {abs(change_pct):.0f}% change in playing style."
                        ),
                        "social_text": (
                            f"{player['player_name']}'s {label} is {direction} {abs(change_pct):.0f}% "
                            f"from career norms. Something has changed."
                        ),
                        "headlines": [],
                    }
        return None

    def _try_speed_demon(self, recent: set) -> dict | None:
        """Find a player with elite or unusual EDGE tracking numbers."""
        if not self.edge_stats:
            return None
        candidates = []
        for pid, edge in self.edge_stats.items():
            if pid in self.unavailable_players or pid in recent:
                continue
            speed_pct = edge.get("max_speed_pct", 0)
            shot_speed_pct = edge.get("shot_speed_pct", 0)
            oz_pctl = edge.get("oz_percentile", 0)
            dist_pct = edge.get("distance_pct", 0)
            # Look for elite speed + high shot speed, or extreme OZ presence
            if speed_pct >= 85 and shot_speed_pct >= 80:
                score = speed_pct + shot_speed_pct
                candidates.append((pid, edge, "fast_shot", score))
            elif oz_pctl >= 90 and dist_pct >= 80:
                score = oz_pctl + dist_pct
                candidates.append((pid, edge, "workload", score))
        if not candidates:
            return None
        best_pid, best_edge, kind, _ = max(candidates, key=lambda x: x[3])
        # Find player name
        name = str(best_pid)
        for s in self.shooters:
            if s["player_id"] == best_pid:
                name = s["player_name"]
                break
        if kind == "fast_shot":
            headline = f"{name} combines elite speed with a lethal shot"
            body = (
                f"{name} hits {best_edge['max_speed_mph']:.1f} mph top speed "
                f"({best_edge['max_speed_pct']:.0f}th percentile) and fires shots at "
                f"{best_edge['shot_speed_mph']:.1f} mph ({best_edge['shot_speed_pct']:.0f}th percentile). "
                f"That combination of skating and shooting is rare."
            )
            social = (
                f"{name}: {best_edge['max_speed_mph']:.1f} mph skating "
                f"+ {best_edge['shot_speed_mph']:.1f} mph shot. Elite at both."
            )
        else:
            headline = f"{name} leads the league in offensive zone presence"
            body = (
                f"{name} spends {best_edge['oz_pct']:.1f}% of his time in the offensive zone "
                f"({best_edge['oz_percentile']:.0f}th percentile) while covering "
                f"{best_edge['distance_mi']:.1f} miles per game ({best_edge['distance_pct']:.0f}th percentile). "
                f"That's an exceptional workload in the attacking end."
            )
            social = (
                f"{name}: {best_edge['oz_pct']:.1f}% OZ time "
                f"({best_edge['oz_percentile']:.0f}th %ile) and {best_edge['distance_mi']:.1f} mi/game. "
                f"A true offensive zone presence."
            )
        return {
            "story_type": StoryType.SPEED_DEMON,
            "subject_type": "player",
            "subject_id": best_pid,
            "subject_name": name,
            "headline": headline,
            "body": body,
            "social_text": social,
            "headlines": [],
        }

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

    def candidates(self) -> list[dict]:
        """Gather all qualifying story candidates (used by LLM narrator)."""
        recent = self._recent_subjects()
        available = self._available(recent)
        results = []
        for fn in [
            lambda: self._try_news_combo(available),
            lambda: self._try_extreme_shooter(available),
            lambda: self._try_faceoff_king(recent),
            lambda: self._try_style_shift(available),
            lambda: self._try_speed_demon(recent),
            lambda: self._try_multi_season(available),
            lambda: self._try_team_record(recent),
        ]:
            result = fn()
            if result is not None:
                results.append(result)
        return results

    def select(self) -> dict:
        recent = self._recent_subjects()
        available = self._available(recent)
        return (
            self._try_news_combo(available)
            or self._try_extreme_shooter(available)
            or self._try_faceoff_king(recent)
            or self._try_style_shift(available)
            or self._try_speed_demon(recent)
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
