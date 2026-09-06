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
