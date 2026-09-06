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
# Known misspellings for matching only; output always uses the draft board.
NAME_ALIASES = {
    "JeremySwayman": "Jeremy Swayman",
    "David Pasternak": "David Pastrnak",
    "MIkhail Sergachev": "Mikhail Sergachev",
    "Jakob Markstron": "Jacob Markstrom",
    "Mathew Tkachuk": "Matthew Tkachuk",
}


def team_key(name: str) -> str:
    key = normalize(name)
    return TEAM_ALIASES.get(key, key)


def match(name: str, candidates: list[str]) -> str | None:
    key = normalize(NAME_ALIASES.get(name, name))
    exact = [p for p in candidates if normalize(NAME_ALIASES.get(p, p)) == key]
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
    if any(re.fullmatch(r"[0-9]+", str(r[6])) is None for r in data):
        raise ValueError("Traded count must be a nonnegative integer")
    rows = [Keeper(r[0], r[2].strip(), int(r[4]), int(r[6])) for r in data if r[2].strip()]
    names = [normalize(NAME_ALIASES.get(r.player, r.player)) for r in rows]
    if len(names) != len(set(names)):
        raise ValueError("duplicate keeper on sheet")
    return rows


def reconcile(
    board: dict[str, Any],
    snapshot: dict[str, Any],
    season: int = 2025,
    expected_count: int = 5,
    *,
    warnings: list[str] | None = None,
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
    # Resolve globally before assignment: ownership changes never restart a contract.
    contracts = {}
    used = set()
    for picks in drafted.values():
        for player in picks:
            found = match(player, [row.player for row in old])
            if found is not None:
                if found in used:
                    raise ValueError("multiple drafted players match the same sheet keeper")
                used.add(found)
                if warnings is not None and normalize(
                    NAME_ALIASES.get(player, player)
                ) != normalize(NAME_ALIASES.get(found, found)):
                    warnings.append(
                        f"fuzzy player-name match: {player} -> {found}; "
                        "verify same person before trusting FYK/count"
                    )
                contracts[player] = next(row for row in old if row.player == found)
    result = []
    for team in teams:
        picks = drafted[team_key(team)]
        # Existing contracts follow original sheet order, including incoming keepers.
        retained = sorted(
            (p for p in picks if p in contracts), key=lambda p: old.index(contracts[p])
        )
        for player in retained:
            row = contracts[player]
            if team_key(row.team) != team_key(team) and warnings is not None:
                warnings.append(
                    f"possible unrecorded trade: {player} sheet-team {row.team} -> "
                    f"draft-team {team}; FYK/count carried, verify bonus"
                )
            result.append(replace(row, team=team, player=player))
        result.extend(Keeper(team, p, season, 0) for p in picks if p not in contracts)
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
    warnings: list[str] | None = None,
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
    histories: dict[str, list[tuple[str, str, str]]] = {}
    pending = []
    queued = set(seen)
    for trade in sorted((t for t in trades if t["season"] == season), key=trade_date):
        key = trade_key(trade)
        if key in queued:
            continue
        queued.add(key)
        if len(trade["teams"]) != 2:
            raise ValueError("trade must contain two teams")
        transferred: set[str] = set()
        events = []
        for side in trade["teams"]:
            for item in side["received"]:
                if item.startswith("Round "):
                    continue
                player = re.sub(r"\s*\([^)]*\)\s*$", "", item)
                found = match(player, [r.player for r in rows])
                if found is None:
                    continue
                if found in transferred:
                    raise ValueError("duplicate keeper in trade")
                transferred.add(found)
                if warnings is not None and normalize(
                    NAME_ALIASES.get(player, player)
                ) != normalize(NAME_ALIASES.get(found, found)):
                    warnings.append(
                        f"fuzzy player-name match: {player} -> {found}; "
                        "verify same person before trusting FYK/count"
                    )
                target = teams.get(team_key(side["team"]))
                if target is None:
                    raise ValueError(f"unknown acquiring team: {side['team']}")
                source = team_key(next(s["team"] for s in trade["teams"] if s is not side))
                histories.setdefault(found, []).append((source, team_key(target), key))
                events.append((found, source, target))
        pending.append((trade, key, events))
    reflected: set[tuple[str, str]] = set()
    if state is None:
        for row in rows:
            history = histories.get(row.player, [])
            if not history:
                continue
            if any(left[1] != right[0] for left, right in zip(history, history[1:])):
                raise ValueError(
                    f"trade ownership conflict for {row.player}: discontinuous history"
                )
            positions = [history[0][0], *(hop[1] for hop in history)]
            owner = team_key(row.team)
            if owner not in positions:
                raise ValueError(f"trade ownership conflict for {row.player}")
            if positions.count(owner) != 1:
                raise ValueError(
                    f"ambiguous unwatermarked trade history for {row.player}; "
                    "establish a verified baseline before applying"
                )
            # A unique position in a linear history identifies its reflected prefix.
            reflected.update((row.player, hop[2]) for hop in history[: positions.index(owner)])
    for trade, key, events in pending:
        for found, source, target in events:
            if (found, key) in reflected:
                continue
            index = next(i for i, r in enumerate(result) if r.player == found)
            row = result[index]
            if team_key(row.team) not in (source, team_key(target)):
                raise ValueError(f"trade ownership conflict for {found}")
            if team_key(row.team) != team_key(target):
                result[index] = replace(row, team=target, traded=row.traded + 1)
                if warnings is not None:
                    warnings.append(
                        f"keeper trade: {row.player} {row.team} -> {target}; "
                        f"trade count {row.traded} -> {row.traded + 1}"
                    )
        seen.add(key)
        watermark = max(watermark, trade_date(trade).isoformat())
    # Stable within each owner block; scan does not force five keepers per team.
    order = {key: i for i, key in enumerate(teams)}
    result.sort(key=lambda r: order[team_key(r.team)])
    return result, {"season": season, "seen": sorted(seen), "last_seen": watermark}
