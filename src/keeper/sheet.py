"""Formula-preserving Sheets plans and the deliberately test-copy-only adapter."""

from __future__ import annotations

import copy
import importlib.util
import json
import os
import re
from datetime import datetime, timezone
from importlib.abc import Loader
from importlib.machinery import ModuleSpec
from pathlib import Path
from typing import Any, cast
from urllib.parse import quote

from .core import Keeper, match, team_key

TEST_SHEET = "1E8P5w5ensWavBPQBO66sMmqAmFBGP0c11AhT91FPxbk"
FORMULA_COLUMNS = (0, 1, 3, 5)
ERROR_PREFIXES = ("#REF!", "#ERROR!", "#N/A", "#VALUE!", "#DIV/0!", "#NAME?", "#NUM!", "#NULL!")


def shifted(formula: str, offset: int) -> str:
    # Only local relative references; quoted cross-tab references are untouched.
    parts = re.split(r"('[^']*'![^,\)]+)", formula)
    for i in range(0, len(parts), 2):
        parts[i] = re.sub(
            r"(?<![A-Za-z0-9_$])([A-Z]+)([0-9]+)",
            lambda m: str(m[1]) + str(int(m[2]) + offset),
            parts[i],
        )
    return "".join(parts)


def grid(start: int, end: int, col: int, last: int | None = None) -> dict[str, Any]:
    return {
        "sheetId": 0,
        "startRowIndex": start,
        "endRowIndex": end,
        "startColumnIndex": col,
        "endColumnIndex": col + 1 if last is None else last,
    }


def make_plan(snapshot: dict[str, Any], rows: list[Keeper]) -> dict[str, Any]:
    values, formulas = snapshot["raw_values"], snapshot["raw_formulas"]
    if len(values) != len(formulas) or len(values) < 4:
        raise ValueError("invalid snapshot shape")
    blocks: list[dict[str, Any]] = []
    for i, row in enumerate(values[3:], 3):
        if len(row) < 7 or len(formulas[i]) < 7:
            raise ValueError("incomplete sheet row")
        if not all(
            isinstance(formulas[i][c], str) and formulas[i][c].startswith("=")
            for c in FORMULA_COLUMNS
        ):
            raise ValueError("missing formula in protected column")
        if not blocks or blocks[-1]["team"] != row[0]:
            blocks.append({"team": row[0], "start": i, "count": 0})
        blocks[-1]["count"] += 1
    if len({team_key(b["team"]) for b in blocks}) != len(blocks):
        raise ValueError("non-contiguous owner blocks")
    if any(team_key(r.team) not in {team_key(b["team"]) for b in blocks} for r in rows):
        raise ValueError("unknown team in output")
    requests: list[dict[str, Any]] = []
    for block in reversed(blocks):
        wanted = sum(team_key(r.team) == team_key(block["team"]) for r in rows)
        # Keep an empty template row for a team temporarily holding zero keepers.
        count = max(1, wanted)
        start, old = block["start"], block["count"]
        if count < old:
            requests.append(
                {
                    "deleteDimension": {
                        "range": {
                            "sheetId": 0,
                            "dimension": "ROWS",
                            "startIndex": start + count,
                            "endIndex": start + old,
                        }
                    }
                }
            )
        elif count > old:
            end = start + old
            requests.append(
                {
                    "insertDimension": {
                        "range": {
                            "sheetId": 0,
                            "dimension": "ROWS",
                            "startIndex": end,
                            "endIndex": start + count,
                        },
                        "inheritFromBefore": True,
                    }
                }
            )
            for paste in ("PASTE_FORMAT", "PASTE_DATA_VALIDATION"):
                requests.append(
                    {
                        "copyPaste": {
                            "source": grid(end - 1, end, 0, 7),
                            "destination": grid(end, start + count, 0, 7),
                            "pasteType": paste,
                        }
                    }
                )
            for col in FORMULA_COLUMNS:
                requests.append(
                    {
                        "copyPaste": {
                            "source": grid(end - 1, end, col),
                            "destination": grid(end, start + count, col),
                            "pasteType": "PASTE_FORMULA",
                        }
                    }
                )
    expected = {
        "raw_values": copy.deepcopy(values[:3]),
        "raw_formulas": copy.deepcopy(formulas[:3]),
    }
    cursor = 3
    diffs = []
    for block in blocks:
        source = block["start"]
        desired = [r for r in rows if team_key(r.team) == team_key(block["team"])]
        before = [r[2] for r in values[source : source + block["count"]] if r[2]]
        after = [r.player for r in desired]
        updated = []
        for keeper in desired:
            previous_name = match(keeper.player, [r[2].strip() for r in values[3:] if r[2].strip()])
            previous = next((r for r in values[3:] if r[2].strip() == previous_name), None)
            old_year = int(previous[4]) if previous else None
            old_count = int(previous[6]) if previous else None
            if (old_year, old_count) != (keeper.first_year, keeper.traded):
                updated.append(
                    {
                        "player": keeper.player,
                        "first_year": {"before": old_year, "after": keeper.first_year},
                        "trade_count": {"before": old_count, "after": keeper.traded},
                    }
                )
        diffs.append(
            {
                "team": block["team"],
                "added": [p for p in after if p not in before],
                "removed": [p for p in before if p not in after],
                "updated": updated,
            }
        )
        if not desired:
            desired = [Keeper(block["team"], "", int(values[0][1]), 0)]
        for keeper in desired:
            row = list(values[source])
            frow = list(formulas[source])
            for col in FORMULA_COLUMNS:
                frow[col] = shifted(formulas[source][col], cursor - source)
            for col, value in ((2, keeper.player), (4, keeper.first_year), (6, keeper.traded)):
                row[col] = str(value)
                frow[col] = value
            expected["raw_values"].append(row)
            expected["raw_formulas"].append(frow)
            cursor += 1
    expected["raw_validation"] = []
    for row in range(3, cursor):
        cell = f"G{row + 1}"
        rule = {
            "condition": {
                "type": "CUSTOM_FORMULA",
                "values": [
                    {"userEnteredValue": f"=AND(ISNUMBER({cell}),{cell}>=0,MOD({cell},1)=0)"}
                ],
            },
            "strict": True,
        }
        requests.append({"setDataValidation": {"range": grid(row, row + 1, 6), "rule": rule}})
        expected["raw_validation"].append(rule)
    for col in (2, 4, 6):
        requests.append(
            {
                "updateCells": {
                    "range": grid(3, cursor, col),
                    "rows": [
                        {
                            "values": [
                                {
                                    "userEnteredValue": {
                                        "stringValue" if col == 2 else "numberValue": row[col]
                                    }
                                }
                            ]
                        }
                        for row in expected["raw_formulas"][3:]
                    ],
                    "fields": "userEnteredValue",
                }
            }
        )
    return {"requests": requests, "diff": diffs, "expected": expected}


def verify(actual: dict[str, Any], expected: dict[str, Any]) -> None:
    if actual.get("raw_validation") != expected.get("raw_validation"):
        raise ValueError("post-write count validation verification failed")
    if actual["raw_formulas"] != expected["raw_formulas"]:
        raise ValueError("post-write formula/value verification failed; backup retained")
    if [(r[0], r[1]) for r in actual["raw_values"][3:]] != [
        (r[0], r[1]) for r in expected["raw_values"][3:]
    ]:
        raise ValueError("post-write owner alignment verification failed")
    if any(str(v).startswith(ERROR_PREFIXES) for r in actual["raw_values"] for v in r):
        raise ValueError("post-write formula error verification failed")


def apply_plan(
    api: Any,
    sheet_id: str,
    before: dict[str, Any],
    plan: dict[str, Any],
    backup_dir: Path,
    *,
    apply: bool = False,
) -> Path | None:
    if not apply:
        return None
    if sheet_id != TEST_SHEET:
        raise ValueError("apply is restricted to the TEST COPY")
    if api.read() != before:
        raise ValueError("sheet changed since planning; rerun dry-run")
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    path = backup_dir / f"raw-data-{stamp}.json"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as file:
        json.dump(before, file, indent=2)
        file.flush()
        os.fsync(file.fileno())
    api.write(plan["requests"])
    verify(api.read(), plan["expected"])
    api.check_ui()
    return path


class Sheets:
    def __init__(
        self, sheet_id: str = TEST_SHEET, helper: str = "/home/david/.config/sheets-cli/sheets.py"
    ):
        self.sheet_id = sheet_id
        spec = cast(
            ModuleSpec, importlib.util.spec_from_file_location("keeper_sheets_helper", helper)
        )
        module = importlib.util.module_from_spec(spec)
        cast(Loader, spec.loader).exec_module(module)
        self.call = module.call
        metadata = self.call(sheet_id, fields="sheets(properties)")
        self.tabs = {s["properties"]["title"]: s["properties"] for s in metadata["sheets"]}
        if self.tabs.get("Raw Data", {}).get("sheetId") != 0:
            raise ValueError("Raw Data sheetId must be 0")

    def values(self, range_name: str, render: str = "FORMATTED_VALUE") -> list[list[Any]]:
        return cast(
            list[list[Any]],
            self.call(
                f"{self.sheet_id}/values/{quote(range_name, safe='!:')}", valueRenderOption=render
            ).get("values", []),
        )

    def read(self) -> dict[str, Any]:
        limit = self.tabs["Raw Data"]["gridProperties"]["rowCount"]
        range_name = f"'Raw Data'!A1:G{limit}"
        snapshot: dict[str, Any] = {
            "raw_values": self.values(range_name),
            "raw_formulas": self.values(range_name, "FORMULA"),
        }
        owners = self.values("'List Of Teams And Owners'!A2:B13")
        blocks = list(dict.fromkeys((r[0], r[1]) for r in snapshot["raw_values"][3:]))
        if blocks != [tuple(r) for r in owners]:
            raise ValueError("owner blocks do not match List Of Teams And Owners")
        for row, formula in zip(snapshot["raw_values"][3:], snapshot["raw_formulas"][3:]):
            owner_index = owners.index([row[0], row[1]]) + 2
            if formula[1] != f"='List Of Teams And Owners'!$B${owner_index}":
                raise ValueError("owner formula points to wrong owner cell")
        validations = (
            self.call(
                self.sheet_id,
                ranges=f"'Raw Data'!G4:G{len(snapshot['raw_values'])}",
                fields="sheets(data(rowData(values(dataValidation))))",
            )["sheets"][0]
            .get("data", [{}])[0]
            .get("rowData", [])
        )
        snapshot["raw_validation"] = [
            (
                validations[i].get("values", [{}])[0].get("dataValidation", {})
                if i < len(validations)
                else {}
            )
            for i in range(len(snapshot["raw_values"]) - 3)
        ]
        return snapshot

    def write(self, requests: list[dict[str, Any]]) -> None:
        if self.sheet_id != TEST_SHEET:
            raise ValueError("apply is restricted to the TEST COPY")
        self.call(f"{self.sheet_id}:batchUpdate", method="POST", body={"requests": requests})

    def check_ui(self) -> None:
        props = self.tabs["UI"]["gridProperties"]
        # Existing UI uses at most AB; read its metadata-grounded populated grid.
        rows = self.values(f"'UI'!A1:AB{props['rowCount']}")
        if any(str(v).startswith(ERROR_PREFIXES) for row in rows for v in row):
            raise ValueError("UI formula error verification failed")
