"""Run with python3 -m src.keeper.cli; no changes without --apply."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import subprocess
from pathlib import Path
from typing import Any

from .collect import parse_collection
from .core import from_snapshot, reconcile, scanTrades
from .sheet import TEST_SHEET, Sheets, apply_plan, make_plan, verify


def save_json(path: Path, data: Any) -> None:
    temporary = path.with_suffix(".tmp")
    with temporary.open("w") as file:
        json.dump(data, file, indent=2)
        file.flush()
        os.fsync(file.fileno())
    temporary.replace(path)
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["reconcile", "scan-trades"])
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--input", type=Path, help="Fixture or previously collected JSON")
    parser.add_argument("--profile", type=Path, help="Existing authenticated Yahoo profile")
    parser.add_argument("--league-id", type=int, default=5003)
    parser.add_argument("--sheet-id", default=TEST_SHEET)
    parser.add_argument("--state-dir", type=Path, default=Path.home() / ".local/state/nhl-keepers")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.apply and args.sheet_id != TEST_SHEET:
        parser.error("--apply is restricted to the TEST COPY")
    if not args.input and not args.profile:
        parser.error("provide --input or --profile")
    args.state_dir.mkdir(parents=True, exist_ok=True)
    # Lock by sheet, including across seasons, and hold through verification/state write.
    lock = args.state_dir / f"{args.sheet_id}.lock"
    with lock.open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.input:
            data = json.loads(args.input.read_text())
        else:
            scraper = Path(__file__).with_name("collect.mjs")
            output = subprocess.run(
                [
                    "node",
                    str(scraper),
                    args.command,
                    str(args.season),
                    str(args.profile),
                    str(args.league_id),
                ],
                capture_output=True,
                text=True,
                check=True,
                timeout=180,
            )
            collected = json.loads(output.stdout)
            data = parse_collection(collected, args.command, args.season, args.league_id)
        api = Sheets(args.sheet_id)
        before = api.read()
        state_file = args.state_dir / f"watermark-{args.sheet_id}-{args.season}.json"
        pending_file = args.state_dir / f"pending-{args.sheet_id}.json"
        if pending_file.exists():
            pending = json.loads(pending_file.read_text())
            if not args.apply:
                print("Pending apply requires recovery with --apply before new work")
                return
            if before["raw_formulas"] == pending["expected"]["raw_formulas"]:
                verify(before, pending["expected"])
                api.check_ui()
                if pending["state"] is not None:
                    save_json(args.state_dir / pending["state_file"], pending["state"])
                pending_file.unlink()
                print("Recovered verified prior apply; run again for new work")
                return
            if before != pending["before"]:
                raise ValueError("pending apply conflicts with current sheet; inspect backup")
            # Atomic batch did not land. Retry the identical recorded operation.
            apply_plan(
                api, args.sheet_id, before, pending["plan"], args.state_dir / "backups", apply=True
            )
            if pending["state"] is not None:
                save_json(args.state_dir / pending["state_file"], pending["state"])
            pending_file.unlink()
            print("Recovered pending apply; run again for new work")
            return
        state = None
        if args.command == "reconcile":
            rows = reconcile(data, before, season=args.season)
        else:
            state = json.loads(state_file.read_text()) if state_file.exists() else None
            rows, state = scanTrades(
                from_snapshot(before),
                data,
                season=args.season,
                state=state,
                known_teams=list(dict.fromkeys(r[0] for r in before["raw_values"][3:])),
            )
        plan = make_plan(before, rows)
        print(
            json.dumps(
                {
                    "dry_run": not args.apply,
                    "sheet_id": args.sheet_id,
                    "diff": plan["diff"],
                    "proposed_writes": plan["requests"],
                },
                indent=2,
            )
        )
        if args.apply:
            save_json(
                pending_file,
                {
                    "before": before,
                    "expected": plan["expected"],
                    "plan": plan,
                    "state": state,
                    "state_file": state_file.name,
                },
            )
        backup = apply_plan(
            api, args.sheet_id, before, plan, args.state_dir / "backups", apply=args.apply
        )
        if args.apply and state is not None:
            save_json(state_file, state)
        if args.apply:
            pending_file.unlink()
        if backup:
            print(f"Verified TEST COPY. Backup: {backup}")


if __name__ == "__main__":
    main()
