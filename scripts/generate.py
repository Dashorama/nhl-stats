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
        return {"hot_shooters": hot, "cold_shooters": cold, "teams": teams[:10]}

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
            ax.text(0.5, 0.5, story["headline"], ha="center", va="center", wrap=True)
            ax.axis("off")

        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        plt.tight_layout()
        plt.savefig(chart_path, dpi=120, bbox_inches="tight")
        plt.close()
        return chart_name

    def _write_player_files(self, story_data: dict) -> None:
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
            (out_dir / f"{s['player_id']}.json").write_text(
                json.dumps({**s, "seasons": career, "verdict": verdict, "injury_status": status}, indent=2)
            )

    def _write_team_files(self) -> None:
        out_dir = self.site_dir / "src/data/teams"
        out_dir.mkdir(parents=True, exist_ok=True)
        with self._db() as conn:
            try:
                teams = conn.execute(
                    "SELECT abbrev, name, conference, division FROM teams"
                ).fetchall()
            except sqlite3.OperationalError:
                return  # teams table may not exist yet (e.g. empty test DB)
        for t in teams:
            (out_dir / f"{t['abbrev']}.json").write_text(json.dumps({
                "abbrev": t["abbrev"],
                "name": t["name"],
                "conference": t["conference"],
                "division": t["division"],
                "current_season": {},
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
    g.run(injuries_available=not args.injuries_unavailable, headlines=headlines)
    sys.exit(0)
