"""Parse bounded Yahoo page content, rejecting incomplete or changed markup."""

from typing import Any

from bs4 import BeautifulSoup


def parse_draft(html: str, season: int) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    selected = soup.select_one("#yfa-draftresults-select option[selected]")
    if selected is None or str(season) not in selected.get_text():
        raise ValueError("draft season selection not confirmed")
    result: dict[str, Any] = {}
    for tag in soup.select('[title="This player is a keeper."]'):
        row = tag.find_parent("tr")
        player = row.select_one("a.name") if row else None
        team = row.select_one("td.last") if row else None
        if player is None or team is None:
            raise ValueError("unrecognized keeper row")
        result.setdefault(team.get_text(strip=True), []).append(
            {"player": player.get_text(strip=True), "keeper": True}
        )
    if len(result) != 12 or any(len(p) != 5 for p in result.values()):
        raise ValueError("incomplete keeper board")
    return result


def parse_trades(html: str, season: int, league_id: int) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("table.Tst-transaction-table")
    if table is None:
        raise ValueError("transaction table missing; auth or markup changed")
    rows = table.select("tr")
    if len(rows) <= 1 and "No recent transactions" in soup.get_text() and not table.select("a"):
        return []
    trades = []
    pending = []
    dates = []
    for row in rows:
        if "Traded to" not in row.get_text():
            raise ValueError("unrecognized trade row")
        cells = row.find_all("td", recursive=False)
        assets, owner = cells[-3], cells[-1]
        team = owner.select_one("a")
        stamp = owner.select_one(".F-timestamp")
        if team is None or stamp is None:
            raise ValueError("trade owner/date missing")
        received = []
        for paragraph in assets.select("p"):
            player = paragraph.select_one("a")
            position = paragraph.select_one(".F-position")
            if player is not None and position is not None:
                received.append(f"{player.get_text(strip=True)} ({position.get_text(strip=True)})")
            elif paragraph.get_text(strip=True).startswith("Round "):
                received.append(paragraph.get_text(" ", strip=True))
            else:
                raise ValueError("unrecognized trade asset")
        pending.append({"team": team.get_text(strip=True), "received": received})
        dates.append(stamp.get_text(strip=True))
        if len(pending) == 2:
            if dates[0] != dates[1]:
                raise ValueError("trade pairing date mismatch")
            trades.append(
                {"season": season, "league_id": league_id, "date": dates[0], "teams": pending}
            )
            pending, dates = [], []
    if pending or not trades:
        raise ValueError("incomplete trade page")
    return trades


def parse_collection(
    collected: dict[str, Any], command: str, season: int, league_id: int
) -> dict[str, Any] | list[dict[str, Any]]:
    from .core import trade_key

    if collected["season"] != season or collected["league_id"] != league_id:
        raise ValueError("collector scope mismatch")
    if command == "reconcile":
        return parse_draft(collected["pages"][0], season)
    trades = [
        trade for html in collected["pages"] for trade in parse_trades(html, season, league_id)
    ]
    if collected.get("complete") is not True or collected.get("transaction_count") != len(trades):
        raise ValueError("incomplete transaction collection")
    if len({trade_key(t) for t in trades}) != len(trades):
        raise ValueError("overlapping transaction pages")
    return trades
