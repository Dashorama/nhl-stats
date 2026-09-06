"""Ground truth and behavioral tests for the I/O-free keeper engine."""
import copy
import csv
import json
from pathlib import Path

import pytest

from src.keeper.core import Keeper, reconcile, scanTrades

FIXTURES = Path(__file__).parent / 'fixtures/keeper_reconcile'


def fixture(name):
    return json.loads((FIXTURES / name).read_text())


def test_reconcile_ground_truth():
    board, snapshot = fixture('keepers_2025.json'), fixture('rawdata_backup.json')
    original = copy.deepcopy((board, snapshot))
    result = reconcile(board, snapshot, season=2025)
    expected = list(csv.DictReader((FIXTURES / 'keeper_sheet_2025_reconciled.csv').open()))
    assert [(k.team, k.player, str(k.first_year), str(k.traded)) for k in result] == [
        (r['Team Name'], r['Player Name'], r['First Year Kept'], r['Traded?'])
        for r in expected
    ]
    assert (board, snapshot) == original


def test_reconcile_tag_count_and_unknown_team():
    board, snapshot = fixture('keepers_2025.json'), fixture('rawdata_backup.json')
    board['Julie the Cat'][0]['keeper'] = False
    with pytest.raises(ValueError, match='keeper count'):
        reconcile(board, snapshot, season=2025)
    board = fixture('keepers_2025.json')
    board['Unknown'] = board.pop('Julie the Cat')
    with pytest.raises(ValueError, match='team'):
        reconcile(board, snapshot, season=2025)


def test_trade_fixture_five_real_trades_and_replay():
    # The backup already reflects these trades: scanning must leave it unchanged.
    from src.keeper.core import from_snapshot
    rows = from_snapshot(fixture('rawdata_backup.json'))
    result, state = scanTrades(rows, fixture('trades.json'), season=2024)
    assert result == rows
    assert len(state['seen']) == 7  # five keeper trades, two non-keeper trades
    replay, replay_state = scanTrades(result, fixture('trades.json'), season=2024, state=state)
    assert (replay, replay_state) == (result, state)
    # Undo five actual keeper trades, then replay the same sample.
    before = copy.deepcopy(rows)
    origins = {'Jeremy Swayman': 'The Bad Place', 'Leon Draisaitl': 'Jean Claude VanDangles',
               'Brayden Point': 'Julie the Cat', 'William Nylander': "Miller's High Life",
               'Nathan MacKinnon': "Miller's High Life"}
    from src.keeper.core import normalize
    for i, row in enumerate(before):
        for player, team in origins.items():
            if normalize(row.player) == normalize(player):
                before[i] = Keeper(team, row.player, row.first_year, 0)
    moved, _ = scanTrades(before, fixture('trades.json'), season=2024)
    assert sorted((r.player, r.team, r.first_year, r.traded) for r in moved) == sorted(
        (r.player, r.team, r.first_year, r.traded) for r in rows)


def test_chained_trades_chronology_one_time_and_watermark():
    rows = [Keeper('A', 'Player One', 2022, 0), Keeper('B', 'Other', 2024, 0),
            Keeper('C', 'Third', 2024, 0)]
    def trade(date, source, target):
        return {'season': 2025, 'league_id': 5003, 'date': date,
                'teams': [{'team': source, 'received': ['Round 2']},
                          {'team': target, 'received': ['Player One (BOS - G)']}]}
    trades = [trade('Feb 1, 4:10 am', 'B', 'C'), trade('Dec 1, 4:10 am', 'A', 'B')]
    result, state = scanTrades(rows, trades, season=2025)
    assert next(r for r in result if r.player == 'Player One') == Keeper('C', 'Player One', 2022, 1)
    assert scanTrades(result, trades, season=2025, state=state) == (result, state)
    with pytest.raises(ValueError, match='season'):
        scanTrades(result, trades, season=2026, state=state)


@pytest.mark.parametrize('mutation,message', [
    ('duplicate_board', 'duplicate'), ('duplicate_sheet', 'duplicate'),
    ('malformed_sheet', 'snapshot'), ('invalid_flag', 'Traded'),
])
def test_reconcile_rejects_corrupt_inputs(mutation, message):
    board, snapshot = fixture('keepers_2025.json'), fixture('rawdata_backup.json')
    if mutation == 'duplicate_board':
        board['Julie the Cat'][0]['player'] = board['Cuylle-O'][0]['player']
    elif mutation == 'duplicate_sheet':
        snapshot['raw_values'][4][2] = snapshot['raw_values'][3][2]
    elif mutation == 'malformed_sheet':
        snapshot['raw_values'][4] = ['partial']
    else:
        snapshot['raw_values'][4][6] = '2'
    with pytest.raises(ValueError, match=message):
        reconcile(board, snapshot)


def test_matching_ambiguity_is_an_error():
    from src.keeper.core import match
    with pytest.raises(ValueError, match='ambiguous'):
        match('JT Miller', ['J.T. Miller', 'JT Miller'])
    with pytest.raises(ValueError, match='ambiguous'):
        match('Player Ones', ['Player Onea', 'Player Oneb'])


@pytest.mark.parametrize('mutation,message', [
    ('sides', 'two teams'), ('unknown', 'unknown acquiring'),
    ('owner', 'ownership conflict'), ('league', 'league'),
])
def test_trade_conflicts_fail_closed(mutation, message):
    rows = [Keeper('A', 'Player One', 2022, 0), Keeper('B', 'Other', 2024, 0),
            Keeper('C', 'Third', 2024, 0)]
    trade = {'season': 2025, 'league_id': 5003, 'date': 'Dec 1, 4:10 am',
             'teams': [{'team': 'A', 'received': ['Round 1']},
                       {'team': 'B', 'received': ['Player One (BOS - G)']}]}
    trades = [trade]
    if mutation == 'sides':
        trade['teams'].pop()
    elif mutation == 'unknown':
        trade['teams'][1]['team'] = 'Unknown'
    elif mutation == 'owner':
        trade['teams'][0]['team'] = 'C'
    else:
        other = copy.deepcopy(trade)
        other['league_id'] = 42
        trades.append(other)
    with pytest.raises(ValueError, match=message):
        scanTrades(rows, trades, season=2025)
