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
let url='', step=0, visits=[];
const page={
 setDefaultTimeout(){},
 async goto(next){visits.push(next); writeFileSync(process.env.KEEPER_TEST_CLOSED+'.visits',JSON.stringify(visits)); url=s.redirect && next.includes('transactions') ? s.redirect : next; step++;},
 url(){return url;},
 locator(selector){return {async evaluateAll(){
   return selector.includes('option') ? (s.bareUnavailable && !new URL(url).pathname.match(/^\/\d{4}\//) ? [] : s.options) : (s.next || []);
 }, async evaluate(){
   if(s.pages) return s.pages[step-2];
   if(s.loop) return {tradeCount:25,pagers:[{href:`https://hockey.fantasysports.yahoo.com/hockey/5003/transactions?transactionsfilter=trade&count=${(step-1)*25}`,terminal:false}]};
   return {tradeCount:s.tradeCount ?? (s.next?.length ? 25 : 0),
           pagers:s.pagers || (s.next || []).map(href=>({href,terminal:false}))};
 }};},
 async content(){return s.pages?.[step-2]?.html || '<html>captured page</html>';}
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
        ({"options": [{"value": "current", "text": "2026 draft order"}]},
         "reconcile", "2000", "5003", "season metadata"),
        ({"options": [{"value": "current", "text": "2026 draft order"}]},
         "scan-trades", "2024", "5003", "season metadata"),
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


def invoke(tmp_path, scenario, command="reconcile", season="2025", league="26028", profile=None):
    scenario.setdefault(
        "options",
        [
            {"value": "current", "text": f"{season} draft order"},
            {"value": "previous", "text": f"{int(season) - 1} season draft results"},
        ],
    )
    module = tmp_path / "browser.mjs"
    module.write_text(BROWSER)
    closed = tmp_path / "closed"
    result = subprocess.run(
        ["node", str(SCRIPT), command, season, str(profile or tmp_path), league],
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
        "league_id": 26028,
    }
    assert closed.read_text() == "closed"


def test_two_page_structural_pager_deduplicates_top_bottom_links(tmp_path):
    next_url = "https://hockey.fantasysports.yahoo.com/hockey/5003/transactions?transactionsfilter=trade&count=25"
    scenario = {
        "pages": [
            {
                "html": "page one",
                "tradeCount": 25,
                "pagers": [{"href": next_url, "terminal": False}] * 2,
            },
            {"html": "page two", "tradeCount": 1, "pagers": [{"href": None, "terminal": True}] * 2},
        ]
    }
    result, closed = invoke(tmp_path, scenario, "scan-trades", "2026", "5003")
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output["pages"] == ["page one", "page two"]
    assert output["complete"] is True
    assert output["transaction_count"] == 26
    assert closed.exists()


@pytest.mark.parametrize(
    "scenario,error",
    [
        ({"tradeCount": 25}, "terminal pagination"),
        ({"tradeCount": 1, "pagers": [{"href": None, "terminal": False}]}, "pagination marker"),
        ({"tradeCount": 26, "pagers": [{"href": None, "terminal": True}]}, "page size"),
        (
            {
                "tradeCount": 1,
                "next": [
                    "https://hockey.fantasysports.yahoo.com/hockey/5003/transactions?transactionsfilter=trade&count=25"
                ],
            },
            "page size",
        ),
        (
            {
                "next": [
                    "https://hockey.fantasysports.yahoo.com/hockey/5003/transactions?transactionsfilter=trade&count=50"
                ]
            },
            "pagination offset",
        ),
        ({"loop": True}, "pagination incomplete"),
    ],
)
def test_pagination_refuses_unproven_completeness(tmp_path, scenario, error):
    result, _ = invoke(tmp_path, scenario, "scan-trades", "2026", "5003")
    assert result.returncode != 0
    assert error in result.stderr
    assert result.stdout == ""


def test_missing_profile_never_creates_browser_session(tmp_path):
    result, closed = invoke(tmp_path, {}, profile=tmp_path / "missing-profile")
    assert result.returncode != 0
    assert "ENOENT" in result.stderr
    assert not closed.exists()


@pytest.mark.parametrize("command", ["reconcile", "scan-trades"])
@pytest.mark.parametrize("fallback", [False, True])
def test_season_specific_league_bare_first_and_archive_fallback(tmp_path, command, fallback):
    result, closed = invoke(tmp_path, {"bareUnavailable": fallback}, command, "2024", "17419")
    assert result.returncode == 0, result.stderr
    visits = json.loads(Path(str(closed) + ".visits").read_text())
    root = "https://hockey.fantasysports.yahoo.com"
    expected = [root + "/hockey/17419/draftresults"]
    if fallback:
        expected.append(root + "/2024/hockey/17419/draftresults")
    if command == "scan-trades":
        expected.append(root + ("/2024" if fallback else "") +
                        "/hockey/17419/transactions?transactionsfilter=trade")
    assert visits == expected
