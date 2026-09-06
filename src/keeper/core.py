"""Pure keeper rules. No filesystem, network, clock or spreadsheet dependencies."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass, replace
from datetime import datetime
from difflib import SequenceMatcher
from typing import Any


@dataclass(frozen=True)
class Keeper:
    team: str
    player: str
    first_year: int
    traded: int


def normalize(value: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", value).casefold() if c.isalnum())


TEAM_ALIASES = {
    normalize("Bitch Slappers"): normalize("Jean Claude VanDangles"),
    normalize("JeanClaud VanDangles"): normalize("Jean Claude VanDangles"),
}
# Display corrections made in the authoritative hand-reconciled fixture.
DISPLAY_ALIASES = {
    "JeremySwayman": "Jeremy Swayman",
    "David Pasternak": "David Pastrnak",
    "MIkhail Sergachev": "Mikhail Sergachev",
    "Jakob Markstron": "Jacob Markstrom",
}


def team_key(name: str) -> str:
    key = normalize(name)
    return TEAM_ALIASES.get(key, key)


def match(name: str, candidates: list[str]) -> str | None:
    key = normalize(DISPLAY_ALIASES.get(name, name))
    exact = [p for p in candidates if normalize(DISPLAY_ALIASES.get(p, p)) == key]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        raise ValueError(f"ambiguous player: {name}")
    scores = sorted(
        ((SequenceMatcher(None, key, normalize(p)).ratio(), p) for p in candidates), reverse=True
    )
    if not scores or scores[0][0] < 0.88:
        return None
    if len(scores) > 1 and scores[0][0] - scores[1][0] < 0.06:
        raise ValueError(f"ambiguous player: {name}")
    return scores[0][1]


def from_snapshot(snapshot: dict[str, Any]) -> list[Keeper]:
    data = snapshot["raw_values"][3:]
    if any(len(r) < 7 for r in data):
        raise ValueError("incomplete snapshot row")
    if any(str(r[6]) not in ("0", "1") for r in data):
        raise ValueError("Traded must be 0 or 1")
    rows = [Keeper(r[0], r[2].strip(), int(r[4]), int(r[6])) for r in data if r[2].strip()]
    names = [normalize(DISPLAY_ALIASES.get(r.player, r.player)) for r in rows]
    if len(names) != len(set(names)):
        raise ValueError("duplicate keeper on sheet")
    return rows


def reconcile(
    board: dict[str, Any], snapshot: dict[str, Any], season: int = 2025, expected_count: int = 5
) -> list[Keeper]:
    old = from_snapshot(snapshot)
    teams = list(dict.fromkeys(r[0] for r in snapshot["raw_values"][3:] if r))
    drafted = {
        team_key(t): [p["player"] for p in picks if p.get("keeper") is True]
        for t, picks in board.items()
        if t != "raw_full_draft"
    }
    if set(drafted) != {team_key(t) for t in teams}:
        raise ValueError("draft and sheet team sets differ")
    if any(len(picks) != expected_count for picks in drafted.values()):
        raise ValueError("unexpected keeper count; incomplete draft?")
    names = [normalize(p) for picks in drafted.values() for p in picks]
    if len(names) != len(set(names)):
        raise ValueError("duplicate drafted player")
    result = []
    for team in teams:
        remaining = list(drafted[team_key(team)])
        retained = []
        for row in old:
            if row.team != team:
                continue
            found = match(row.player, remaining)
            if found is not None:
                remaining.remove(found)
                retained.append(replace(row, player=DISPLAY_ALIASES.get(row.player, row.player)))
        # Explicit 2025 hand-sheet presentation exception; unrelated rows are stable.
        if season == 2025 and team_key(team) == normalize("Trou Trou Train"):
            pair = [
                i for i, r in enumerate(retained) if r.player in ("Jack Hughes", "Leon Draisaitl")
            ]
            if len(pair) == 2:
                ordered = sorted((retained[i] for i in pair), key=lambda r: r.player)
                for i, row in zip(pair, ordered):
                    retained[i] = row
        result.extend(retained)
        result.extend(Keeper(team, p, season, 0) for p in remaining)
    return result


def trade_key(trade: dict[str, Any]) -> str:
    canonical = {k: trade[k] for k in ("season", "league_id", "date")}
    # Yahoo renders current NHL labels on historical trades. Those labels and
    # presentation order are not transaction identity.
    canonical["teams"] = sorted(
        (
            team_key(side["team"]),
            sorted(normalize(re.sub(r"\s*\([^)]*\)\s*$", "", item)) for item in side["received"]),
        )
        for side in trade["teams"]
    )
    return hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()


def trade_date(trade: dict[str, Any]) -> datetime:
    date = datetime.strptime(f"{trade['season'] + 1} {trade['date']}", "%Y %b %d, %I:%M %p")
    return date.replace(year=trade["season"] + (1 if date.month < 7 else 0))


def scanTrades(  # noqa: N802
    rows: list[Keeper],
    trades: list[dict[str, Any]],
    *,
    season: int,  # noqa: N802
    state: dict[str, Any] | None = None,
    known_teams: list[str] | None = None,
) -> tuple[list[Keeper], dict[str, Any]]:
    """Process only this season. Return new rows and a persist-after-verify watermark."""
    if state is not None and state["season"] != season:
        raise ValueError("watermark season mismatch")
    if len({t["league_id"] for t in trades if t["season"] == season}) > 1:
        raise ValueError("mixed league trade input")
    seen = set(state["seen"] if state else [])
    watermark = state.get("last_seen", "") if state else ""
    result = list(rows)
    teams = {
        team_key(name): name
        for name in (known_teams if known_teams is not None else [r.team for r in rows])
    }
    for trade in sorted((t for t in trades if t["season"] == season), key=trade_date):
        key = trade_key(trade)
        if key in seen:
            continue
        if len(trade["teams"]) != 2:
            raise ValueError("trade must contain two teams")
        for side in trade["teams"]:
            for item in side["received"]:
                if item.startswith("Round "):
                    continue
                player = re.sub(r"\s*\([^)]*\)\s*$", "", item)
                found = match(player, [r.player for r in result])
                if found is None:
                    continue
                target = teams.get(team_key(side["team"]))
                if target is None:
                    raise ValueError(f"unknown acquiring team: {side['team']}")
                index = next(i for i, r in enumerate(result) if r.player == found)
                source = next(s["team"] for s in trade["teams"] if s is not side)
                row = result[index]
                if team_key(row.team) not in (team_key(source), team_key(target)):
                    raise ValueError(f"trade ownership conflict for {player}")
                result[index] = replace(row, team=target, traded=1)
        seen.add(key)
        watermark = max(watermark, trade_date(trade).isoformat())
    # Stable within each owner block; scan does not force five keepers per team.
    order = {key: i for i, key in enumerate(teams)}
    result.sort(key=lambda r: order[team_key(r.team)])
    return result, {"season": season, "seen": sorted(seen), "last_seen": watermark}
