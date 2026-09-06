"""Exercise the real Node entrypoint against a disposable browser transport."""

import json
import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "src/keeper/collect.mjs"
BROWSER = """
import {writeFileSync} from 'node:fs';
const s=JSON.parse(process.env.KEEPER_TEST_SCENARIO);
let url='', step=0;
const page={
 setDefaultTimeout(){},
 async goto(next){url=s.redirect && next.includes('transactions') ? s.redirect : next; step++;},
 url(){return url;},
 locator(selector){return {async evaluateAll(){
   return selector.includes('option') ? s.options : (s.next || []);
 }};},
 async content(){return '<html>captured page</html>';}
};
export const chromium={async launchPersistentContext(){return {
 async newPage(){return page;},
 async close(){writeFileSync(process.env.KEEPER_TEST_CLOSED,'closed');}
};}};
"""


@pytest.mark.parametrize(
    "scenario,command,season,league,error",
    [
        ({"options": []}, "reconcile", "2025", "5003", "season metadata"),
        ({}, "reconcile", "2000", "5003", "not available"),
        ({}, "scan-trades", "2024", "5003", "archived --league-id"),
        (
            {"next": ["https://evil.example/transactions"]},
            "scan-trades",
            "2026",
            "5003",
            "pagination target",
        ),
        ({"next": ["a", "b"]}, "scan-trades", "2026", "5003", "ambiguous pagination"),
        (
            {"redirect": "https://hockey.fantasysports.yahoo.com/login"},
            "scan-trades",
            "2026",
            "5003",
            "redirect",
        ),
        (
            {
                "next": [
                    "https://hockey.fantasysports.yahoo.com/hockey/5003/transactions?transactionsfilter=trade"
                ]
            },
            "scan-trades",
            "2026",
            "5003",
            "pagination incomplete",
        ),
        ({}, "bad-command", "2025", "5003", "invalid collector arguments"),
    ],
)
def test_transport_refuses_unverified_collection(
    tmp_path, scenario, command, season, league, error
):
    result, closed = invoke(tmp_path, scenario, command, season, league)
    assert result.returncode != 0
    assert error in result.stderr
    assert result.stdout == ""
    if command != "bad-command":
        assert closed.exists()


def invoke(tmp_path, scenario, command="reconcile", season="2025", league="5003"):
    scenario.setdefault(
        "options",
        [
            {"value": "current", "text": "2026 draft order"},
            {"value": "previous", "text": "2025 season draft results"},
        ],
    )
    module = tmp_path / "browser.mjs"
    module.write_text(BROWSER)
    closed = tmp_path / "closed"
    result = subprocess.run(
        ["node", str(SCRIPT), command, season, str(tmp_path), league],
        env={
            **os.environ,
            "KEEPER_PLAYWRIGHT": str(module),
            "KEEPER_TEST_SCENARIO": json.dumps(scenario),
            "KEEPER_TEST_CLOSED": str(closed),
        },
        text=True,
        capture_output=True,
        timeout=10,
    )
    return result, closed


def test_transport_returns_captured_page_and_closes_profile(tmp_path):
    result, closed = invoke(tmp_path, {})
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "pages": ["<html>captured page</html>"],
        "season": 2025,
        "league_id": 5003,
    }
    assert closed.read_text() == "closed"
