"""Tests for the NHL shift-chart scraper.

Shift charts come from a different host than the rest of the api-web data
(``api.nhle.com/stats/rest/en``), so they get their own scraper.
"""

from src.scrapers.nhl_shifts import NHLShiftChartScraper

SHIFT_PAYLOAD = {
    "total": 2,
    "data": [
        {
            "id": 8301699,
            "detailCode": 0,
            "duration": "00:42",
            "endTime": "00:42",
            "eventDescription": None,
            "eventNumber": 6,
            "firstName": "Patrick",
            "gameId": 2018020001,
            "lastName": "Marleau",
            "period": 1,
            "playerId": 8466139,
            "shiftNumber": 1,
            "startTime": "00:00",
            "teamAbbrev": "TOR",
            "teamId": 10,
            "typeCode": 517,
        },
        {
            "id": 8301700,
            "detailCode": 0,
            "duration": "01:03",
            "endTime": "02:11",
            "eventNumber": 12,
            "firstName": "Auston",
            "gameId": 2018020001,
            "lastName": "Matthews",
            "period": 1,
            "playerId": 8479318,
            "shiftNumber": 1,
            "startTime": "01:08",
            "teamAbbrev": "TOR",
            "teamId": 10,
            "typeCode": 517,
        },
    ],
}


class TestShiftChartScraper:
    def test_uses_the_stats_rest_host(self):
        assert NHLShiftChartScraper.BASE_URL == "https://api.nhle.com/stats/rest/en"

    def test_parses_every_shift_row(self):
        shifts = NHLShiftChartScraper.parse_shifts(SHIFT_PAYLOAD)
        assert len(shifts) == 2

    def test_maps_the_shift_fields(self):
        shift = NHLShiftChartScraper.parse_shifts(SHIFT_PAYLOAD)[0]
        assert shift["game_id"] == 2018020001
        assert shift["player_id"] == 8466139
        assert shift["player_name"] == "Patrick Marleau"
        assert shift["team_abbrev"] == "TOR"
        assert shift["team_id"] == 10
        assert shift["period"] == 1
        assert shift["shift_number"] == 1
        assert shift["start_time"] == "00:00"
        assert shift["end_time"] == "00:42"
        assert shift["duration"] == "00:42"
        assert shift["type_code"] == 517
        assert shift["detail_code"] == 0
        assert shift["event_number"] == 6

    def test_drops_rows_without_the_natural_key(self):
        payload = {"data": [{"gameId": 2018020001, "playerId": None, "period": 1}]}
        assert NHLShiftChartScraper.parse_shifts(payload) == []

    def test_handles_an_empty_payload(self):
        assert NHLShiftChartScraper.parse_shifts({"data": []}) == []
        assert NHLShiftChartScraper.parse_shifts({}) == []
