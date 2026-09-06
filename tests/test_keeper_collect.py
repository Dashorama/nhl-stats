import json
from pathlib import Path

import pytest

from src.keeper.collect import parse_draft, parse_trades

FIXTURES = Path(__file__).parent / "fixtures/keeper_reconcile"


def test_live_markup_draft_matches_staged_keeper_board():
    html = (FIXTURES / "draft.html").read_text()
    result = parse_draft(html, 2025)
    expected = json.loads((FIXTURES / "keepers_2025.json").read_text())
    assert {t: [p["player"] for p in picks] for t, picks in result.items()} == {
        t: [p["player"] for p in picks] for t, picks in expected.items() if t != "raw_full_draft"
    }
    with pytest.raises(ValueError, match="season"):
        parse_draft(html, 2026)
    with pytest.raises(ValueError, match="keeper"):
        parse_draft(html.replace("This player is a keeper.", "removed"), 2025)


def test_live_markup_trade_sample_and_fail_closed():
    html = (FIXTURES / "transactions.html").read_text()
    result = parse_trades(html, 2024, 17419)
    expected = json.loads((FIXTURES / "trades.json").read_text())[:7]
    assert [{k: t[k] for k in ("season", "league_id", "date", "teams")} for t in result] == [
        {k: t[k] for k in ("season", "league_id", "date", "teams")} for t in expected
    ]
    with pytest.raises(ValueError, match="transaction"):
        parse_trades("<html>Login required</html>", 2024, 17419)
    with pytest.raises(ValueError, match="^unrecognized trade row$"):
        parse_trades(html.replace("Traded to", "Changed markup", 1), 2024, 17419)
    assert (
        parse_trades(
            '<table class="Tst-transaction-table"></table>No recent transactions', 2026, 5003
        )
        == []
    )


def test_empty_live_transaction_table():
    assert (
        parse_trades(
            '<table class="Tst-transaction-table"><tr><td colspan="4">'
            "<div>No recent transactions</div></td></tr></table>",
            2026,
            5003,
        )
        == []
    )


@pytest.mark.parametrize(
    "old,new,message",
    [
        ('class="name"', 'class="renamed"', "keeper row"),
    ],
)
def test_changed_keeper_markup(old, new, message):
    html = (FIXTURES / "draft.html").read_text().replace(old, new)
    with pytest.raises(ValueError, match=message):
        parse_draft(html, 2025)


@pytest.mark.parametrize(
    "old,new,message",
    [
        ("F-timestamp", "removed", "owner/date"),
        ("Round 3", "Mystery asset", "asset"),
        ("Mar 1, 4:10 am", "Mar 2, 4:10 am", "pairing date"),
    ],
)
def test_changed_trade_markup(old, new, message):
    html = (FIXTURES / "transactions.html").read_text().replace(old, new, 1)
    with pytest.raises(ValueError, match=message):
        parse_trades(html, 2024, 17419)


def test_incomplete_trade_pair():
    from bs4 import BeautifulSoup

    soup = BeautifulSoup((FIXTURES / "transactions.html").read_text(), "html.parser")
    soup.select("tr")[-1].decompose()
    with pytest.raises(ValueError, match="incomplete trade"):
        parse_trades(str(soup), 2024, 17419)


def test_collection_completeness_and_nonoverlapping_pages():
    from src.keeper.collect import parse_collection

    html = (FIXTURES / "transactions.html").read_text()
    collection = {
        "season": 2024,
        "league_id": 17419,
        "pages": [html],
        "complete": True,
        "transaction_count": 7,
    }
    assert len(parse_collection(collection, "scan-trades", 2024, 17419)) == 7
    with pytest.raises(ValueError, match="collector scope"):
        parse_collection(collection, "scan-trades", 2025, 17419)
    with pytest.raises(ValueError, match="incomplete transaction collection"):
        parse_collection({**collection, "complete": False}, "scan-trades", 2024, 17419)
    with pytest.raises(ValueError, match="incomplete transaction collection"):
        parse_collection({**collection, "transaction_count": 6}, "scan-trades", 2024, 17419)
    with pytest.raises(ValueError, match="overlapping transaction pages"):
        parse_collection(
            {**collection, "pages": [html, html], "transaction_count": 14},
            "scan-trades",
            2024,
            17419,
        )


def test_two_page_fixture_reconciles_collected_count():
    from src.keeper.collect import parse_collection

    pages = [(FIXTURES / f"transactions-page-{i}.html").read_text() for i in (1, 2)]
    result = parse_collection(
        {
            "season": 2026,
            "league_id": 5003,
            "pages": pages,
            "complete": True,
            "transaction_count": 26,
        },
        "scan-trades",
        2026,
        5003,
    )
    assert len(result) == 26
    assert result[-1]["date"] == "Oct 26, 4:10 am"


def test_season_league_map_and_unknown_season():
    from src.keeper.collect import resolve_league

    # Change detector for the full map supplied in NOVA-KRT-2; not live ID discovery.
    assert [resolve_league(year) for year in range(2014, 2027)] == [
        107861,
        49434,
        69011,
        78662,
        26937,
        20403,
        29812,
        21085,
        13632,
        23870,
        17419,
        26028,
        5003,
    ]
    with pytest.raises(ValueError, match="unknown season"):
        resolve_league(2027)
    assert resolve_league(2027, 12345) == 12345


def test_archived_2025_league_capture_has_its_own_current_draft():
    from bs4 import BeautifulSoup

    html = (FIXTURES / "draft-2025-26028.html").read_text()
    soup = BeautifulSoup(html, "html.parser")
    assert soup.select_one('option[value="current"]').get_text(strip=True) == "2025 draft order"
    assert soup.select_one("option[selected]").get_text(strip=True) == "2025 draft order"
    result = parse_draft(html, 2025)
    board = json.loads((FIXTURES / "keepers_2025.json").read_text())
    assert {t: [p["player"] for p in picks] for t, picks in result.items()} == {
        t: [p["player"] for p in picks] for t, picks in board.items() if t != "raw_full_draft"
    }
