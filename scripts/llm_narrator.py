"""LLM-powered story narrator using a local Ollama model.

Receives raw stats data (shooters, teams, faceoffs, EDGE tracking,
career histories, headlines) and gives the LLM full creative freedom
to find the most interesting story.  Falls back gracefully when Ollama
is unreachable.
"""

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import date

from openai import OpenAI

logger = logging.getLogger(__name__)

# Default to the WSL→Windows host gateway; overridable via env
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://172.17.64.1:11434/v1")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "phi4:14b")
OLLAMA_TIMEOUT = float(os.environ.get("OLLAMA_TIMEOUT", "90"))

SYSTEM_PROMPT = """\
You are a sharp, data-driven NHL analyst writing a daily feature for a stats website.

You will receive a JSON object with today's raw data:
- **shooters**: every qualified skater's season stats (goals, expected goals, GAx, \
shot counts, high-danger %, rush %, rebound %, position)
- **career**: multi-season history per player (same metrics by season — look for \
trend shifts, breakouts, collapses, style changes)
- **teams**: every team's actual vs expected win rate
- **faceoffs**: faceoff win rates with offensive/defensive/neutral zone splits
- **tracking**: NHL EDGE data (skating speed, shot speed, OZ time, distance per game, \
all with league percentiles)
- **headlines**: recent hockey news from RSS feeds
- **recent_stories**: subjects covered in the last 7 days (AVOID repeating these)

YOUR JOB:
Find the single most interesting, surprising, or narratively compelling story in this \
data.  You have COMPLETE freedom — you are NOT limited to a fixed set of story types.

Some ideas (but don't limit yourself to these):
- A player whose style metrics shifted dramatically from career norms
- A faceoff specialist who is elite in one zone but terrible in another
- A team whose actual record wildly diverges from their underlying numbers
- A player combining elite skating speed with an elite shot
- A shooting outlier who is in the news today (pair stats with a headline)
- A veteran whose career trend tells an interesting arc
- An unlikely player quietly having a historically unusual season
- A contrast or rivalry between two players/teams in the data
- Anything else you notice that would make a good read

RULES:
- Pick ONE subject (a player_id or team abbrev from the data — do NOT invent names)
- Write a punchy headline (max 80 chars) that is NOT just "X is scoring above/below \
expectations" — be creative
- Write an informative body (2-4 sentences) with specific numbers from the data
- Write a social_text blurb (max 200 chars) for Bluesky
- Tone: confident, analytical, modern sports blog — not breathless hype
- Do NOT repeat a subject from recent_stories

Respond with ONLY valid JSON (no markdown, no commentary) in this exact schema:
{
  "subject_type": "player" or "team",
  "subject_id": <int player_id or string team abbrev>,
  "subject_name": "<full name>",
  "headline": "<string, max 80 chars>",
  "body": "<string, 2-4 sentences>",
  "social_text": "<string, max 200 chars>",
  "story_type": "<short label you invent, e.g. 'zone_split_faceoff', 'speed_vs_goals', etc>"
}"""


def _trim_shooters(shooters: list[dict], career: dict, limit: int = 40) -> list[dict]:
    """Pick the most story-worthy players to fit in the context window.

    Selects from multiple axes (extreme GAx, high HD%, high rush%, etc.)
    so the LLM has diverse angles to work with.
    """
    by_gax = sorted(shooters, key=lambda p: abs(p.get("gax", 0)), reverse=True)
    by_hd = sorted(shooters, key=lambda p: p.get("hd_shot_pct", 0), reverse=True)
    by_rush = sorted(shooters, key=lambda p: p.get("rush_rate", 0), reverse=True)
    by_rebound = sorted(shooters, key=lambda p: p.get("rebound_rate", 0), reverse=True)

    seen = set()
    result = []
    for source in [by_gax, by_hd, by_rush, by_rebound]:
        for p in source:
            pid = p["player_id"]
            if pid not in seen:
                seen.add(pid)
                entry = dict(p)
                # Attach career inline so the LLM sees trends
                if pid in career:
                    entry["career"] = career[pid]
                result.append(entry)
                if len(result) >= limit:
                    return result
    return result


def _trim_faceoffs(faceoff_stats: dict, limit: int = 15) -> list[dict]:
    """Pick the most interesting faceoff profiles."""
    if not faceoff_stats:
        return []
    entries = []
    for pid, fo in faceoff_stats.items():
        total = fo.get("fo_wins", 0) + fo.get("fo_losses", 0)
        if total < 200:
            continue
        pct = fo.get("fo_pct", 50)
        oz = fo.get("fo_oz_pct") or pct
        dz = fo.get("fo_dz_pct") or pct
        interest = abs(pct - 50) + abs(oz - dz) * 0.5
        entries.append({"player_id": pid, **fo, "_interest": interest})
    entries.sort(key=lambda x: x["_interest"], reverse=True)
    for e in entries:
        e.pop("_interest", None)
    return entries[:limit]


def _trim_tracking(edge_stats: dict, limit: int = 15) -> list[dict]:
    """Pick the most interesting EDGE tracking profiles."""
    if not edge_stats:
        return []
    entries = []
    for pid, e in edge_stats.items():
        score = max(
            e.get("max_speed_pct", 0),
            e.get("shot_speed_pct", 0),
            e.get("oz_percentile", 0),
            e.get("distance_pct", 0),
        )
        entries.append({"player_id": pid, **e, "_score": score})
    entries.sort(key=lambda x: x["_score"], reverse=True)
    for e in entries:
        e.pop("_score", None)
    return entries[:limit]


@dataclass
class LLMNarrator:
    base_url: str = OLLAMA_BASE_URL
    model: str = OLLAMA_MODEL
    timeout: float = OLLAMA_TIMEOUT

    def _client(self) -> OpenAI:
        return OpenAI(
            base_url=self.base_url,
            api_key="ollama",  # Ollama doesn't need a real key
            timeout=self.timeout,
        )

    def narrate(
        self,
        shooters: list[dict],
        teams: list[dict],
        career_stats: dict,
        faceoff_stats: dict | None,
        edge_stats: dict | None,
        headlines: list[dict],
        recent_subjects: list[dict],
        player_names: dict[int, str] | None = None,
    ) -> dict | None:
        """Give the LLM raw data and let it find the best story.

        Returns a story dict with headline/body/social_text/subject_id etc,
        or None if the LLM is unreachable or returns invalid output.
        """
        # Build a compact but rich data payload
        trimmed_shooters = _trim_shooters(shooters, career_stats)
        payload = {
            "date": str(date.today()),
            "shooters": trimmed_shooters,
            "teams": teams[:15],
            "faceoffs": _trim_faceoffs(faceoff_stats),
            "tracking": _trim_tracking(edge_stats),
            "headlines": [
                {"title": h.get("title", ""), "source": h.get("source", "")}
                for h in (headlines or [])[:20]
            ],
            "recent_stories": recent_subjects,
        }

        # Attach player names to faceoff/tracking entries so the LLM knows who they are
        name_map = player_names or {}
        if not name_map:
            name_map = {s["player_id"]: s["player_name"] for s in shooters}
        for section in [payload["faceoffs"], payload["tracking"]]:
            for entry in section:
                pid = entry.get("player_id")
                if pid and pid in name_map:
                    entry["player_name"] = name_map[pid]

        user_msg = json.dumps(payload, indent=2, default=str)
        logger.info("LLM prompt size: %d chars, %d shooters, %d faceoffs, %d tracking",
                     len(user_msg), len(trimmed_shooters),
                     len(payload["faceoffs"]), len(payload["tracking"]))

        try:
            client = self._client()
            resp = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.8,
                max_tokens=600,
            )
            raw = resp.choices[0].message.content.strip()

            # Strip markdown fences if the model wraps them anyway
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
                if raw.endswith("```"):
                    raw = raw[:-3]
                raw = raw.strip()

            result = json.loads(raw)

            # Validate required fields
            for key in ("subject_type", "subject_id", "headline", "body", "social_text"):
                if key not in result:
                    logger.warning("LLM response missing key '%s', falling back", key)
                    return None

            # Validate subject exists in the data we gave it
            sid = result["subject_id"]
            valid_player_ids = {s["player_id"] for s in shooters}
            valid_team_ids = {t["abbrev"] for t in teams}
            if faceoff_stats:
                valid_player_ids.update(faceoff_stats.keys())
            if edge_stats:
                valid_player_ids.update(int(k) for k in edge_stats.keys())

            if result["subject_type"] == "player" and sid not in valid_player_ids:
                # Try int coercion (JSON may stringify it)
                try:
                    sid = int(sid)
                    result["subject_id"] = sid
                except (ValueError, TypeError):
                    pass
                if sid not in valid_player_ids:
                    logger.warning("LLM picked unknown player_id %s, falling back", sid)
                    return None
            elif result["subject_type"] == "team" and sid not in valid_team_ids:
                logger.warning("LLM picked unknown team '%s', falling back", sid)
                return None

            # Check it didn't pick a recent subject
            recent_ids = {s.get("subject_id") for s in recent_subjects}
            if sid in recent_ids:
                logger.warning("LLM picked recently covered subject %s, falling back", sid)
                return None

            story = {
                "story_type": result.get("story_type", "llm_original"),
                "subject_type": result["subject_type"],
                "subject_id": result["subject_id"],
                "subject_name": result.get("subject_name", ""),
                "headline": str(result["headline"])[:120],
                "body": str(result["body"]),
                "social_text": str(result["social_text"])[:250],
                "headlines": [],
            }
            logger.info("LLM story (%s): %s — %s",
                        story["story_type"], story["subject_name"], story["headline"])
            return story

        except Exception:
            logger.warning("LLM narration failed, falling back to deterministic selection",
                           exc_info=True)
            return None
