"""Ground truth and behavioral tests for the I/O-free keeper engine."""

import copy
import csv
import json
from pathlib import Path

import pytest

from src.keeper.core import Keeper, normalize, reconcile, scanTrades

FIXTURES = Path(__file__).parent / "fixtures/keeper_reconcile"


def fixture(name):
    return json.loads((FIXTURES / name).read_text())


def test_reconcile_ground_truth():
    board, snapshot = fixture("keepers_2025.json"), fixture("rawdata_backup.json")
    original = copy.deepcopy((board, snapshot))
    result = reconcile(board, snapshot, season=2025)
    expected = list(csv.DictReader((FIXTURES / "keeper_sheet_2025_reconciled.csv").open()))
    owners = {r[0]: r[1] for r in snapshot["raw_values"][3:]}
    # CSV typo is reference noise; draft spelling is separately tested below.
    reference_names = {"Mathew Tkachuk": "Matthew Tkachuk"}
    assert {(owners[k.team], normalize(k.player), k.first_year, k.traded) for k in result} == {
        (
            owners[r["Team Name"]],
            normalize(reference_names.get(r["Player Name"], r["Player Name"])),
            int(r["First Year Kept"]),
            int(r["Traded?"]),
        )
        for r in expected
    }
    assert len(result) == len(expected)
    assert (board, snapshot) == original


def test_reconcile_tag_count_and_unknown_team():
    board, snapshot = fixture("keepers_2025.json"), fixture("rawdata_backup.json")
    board["Julie the Cat"][0]["keeper"] = False
    with pytest.raises(ValueError, match="keeper count"):
        reconcile(board, snapshot, season=2025)
    board = fixture("keepers_2025.json")
    board["Unknown"] = board.pop("Julie the Cat")
    with pytest.raises(ValueError, match="team"):
        reconcile(board, snapshot, season=2025)


def test_trade_fixture_five_real_trades_and_replay():
    # The backup already reflects these trades: scanning must leave it unchanged.
    from src.keeper.core import from_snapshot

    rows = from_snapshot(fixture("rawdata_backup.json"))
    result, state = scanTrades(rows, fixture("trades.json"), season=2024)
    assert result == rows
    assert len(state["seen"]) == 7  # five keeper trades, two non-keeper trades
    replay, replay_state = scanTrades(result, fixture("trades.json"), season=2024, state=state)
    assert (replay, replay_state) == (result, state)
    # Undo five actual keeper trades, then replay the same sample.
    before = copy.deepcopy(rows)
    origins = {
        "Jeremy Swayman": "The Bad Place",
        "Leon Draisaitl": "Jean Claude VanDangles",
        "Brayden Point": "Julie the Cat",
        "William Nylander": "Miller's High Life",
        "Nathan MacKinnon": "Miller's High Life",
    }
    from src.keeper.core import normalize

    for i, row in enumerate(before):
        for player, team in origins.items():
            if normalize(row.player) == normalize(player):
                before[i] = Keeper(team, row.player, row.first_year, 0)
    moved, _ = scanTrades(before, fixture("trades.json"), season=2024)
    assert sorted((r.player, r.team, r.first_year, r.traded) for r in moved) == sorted(
        (r.player, r.team, r.first_year, r.traded) for r in rows
    )


def test_chained_trades_chronology_cumulative_and_watermark():
    rows = [
        Keeper("A", "Player One", 2022, 0),
        Keeper("B", "Other", 2024, 0),
        Keeper("C", "Third", 2024, 0),
    ]

    def trade(date, source, target):
        return {
            "season": 2025,
            "league_id": 5003,
            "date": date,
            "teams": [
                {"team": source, "received": ["Round 2"]},
                {"team": target, "received": ["Player One (BOS - G)"]},
            ],
        }

    trades = [trade("Feb 1, 4:10 am", "B", "C"), trade("Dec 1, 4:10 am", "A", "B")]
    result, state = scanTrades(rows, trades, season=2025)
    assert next(r for r in result if r.player == "Player One") == Keeper("C", "Player One", 2022, 2)
    assert scanTrades(result, trades, season=2025, state=state) == (result, state)
    with pytest.raises(ValueError, match="season"):
        scanTrades(result, trades, season=2026, state=state)


@pytest.mark.parametrize(
    "mutation,message",
    [
        ("duplicate_board", "duplicate"),
        ("duplicate_sheet", "duplicate"),
        ("malformed_sheet", "snapshot"),
        ("invalid_flag", "Traded"),
    ],
)
def test_reconcile_rejects_corrupt_inputs(mutation, message):
    board, snapshot = fixture("keepers_2025.json"), fixture("rawdata_backup.json")
    if mutation == "duplicate_board":
        board["Julie the Cat"][0]["player"] = board["Cuylle-O"][0]["player"]
    elif mutation == "duplicate_sheet":
        snapshot["raw_values"][4][2] = snapshot["raw_values"][3][2]
    elif mutation == "malformed_sheet":
        snapshot["raw_values"][4] = ["partial"]
    else:
        snapshot["raw_values"][4][6] = "-1"
    with pytest.raises(ValueError, match=message):
        reconcile(board, snapshot)


def test_matching_ambiguity_is_an_error():
    from src.keeper.core import match

    with pytest.raises(ValueError, match="ambiguous"):
        match("JT Miller", ["J.T. Miller", "JT Miller"])
    with pytest.raises(ValueError, match="ambiguous"):
        match("Player Ones", ["Player Onea", "Player Oneb"])


@pytest.mark.parametrize(
    "mutation,message",
    [
        ("sides", "two teams"),
        ("unknown", "unknown acquiring"),
        ("owner", "ownership conflict"),
        ("league", "league"),
    ],
)
def test_trade_conflicts_fail_closed(mutation, message):
    rows = [
        Keeper("A", "Player One", 2022, 0),
        Keeper("B", "Other", 2024, 0),
        Keeper("C", "Third", 2024, 0),
    ]
    trade = {
        "season": 2025,
        "league_id": 5003,
        "date": "Dec 1, 4:10 am",
        "teams": [
            {"team": "A", "received": ["Round 1"]},
            {"team": "B", "received": ["Player One (BOS - G)"]},
        ],
    }
    trades = [trade]
    if mutation == "sides":
        trade["teams"].pop()
    elif mutation == "unknown":
        trade["teams"][1]["team"] = "Unknown"
    elif mutation == "owner":
        trade["teams"][0]["team"] = "C"
    else:
        other = copy.deepcopy(trade)
        other["league_id"] = 42
        trades.append(other)
    with pytest.raises(ValueError, match=message):
        scanTrades(rows, trades, season=2025)


def test_trade_fingerprint_survives_current_nhl_position_labels():
    from src.keeper.core import trade_key

    trade = fixture("trades.json")[0]
    updated = copy.deepcopy(trade)
    updated["teams"][0]["received"][0] = "Jeremy Swayman (NYR - G)"
    updated["teams"].reverse()
    assert trade_key(updated) == trade_key(trade)


def test_team_with_zero_keepers_can_receive_keeper():
    rows = [Keeper("A", "Player One", 2024, 0)]
    trade = {
        "season": 2026,
        "league_id": 5003,
        "date": "Oct 1, 4:10 am",
        "teams": [
            {"team": "A", "received": ["Round 1"]},
            {"team": "B", "received": ["Player One (BOS - G)"]},
        ],
    }
    result, _ = scanTrades(rows, [trade], season=2026, known_teams=["A", "B"])
    assert result == [Keeper("B", "Player One", 2024, 1)]


def test_trade_identity_includes_receiving_teams():
    from src.keeper.core import trade_key

    trade = fixture("trades.json")[0]
    changed = copy.deepcopy(trade)
    changed["teams"][0]["team"] = "Other acquiring team"
    assert trade_key(trade) != trade_key(changed)


def test_trade_result_is_grouped_by_owner_order():
    rows = [
        Keeper("A", "Player One", 2024, 0),
        Keeper("B", "Player Two", 2024, 0),
        Keeper("A", "Player Three", 2024, 0),
    ]
    result, _ = scanTrades(rows, [], season=2026)
    assert [r.player for r in result] == ["Player One", "Player Three", "Player Two"]


def test_leap_day_trade_date():
    from datetime import datetime

    from src.keeper.core import trade_date

    assert trade_date({"season": 2027, "date": "Feb 29, 4:10 am"}) == datetime(2028, 2, 29, 4, 10)


def test_duplicate_alias_candidates_are_ambiguous():
    from src.keeper.core import match

    with pytest.raises(ValueError, match="ambiguous player"):
        match("Jacob Markstrom", ["Jacob Markstrom", "Jakob Markstron"])


def test_exact_match_wins_and_unrelated_names_do_not_match():
    from src.keeper.core import match

    assert match("Player One", ["Player One", "Player Ones"]) == "Player One"
    assert match("Jack Hughes", ["Quinn Hughes"]) is None
    assert match("Jack Hughes", []) is None


def test_board_spelling_and_original_sheet_order_replace_csv_cosmetics():
    board, snapshot = fixture("keepers_2025.json"), fixture("rawdata_backup.json")
    result = reconcile(board, snapshot)
    canonical = {
        p["player"]
        for t, picks in board.items()
        if t != "raw_full_draft"
        for p in picks
        if p.get("keeper") is True
    }
    assert {r.player for r in result} == canonical
    players = [r.player for r in result if r.team == "Trou Trou Train"]
    assert players.index("Leon Draisaitl") < players.index("Jack Hughes")


def small_board_snapshot():
    board = {
        "A": [{"player": p, "keeper": True} for p in ["New Alpha", "Matthew Tkachuk", "New Beta"]],
        "B": [{"player": p, "keeper": True} for p in ["Other One", "Other Two", "Other Three"]],
    }
    snapshot = {
        "raw_values": [
            [],
            [],
            [],
            ["A", "Owner A", "Dropped Player", "", "2020", "", "0"],
            ["B", "Owner B", "Mathew Tkachuk", "", "2022", "", "2"],
            ["B", "Owner B", "Other Two", "", "2023", "", "0"],
        ]
    }
    return board, snapshot


def test_global_contract_carry_and_new_append_order_with_move_warning():
    board, snapshot = small_board_snapshot()
    warnings = []
    result = reconcile(board, snapshot, season=2026, expected_count=3, warnings=warnings)
    assert result == [
        Keeper("A", "Matthew Tkachuk", 2022, 2),
        Keeper("A", "New Alpha", 2026, 0),
        Keeper("A", "New Beta", 2026, 0),
        Keeper("B", "Other Two", 2023, 0),
        Keeper("B", "Other One", 2026, 0),
        Keeper("B", "Other Three", 2026, 0),
    ]
    assert warnings == [
        "possible unrecorded trade: Matthew Tkachuk sheet-team B -> "
        "draft-team A; FYK/count carried, verify bonus"
    ]


@pytest.mark.parametrize("value", ["-1", "1.5", "True", "", True])
def test_trade_count_rejects_invalid_values(value):
    from src.keeper.core import from_snapshot

    _, snapshot = small_board_snapshot()
    snapshot["raw_values"][3][6] = value
    with pytest.raises(ValueError, match="Traded"):
        from_snapshot(snapshot)


def test_two_board_players_cannot_share_one_global_contract():
    board, snapshot = small_board_snapshot()
    snapshot["raw_values"][4][6] = "0"
    board["A"][0]["player"] = "Matthew Tkachuks"
    with pytest.raises(ValueError, match="same sheet keeper"):
        reconcile(board, snapshot, expected_count=3)


def test_cumulative_trade_from_existing_count_and_already_reflected_trade():
    rows = [Keeper("A", "Player One", 2020, 2)]
    trade = {
        "season": 2026,
        "league_id": 5003,
        "date": "Oct 1, 4:10 am",
        "teams": [
            {"team": "A", "received": ["Round 1"]},
            {"team": "B", "received": ["Player One (BOS - G)"]},
        ],
    }
    result, state = scanTrades(rows, [trade], season=2026, known_teams=["A", "B"])
    assert result == [Keeper("B", "Player One", 2020, 3)]
    assert scanTrades(result, [trade], season=2026, state=state, known_teams=["A", "B"]) == (
        result,
        state,
    )
    assert scanTrades(result, [trade], season=2026, known_teams=["A", "B"])[0] == result


@pytest.mark.parametrize("duplicate_side", [0, 1])
def test_one_keeper_cannot_be_received_twice_in_one_trade(duplicate_side):
    trade = {
        "season": 2026,
        "league_id": 5003,
        "date": "Oct 1, 4:10 am",
        "teams": [
            {"team": "A", "received": ["Player One (BOS - G)"]},
            {"team": "B", "received": ["Round 1"]},
        ],
    }
    trade["teams"][duplicate_side]["received"].append("Player One (BOS - G)")
    with pytest.raises(ValueError, match="duplicate keeper in trade"):
        scanTrades(
            [Keeper("B", "Player One", 2022, 2)], [trade], season=2026, known_teams=["A", "B"]
        )


def test_unwatermarked_round_trip_requires_a_verified_baseline():
    rows = [Keeper("A", "Player One", 2022, 2)]
    trades = [
        {
            "season": 2026,
            "league_id": 5003,
            "date": f"Oct {i}, 4:10 am",
            "teams": [
                {"team": source, "received": ["Round 1"]},
                {"team": target, "received": ["Player One (BOS - G)"]},
            ],
        }
        for i, source, target in [(1, "A", "B"), (2, "B", "A")]
    ]
    with pytest.raises(ValueError, match="ambiguous unwatermarked trade history"):
        scanTrades(rows, trades, season=2026, known_teams=["A", "B"])
    # A deliberately established pre-trade watermark disambiguates new round trips.
    baseline = {"season": 2026, "seen": [], "last_seen": ""}
    result, state = scanTrades(rows, trades, season=2026, known_teams=["A", "B"], state=baseline)
    assert result == [Keeper("A", "Player One", 2022, 4)]
    assert scanTrades(result, trades, season=2026, known_teams=["A", "B"], state=state) == (
        result,
        state,
    )


def test_fuzzy_contract_match_warns_about_identity_not_just_bonus():
    board, snapshot = small_board_snapshot()
    board["A"][1]["player"] = "Brand New Guy"
    snapshot["raw_values"][4][2] = "Brand New Guyy"
    warnings = []
    reconcile(board, snapshot, expected_count=3, warnings=warnings)
    assert any("fuzzy player-name match: Brand New Guy -> Brand New Guyy" in w
               and "verify same person" in w for w in warnings)


def test_unwatermarked_linear_history_recognizes_reflected_prefix():
    trade = lambda i, source, target: {"season": 2026, "league_id": 5003,
        "date": f"Oct {i}, 4:10 am", "teams": [
            {"team": source, "received": ["Round 1"]},
            {"team": target, "received": ["Player One (BOS - G)"]}]}
    trades = [trade(1, "A", "B"), trade(2, "B", "C")]
    for owner, count in [("A", 0), ("B", 1), ("C", 2)]:
        result, _ = scanTrades([Keeper(owner, "Player One", 2022, count)], trades,
                              season=2026, known_teams=["A", "B", "C"])
        assert result == [Keeper("C", "Player One", 2022, 2)]
    broken = [trade(1, "A", "B"), trade(2, "A", "C")]
    with pytest.raises(ValueError, match="ownership conflict"):
        scanTrades([Keeper("C", "Player One", 2022, 2)], broken,
                   season=2026, known_teams=["A", "B", "C"])
