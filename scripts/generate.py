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
EDGE_STATS_PATH = PROJECT_DIR / "data/edge_stats.json"

# Season format constants — see plan docs
MONEYPUCK_SEASON = "2024"     # shots table: "2024" = 2024-25 season
NHL_API_SEASON   = "20242025"  # NOTE: games.season is NULL in DB; constant kept for future use


class Generator:
    def __init__(self, db_path=None, site_dir=None, history_path=None):
        self.db_path      = str(db_path or DEFAULT_DB)
        self.site_dir     = Path(site_dir or DEFAULT_SITE)
        self.history_path = str(history_path or DEFAULT_HISTORY)

    @contextmanager
    def _db(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _unavailable_players(self) -> dict[int, str]:
        with self._db() as conn:
            try:
                rows = conn.execute(
                    "SELECT player_id, status FROM injuries WHERE status IN ('IR','LTIR','SUSPENDED')"
                ).fetchall()
                return {r[0]: r[1] for r in rows}
            except sqlite3.OperationalError:
                return {}  # injuries table may not exist yet

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

            xg_rows = conn.execute("""
                SELECT team, SUM(x_goal) AS xgf
                FROM shots WHERE season=?
                GROUP BY team
            """, (MONEYPUCK_SEASON,)).fetchall()

        xgf_map = {r["team"]: r["xgf"] for r in xg_rows}
        total_xg = sum(xgf_map.values())
        num_teams = max(len(xgf_map), 1)

        team_rows_raw = []
        with self._db() as conn:
            # TODO: add WHERE season=NHL_API_SEASON once games.season is populated by the scraper
            team_rows_raw = conn.execute("""
                SELECT home_team AS team,
                       SUM(CASE WHEN home_score > away_score THEN 1.0 ELSE 0.0 END) / COUNT(*) AS win_pct,
                       COUNT(*) AS gp
                FROM games
                WHERE game_type='2' AND game_state='OFF'
                GROUP BY home_team
            """).fetchall()

            name_map = {r["abbrev"]: r["name"] for r in conn.execute(
                "SELECT abbrev, name FROM teams"
            ).fetchall()}

        teams = []
        for r in team_rows_raw:
            abbrev = r["team"]
            xgf = xgf_map.get(abbrev, 0)
            xga = (total_xg - xgf) / max(num_teams - 1, 1) if total_xg > 0 else 0
            xg_win_pct = xgf / (xgf + xga) if (xgf + xga) > 0 else 0.5
            diff = r["win_pct"] - xg_win_pct
            teams.append({
                "abbrev": abbrev,
                "name": name_map.get(abbrev, abbrev),
                "win_pct": round(r["win_pct"], 3),
                "xg_win_pct": round(xg_win_pct, 3),
                "diff": round(diff, 3),
            })
        teams.sort(key=lambda t: abs(t["diff"]), reverse=True)

        all_shooters = [
            {
                "player_id": r["shooter_id"],
                "player_name": r["shooter_name"],
                "team_abbrev": r["team"] or "",
                "goals": r["goals"],
                "xg": round(r["xg"], 1),
                "gax": round(r["gax"], 1),
                "shots": r["shots"],
            }
            for r in rows if r["shooter_id"] not in unavailable
        ]
        hot  = [s for s in all_shooters if s["gax"] > 0][:10]
        cold = sorted([s for s in all_shooters if s["gax"] < 0], key=lambda x: x["gax"])[:10]
        return {"hot_shooters": hot, "cold_shooters": cold, "teams": teams[:10], "all_teams": teams}

    def _query_story_data(self, teams: list) -> dict:
        unavailable = self._unavailable_players()
        with self._db() as conn:
            rows = conn.execute("""
                SELECT shooter_id, shooter_name, team,
                       SUM(goal)             AS goals,
                       SUM(x_goal)           AS xg,
                       SUM(goal)-SUM(x_goal) AS gax,
                       COUNT(*)              AS shots,
                       CAST(SUM(goal) AS FLOAT)/NULLIF(SUM(x_goal),0) AS sh_vs_exp,
                       CAST(SUM(CASE WHEN x_coord >= 69 AND ABS(y_coord) <= 22 THEN 1 ELSE 0 END) AS FLOAT)
                           / NULLIF(COUNT(*), 0)                       AS hd_shot_pct,
                       CAST(SUM(shot_rebound) AS FLOAT) / NULLIF(COUNT(*), 0) AS rebound_rate,
                       CAST(SUM(shot_rush)    AS FLOAT) / NULLIF(COUNT(*), 0) AS rush_rate
                FROM shots WHERE season=?
                GROUP BY shooter_id, shooter_name
                HAVING shots >= 50
            """, (MONEYPUCK_SEASON,)).fetchall()

        shooters = [
            {
                "player_id": r["shooter_id"],
                "player_name": r["shooter_name"],
                "team_abbrev": r["team"] or "",
                "goals": r["goals"],
                "xg": round(r["xg"], 1),
                "gax": round(r["gax"], 1),
                "shots": r["shots"],
                "sh_vs_expected": round(r["sh_vs_exp"] or 1.0, 2),
                "hd_shot_pct": round((r["hd_shot_pct"] or 0) * 100, 1),
                "rebound_rate": round((r["rebound_rate"] or 0) * 100, 1),
                "rush_rate": round((r["rush_rate"] or 0) * 100, 1),
            }
            for r in rows
        ]

        # Look up positions from players table in bulk
        shooter_ids = [s["player_id"] for s in shooters]
        if shooter_ids:
            with self._db() as conn:
                rows = conn.execute(
                    "SELECT id, position FROM players WHERE id IN ({})".format(
                        ",".join("?" * len(shooter_ids))
                    ),
                    shooter_ids,
                ).fetchall()
            positions = {r["id"]: r["position"] or "F" for r in rows}
            for s in shooters:
                s["position"] = positions.get(s["player_id"], "F")

        career: dict[int, list] = {}
        with self._db() as conn:
            for s in shooters:
                hist = conn.execute("""
                    SELECT season,
                           SUM(goal)             AS goals,
                           SUM(x_goal)           AS xg,
                           SUM(goal)-SUM(x_goal) AS gax,
                           COUNT(*)              AS shots,
                           CAST(SUM(goal) AS FLOAT)/NULLIF(SUM(x_goal),0) AS sh_vs_exp,
                           CAST(SUM(CASE WHEN x_coord >= 69 AND ABS(y_coord) <= 22 THEN 1 ELSE 0 END) AS FLOAT)
                               / NULLIF(COUNT(*), 0) AS hd_shot_pct,
                           CAST(SUM(shot_rebound) AS FLOAT) / NULLIF(COUNT(*), 0) AS rebound_rate,
                           CAST(SUM(shot_rush)    AS FLOAT) / NULLIF(COUNT(*), 0) AS rush_rate
                    FROM shots WHERE shooter_id=? GROUP BY season ORDER BY season
                """, (s["player_id"],)).fetchall()
                career[s["player_id"]] = [
                    {
                        "season": r["season"],
                        "goals": r["goals"],
                        "xg": round(r["xg"] or 0, 1),
                        "gax": round(r["gax"] or 0, 1),
                        "shots": r["shots"],
                        "sh_vs_expected": round(r["sh_vs_exp"] or 1.0, 2),
                        "hd_shot_pct": round((r["hd_shot_pct"] or 0) * 100, 1),
                        "rebound_rate": round((r["rebound_rate"] or 0) * 100, 1),
                        "rush_rate": round((r["rush_rate"] or 0) * 100, 1),
                    }
                    for r in hist
                ]

        return {
            "shooters": shooters,
            "teams": teams,
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
            team_abbrev = story["subject_id"]
            # Query team win% from games table
            with self._db() as conn:
                row = conn.execute("""
                    SELECT
                        SUM(CASE WHEN home_score > away_score THEN 1.0 ELSE 0.0 END) / COUNT(*) AS win_pct,
                        COUNT(*) AS gp
                    FROM games
                    WHERE home_team=? AND game_type='2' AND game_state='OFF'
                """, (team_abbrev,)).fetchone()

                # Compute xG win% from shots table
                xg_rows = conn.execute("""
                    SELECT team, SUM(x_goal) AS xgf
                    FROM shots WHERE season=?
                    GROUP BY team
                """, (MONEYPUCK_SEASON,)).fetchall()

            xgf_map = {r["team"]: r["xgf"] for r in xg_rows}
            total_xg = sum(xgf_map.values())
            num_teams = max(len(xgf_map), 1)
            team_xgf = xgf_map.get(team_abbrev, 0)
            team_xga = (total_xg - team_xgf) / max(num_teams - 1, 1) if total_xg > 0 else 0
            xg_win_pct = team_xgf / (team_xgf + team_xga) if (team_xgf + team_xga) > 0 else 0.5

            win_pct = row["win_pct"] if row and row["win_pct"] is not None else 0.5

            labels = ["Actual Win%", "Expected Win%"]
            values = [round(win_pct * 100, 1), round(xg_win_pct * 100, 1)]
            colors = ["#1a73e8", "#e8a21a"]
            y_pos = [0, 1]

            bars = ax.barh(y_pos, values, color=colors, height=0.5)
            ax.set_yticks(y_pos)
            ax.set_yticklabels(labels, fontsize=12)
            ax.set_xlim(0, max(values) * 1.25)
            ax.set_xlabel("Win %", fontsize=11)
            ax.set_title(f"{story.get('subject_name', team_abbrev)} — Actual vs Expected", fontsize=13)

            for bar, val in zip(bars, values):
                ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height() / 2,
                        f"{val:.1f}%", va="center", fontsize=11, fontweight="bold")

        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        plt.tight_layout()
        plt.savefig(chart_path, dpi=120, bbox_inches="tight")
        plt.close()
        return chart_name

    def _compute_faceoff_stats(self) -> dict[int, dict]:
        """Compute faceoff win rates by zone from play-by-play. Returns {player_id: stats}."""
        with self._db() as conn:
            rows = conn.execute("""
                SELECT
                    player_id,
                    SUM(won)          AS wins,
                    SUM(1 - won)      AS losses,
                    SUM(CASE WHEN zone_code='O' THEN won     ELSE 0 END) AS oz_wins,
                    SUM(CASE WHEN zone_code='O' THEN 1       ELSE 0 END) AS oz_total,
                    SUM(CASE WHEN zone_code='D' THEN won     ELSE 0 END) AS dz_wins,
                    SUM(CASE WHEN zone_code='D' THEN 1       ELSE 0 END) AS dz_total,
                    SUM(CASE WHEN zone_code='N' THEN won     ELSE 0 END) AS nz_wins,
                    SUM(CASE WHEN zone_code='N' THEN 1       ELSE 0 END) AS nz_total
                FROM (
                    SELECT player1_id AS player_id, zone_code, 1 AS won FROM play_by_play WHERE event_type='faceoff'
                    UNION ALL
                    SELECT player2_id AS player_id, zone_code, 0 AS won FROM play_by_play WHERE event_type='faceoff'
                )
                WHERE player_id IS NOT NULL
                GROUP BY player_id
                HAVING wins + losses >= 100
            """).fetchall()

        def pct(w, t):
            return round(100.0 * w / t, 1) if t else None

        return {
            r["player_id"]: {
                "fo_wins":    r["wins"],
                "fo_losses":  r["losses"],
                "fo_pct":     pct(r["wins"], r["wins"] + r["losses"]),
                "fo_oz_pct":  pct(r["oz_wins"], r["oz_total"]),
                "fo_dz_pct":  pct(r["dz_wins"], r["dz_total"]),
                "fo_nz_pct":  pct(r["nz_wins"], r["nz_total"]),
            }
            for r in rows
        }

    def _load_edge_stats(self) -> dict[int, dict]:
        """Load EDGE tracking stats keyed by player_id. Returns {} if file missing."""
        if not EDGE_STATS_PATH.exists():
            return {}
        try:
            raw = json.loads(EDGE_STATS_PATH.read_text())
            return {int(k): v for k, v in raw.items()}
        except Exception:
            return {}

    def _write_player_files(self, story_data: dict, rush_rates: dict[int, float], edge_stats: dict[int, dict], faceoff_stats: dict[int, dict]) -> None:
        out_dir = self.site_dir / "src/data/players"
        out_dir.mkdir(parents=True, exist_ok=True)
        for s in story_data["shooters"]:
            career = story_data["career_stats"].get(s["player_id"], [])
            if career:
                avg = sum(c["sh_vs_expected"] for c in career) / len(career)
                pct = abs(avg - 1) * 100
                direction = "above" if avg > 1 else "below"
                verdict = (
                    f"Career average {pct:.0f}% {direction} expected — "
                    f"{'watch for regression' if avg > 1 else 'due for improvement'}."
                )
            else:
                verdict = ""
            status = story_data.get("unavailable", {}).get(s["player_id"], "HEALTHY")
            # Override rush_rate with PBP-computed value if available
            player_data = {**s}
            if s["player_id"] in rush_rates:
                player_data["rush_rate"] = rush_rates[s["player_id"]]
                for season in career:
                    # Apply season-level rush rate only to current season (PBP is current only)
                    if season["season"] == "2025":
                        season["rush_rate"] = rush_rates[s["player_id"]]
            edge = edge_stats.get(s["player_id"])
            faceoffs = faceoff_stats.get(s["player_id"])
            (out_dir / f"{s['player_id']}.json").write_text(
                json.dumps({
                    **player_data,
                    "seasons": career,
                    "verdict": verdict,
                    "injury_status": status,
                    "tracking": edge,
                    "faceoffs": faceoffs,
                }, indent=2)
            )

    def _compute_rush_rates(self) -> dict[int, float]:
        """Compute rush shot rate per player from play-by-play data.

        Rush = unblocked shot within 4 seconds of a neutral/defensive zone event,
        with no stoppage in between. Returns {player_id: rush_rate_pct}.
        """
        with self._db() as conn:
            # Pull all events for the current season's games, ordered for processing
            rows = conn.execute("""
                SELECT p.game_id, p.event_id, p.event_type, p.zone_code,
                       p.time_in_period, p.period, p.player1_id
                FROM play_by_play p
                WHERE p.event_type IN (
                    'shot-on-goal','missed-shot','goal',
                    'faceoff','hit','giveaway','takeaway','stoppage',
                    'blocked-shot','penalty'
                )
                ORDER BY p.game_id, p.period, p.event_id
            """).fetchall()

        def to_seconds(t: str | None) -> int:
            if not t:
                return 0
            parts = t.split(":")
            return int(parts[0]) * 60 + int(parts[1])

        # Group events by game+period, walk sequentially
        from collections import defaultdict
        shot_types = {"shot-on-goal", "missed-shot", "goal"}
        stop_types = {"stoppage", "faceoff", "period-start", "period-end"}

        rush_shots: dict[int, int] = defaultdict(int)
        total_shots: dict[int, int] = defaultdict(int)

        # Build per-game-period event lists
        game_period_events: dict[tuple, list] = defaultdict(list)
        for r in rows:
            game_period_events[(r["game_id"], r["period"])].append(r)

        for events in game_period_events.values():
            for i, ev in enumerate(events):
                if ev["event_type"] not in shot_types:
                    continue
                shooter_id = ev["player1_id"]
                if not shooter_id:
                    continue
                total_shots[shooter_id] += 1

                # Look back for prior event (skip other shots, keep zone/stop events)
                shot_time = to_seconds(ev["time_in_period"])
                is_rush = False
                for j in range(i - 1, max(i - 10, -1), -1):
                    prev = events[j]
                    if prev["event_type"] in stop_types:
                        break  # stoppage resets rush
                    if prev["event_type"] in shot_types:
                        continue  # skip consecutive shots
                    prev_time = to_seconds(prev["time_in_period"])
                    if shot_time - prev_time > 4:
                        break
                    if prev["zone_code"] in ("N", "D"):
                        is_rush = True
                        break
                if is_rush:
                    rush_shots[shooter_id] += 1

        return {
            pid: round(100.0 * rush_shots[pid] / total_shots[pid], 1)
            for pid in total_shots
            if total_shots[pid] > 0
        }

    def _write_team_files(self, leaderboard_teams: list) -> None:
        out_dir = self.site_dir / "src/data/teams"
        out_dir.mkdir(parents=True, exist_ok=True)
        # Build lookup from leaderboard xG data
        xg_by_abbrev = {t["abbrev"]: t for t in leaderboard_teams}
        with self._db() as conn:
            try:
                teams = conn.execute(
                    "SELECT abbrev, name, conference, division, raw_data FROM teams"
                ).fetchall()
            except sqlite3.OperationalError:
                return
        for t in teams:
            raw = json.loads(t["raw_data"]) if t["raw_data"] else {}
            xg = xg_by_abbrev.get(t["abbrev"], {})
            (out_dir / f"{t['abbrev']}.json").write_text(json.dumps({
                "abbrev": t["abbrev"],
                "name": t["name"],
                "conference": t["conference"],
                "division": t["division"],
                "current_season": {
                    "wins": raw.get("wins"),
                    "losses": raw.get("losses"),
                    "ot_losses": raw.get("ot_losses"),
                    "points": raw.get("points"),
                    "games_played": raw.get("games_played"),
                    "win_pct": xg.get("win_pct"),
                    "xg_win_pct": xg.get("xg_win_pct"),
                    "diff": xg.get("diff"),
                },
            }, indent=2))

    def _cleanup_old_charts(self) -> None:
        pub_dir = self.site_dir / "public/data"
        cutoff_ordinal = date.today().toordinal() - 30
        for f in pub_dir.glob("chart-*.png"):
            try:
                chart_date = date.fromisoformat(f.stem.replace("chart-", ""))
                if chart_date.toordinal() < cutoff_ordinal:
                    f.unlink()
            except ValueError:
                pass

    def run(self, injuries_available: bool, headlines: list) -> dict:
        pub_dir = self.site_dir / "public/data"
        pub_dir.mkdir(parents=True, exist_ok=True)

        leaderboard = self._query_leaderboard()
        story_data  = self._query_story_data(teams=leaderboard["teams"])

        selector = StorySelector(
            shooters=story_data["shooters"],
            teams=story_data["teams"],
            career_stats=story_data["career_stats"],
            headlines=headlines if injuries_available else [],
            unavailable_players=set(story_data["unavailable"].keys()) if injuries_available else set(),
            history_path=self.history_path,
        )
        story = selector.select()
        chart_name = self._generate_chart(story)

        story["chart"]      = chart_name
        story["date"]       = str(date.today())
        story["story_type"] = str(story["story_type"])

        (pub_dir / "leaderboard.json").write_text(
            json.dumps({**leaderboard, "date": str(date.today())}, indent=2)
        )
        (pub_dir / "story.json").write_text(json.dumps(story, indent=2))

        rush_rates = self._compute_rush_rates()
        edge_stats = self._load_edge_stats()
        faceoff_stats = self._compute_faceoff_stats()
        self._write_player_files(story_data, rush_rates, edge_stats, faceoff_stats)
        self._write_team_files(leaderboard_teams=leaderboard["all_teams"])
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
    g.run(injuries_available=not args.injuries_unavailable, headlines=headlines)
    sys.exit(0)
