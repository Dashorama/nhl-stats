"""Command-line interface for NHL scraper."""

import asyncio
from typing import Any

import click
from rich.console import Console
from rich.table import Table

from .backfill import (
    backfill_games,
    backfill_play_by_play,
    backfill_shots,
    games_needing_play_by_play,
)
from .scrapers import (
    MoneyPuckScraper,
    NHLAPIScraper,
    NHLRosterScraper,
    NHLShiftChartScraper,
    PuckPediaScraper,
)
from .scrapers.yahoo_fantasy import YahooFantasyClient
from .storage import BoxscoreRecord, Database, GameRecord, PlayerRecord
from .storage.validation import (
    CorpusError,
    assert_pbp_corpus,
    run_integrity_checks,
    seasons_requiring_pbp,
)
from .utils import setup_logging

console = Console()


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging")
@click.option("--json-logs", is_flag=True, help="Output logs as JSON")
@click.pass_context
def main(ctx: click.Context, verbose: bool, json_logs: bool) -> None:
    """NHL Stats - Collect hockey data from multiple sources."""
    ctx.ensure_object(dict)
    setup_logging(level="DEBUG" if verbose else "INFO", json_output=json_logs)
    ctx.obj["db"] = Database()


@main.command()
@click.pass_context
def stats(ctx: click.Context) -> None:
    """Show database statistics."""
    db: Database = ctx.obj["db"]
    counts = db.get_stats()

    table = Table(title="Database Statistics")
    table.add_column("Entity", style="cyan")
    table.add_column("Count", justify="right", style="green")

    for entity, count in counts.items():
        table.add_row(entity.title(), str(count))

    console.print(table)


@main.command()
@click.option("--season", "-s", help="Season (e.g., 20232024)")
@click.pass_context
def scrape_teams(ctx: click.Context, season: str | None) -> None:
    """Scrape team data from NHL API."""
    db: Database = ctx.obj["db"]

    async def run() -> None:
        async with NHLAPIScraper() as scraper:
            teams = await scraper.scrape_teams()
            db.upsert_teams(teams)
            console.print(f"[green]✓ Scraped {len(teams)} teams[/green]")

    asyncio.run(run())


@main.command()
@click.option("--season", "-s", help="Season (e.g., 20232024)")
@click.pass_context
def scrape_players(ctx: click.Context, season: str | None) -> None:
    """Scrape player data from NHL API."""
    db: Database = ctx.obj["db"]

    async def run() -> None:
        async with NHLAPIScraper() as scraper:
            players = await scraper.scrape_players(season)
            db.upsert_players(players)
            console.print(f"[green]✓ Scraped {len(players)} players[/green]")

    asyncio.run(run())


@main.command()
@click.option("--season", "-s", help="Season (e.g., 20232024)")
@click.pass_context
def scrape_games(ctx: click.Context, season: str | None) -> None:
    """Scrape game schedule from NHL API."""
    db: Database = ctx.obj["db"]

    async def run() -> None:
        async with NHLAPIScraper() as scraper:
            games = await scraper.scrape_games(season)
            db.upsert_games(games)
            console.print(f"[green]✓ Scraped {len(games)} games[/green]")

    asyncio.run(run())


@main.command()
@click.option("--season", "-s", help="Season (e.g., 20232024)")
@click.pass_context
def scrape_all(ctx: click.Context, season: str | None) -> None:
    """Scrape all data from NHL API."""
    db: Database = ctx.obj["db"]

    async def run() -> None:
        async with NHLAPIScraper() as scraper:
            console.print("[bold]Scraping teams...[/bold]")
            teams = await scraper.scrape_teams()
            db.upsert_teams(teams)
            console.print(f"  [green]✓ {len(teams)} teams[/green]")

            console.print("[bold]Scraping players...[/bold]")
            players = await scraper.scrape_players(season)
            db.upsert_players(players)
            console.print(f"  [green]✓ {len(players)} players[/green]")

            console.print("[bold]Scraping games...[/bold]")
            games = await scraper.scrape_games(season)
            db.upsert_games(games)
            console.print(f"  [green]✓ {len(games)} games[/green]")

            console.print("\n[bold green]All done![/bold green]")

    asyncio.run(run())


@main.command()
@click.pass_context
def standings(ctx: click.Context) -> None:
    """Show current NHL standings."""

    async def run() -> None:
        async with NHLAPIScraper() as scraper:
            data = await scraper.scrape_standings()

            for division in ["Atlantic", "Metropolitan", "Central", "Pacific"]:
                table = Table(title=f"{division} Division")
                table.add_column("Team", style="cyan")
                table.add_column("GP", justify="right")
                table.add_column("W", justify="right", style="green")
                table.add_column("L", justify="right", style="red")
                table.add_column("OT", justify="right")
                table.add_column("PTS", justify="right", style="bold")
                table.add_column("GF", justify="right")
                table.add_column("GA", justify="right")
                table.add_column("Diff", justify="right")

                div_teams = [t for t in data["teams"] if t["division"] == division]
                div_teams.sort(key=lambda t: t["points"], reverse=True)

                for t in div_teams:
                    diff = t["goal_diff"]
                    diff_str = f"+{diff}" if diff > 0 else str(diff)
                    table.add_row(
                        t["team"],
                        str(t["games_played"]),
                        str(t["wins"]),
                        str(t["losses"]),
                        str(t["ot_losses"]),
                        str(t["points"]),
                        str(t["goals_for"]),
                        str(t["goals_against"]),
                        diff_str,
                    )

                console.print(table)
                console.print()

    asyncio.run(run())


@main.command()
@click.option("--team", "-t", help="Team abbreviation (e.g., TOR)")
@click.option("--season", "-s", help="Season (e.g., 20242025)")
@click.pass_context
def scrape_rosters(ctx: click.Context, team: str | None, season: str | None) -> None:
    """Scrape full rosters from NHL API."""
    db: Database = ctx.obj["db"]

    async def run() -> None:
        async with NHLRosterScraper() as scraper:
            if team:
                console.print(f"[bold]Scraping roster for {team}...[/bold]")
                roster = await scraper.scrape_roster(team, season)
                db.upsert_rosters([roster])
                total = (
                    len(roster.get("forwards", []))
                    + len(roster.get("defensemen", []))
                    + len(roster.get("goalies", []))
                )
                console.print(f"[green]✓ Scraped {total} players for {team}[/green]")
            else:
                console.print("[bold]Scraping all team rosters...[/bold]")
                rosters = await scraper.scrape_all_rosters(season)
                db.upsert_rosters(rosters)
                total = sum(
                    len(r.get("forwards", []))
                    + len(r.get("defensemen", []))
                    + len(r.get("goalies", []))
                    for r in rosters
                )
                console.print(
                    f"[green]✓ Scraped {total} players across {len(rosters)} teams[/green]"
                )

    asyncio.run(run())


@main.command()
@click.option("--season", "-s", help="Season year (e.g., 2024)")
@click.pass_context
def scrape_advanced(ctx: click.Context, season: str | None) -> None:
    """Scrape advanced stats from MoneyPuck."""
    db: Database = ctx.obj["db"]

    async def run() -> None:
        async with MoneyPuckScraper() as scraper:
            console.print("[bold]Downloading MoneyPuck skater stats...[/bold]")
            skaters = await scraper.scrape_skater_stats(season)
            db.upsert_advanced_stats(skaters)
            console.print(f"  [green]✓ {len(skaters)} skaters[/green]")

            console.print("[bold]Downloading MoneyPuck goalie stats...[/bold]")
            goalies = await scraper.scrape_goalie_stats(season)
            db.upsert_advanced_stats(goalies)
            console.print(f"  [green]✓ {len(goalies)} goalies[/green]")

            console.print("\n[bold green]Advanced stats complete![/bold green]")

    asyncio.run(run())


@main.command()
@click.option("--team", "-t", help="Team abbreviation (e.g., TOR)")
@click.pass_context
def scrape_contracts(ctx: click.Context, team: str | None) -> None:
    """Scrape contract data from PuckPedia."""
    db: Database = ctx.obj["db"]

    async def run() -> None:
        async with PuckPediaScraper() as scraper:
            if team:
                console.print(f"[bold]Scraping contracts for {team}...[/bold]")
                contracts = await scraper.scrape_team_contracts(team)
                db.upsert_contracts(contracts)
                console.print(f"[green]✓ Scraped {len(contracts)} contracts[/green]")
            else:
                console.print("[bold]Scraping all team contracts...[/bold]")
                console.print(
                    "[dim](This may take a while to be respectful to PuckPedia's servers)[/dim]"
                )
                contracts = await scraper.scrape_all_contracts()
                db.upsert_contracts(contracts)
                console.print(f"[green]✓ Scraped {len(contracts)} contracts[/green]")

    asyncio.run(run())


@main.command()
@click.option("--year", "-y", type=int, help="Draft year (e.g., 2024)")
@click.pass_context
def scrape_draft(ctx: click.Context, year: int | None) -> None:
    """Scrape draft rankings from NHL API."""
    db: Database = ctx.obj["db"]

    async def run() -> None:
        async with NHLAPIScraper() as scraper:
            if year:
                console.print(f"[bold]Scraping {year} draft...[/bold]")
                picks = await scraper.scrape_draft(year)
                db.upsert_draft_picks(picks)
                console.print(f"[green]✓ Scraped {len(picks)} draft picks for {year}[/green]")
            else:
                # Scrape last 10 years
                from datetime import datetime

                current_year = datetime.now().year
                all_picks = []
                for y in range(current_year, current_year - 10, -1):
                    console.print(f"  Scraping {y} draft...")
                    try:
                        picks = await scraper.scrape_draft(y)
                        db.upsert_draft_picks(picks)
                        all_picks.extend(picks)
                        console.print(f"  [green]✓ {len(picks)} picks[/green]")
                    except Exception as e:
                        console.print(f"  [yellow]⚠ {y}: {e}[/yellow]")
                console.print(f"\n[green]✓ Total: {len(all_picks)} draft picks[/green]")

    asyncio.run(run())


@main.command()
@click.option("--limit", "-l", type=int, help="Max games to scrape (for testing)")
@click.pass_context
def scrape_boxscores(ctx: click.Context, limit: int | None) -> None:
    """Scrape game boxscores from NHL API."""
    db: Database = ctx.obj["db"]

    async def run() -> None:
        # Get completed regular season game IDs from DB
        with db.get_session() as session:
            query = session.query(GameRecord.id).filter(
                GameRecord.game_type == "2", GameRecord.game_state.in_(["OFF", "FINAL"])
            )
            game_ids = [r[0] for r in query.all()]

        if limit:
            game_ids = game_ids[:limit]

        console.print(f"[bold]Scraping boxscores for {len(game_ids)} games...[/bold]")

        async with NHLAPIScraper() as scraper:
            scraped = 0
            for i, game_id in enumerate(game_ids):
                try:
                    result = await scraper.scrape_boxscore(game_id)
                    db.upsert_boxscores(game_id, result["players"])
                    scraped += 1
                    if (i + 1) % 50 == 0:
                        console.print(f"  [dim]Progress: {i + 1}/{len(game_ids)}[/dim]")
                except Exception as e:
                    console.print(f"  [yellow]⚠ Game {game_id}: {e}[/yellow]")

        console.print(f"[green]✓ Scraped boxscores for {scraped} games[/green]")

    asyncio.run(run())


@main.command()
@click.option("--limit", "-l", type=int, help="Max games to scrape (for testing)")
@click.pass_context
def scrape_pbp(ctx: click.Context, limit: int | None) -> None:
    """Scrape play-by-play data from NHL API."""
    db: Database = ctx.obj["db"]

    async def run() -> None:
        with db.get_session() as session:
            query = session.query(GameRecord.id).filter(
                GameRecord.game_type == "2", GameRecord.game_state.in_(["OFF", "FINAL"])
            )
            game_ids = [r[0] for r in query.all()]

        if limit:
            game_ids = game_ids[:limit]

        console.print(f"[bold]Scraping play-by-play for {len(game_ids)} games...[/bold]")

        async with NHLAPIScraper() as scraper:
            scraped = 0
            total_events = 0
            for i, game_id in enumerate(game_ids):
                try:
                    events = await scraper.scrape_play_by_play(game_id)
                    db.insert_play_by_play(game_id, events)
                    scraped += 1
                    total_events += len(events)
                    if (i + 1) % 50 == 0:
                        console.print(
                            f"  [dim]Progress: {i + 1}/{len(game_ids)} "
                            f"({total_events} events)[/dim]"
                        )
                except Exception as e:
                    console.print(f"  [yellow]⚠ Game {game_id}: {e}[/yellow]")

        console.print(f"[green]✓ Scraped {total_events} events from {scraped} games[/green]")

    asyncio.run(run())


@main.command()
@click.option("--season", "-s", help="Season (e.g., 20242025)")
@click.pass_context
def scrape_full(ctx: click.Context, season: str | None) -> None:
    """Scrape all data from all sources."""
    db: Database = ctx.obj["db"]

    async def run() -> None:
        # NHL API - basic data
        async with NHLAPIScraper() as scraper:
            console.print("[bold cyan]═══ NHL API ═══[/bold cyan]")

            console.print("  Scraping teams...")
            teams = await scraper.scrape_teams()
            db.upsert_teams(teams)
            console.print(f"  [green]✓ {len(teams)} teams[/green]")

            console.print("  Scraping players...")
            players = await scraper.scrape_players(season)
            db.upsert_players(players)
            console.print(f"  [green]✓ {len(players)} players[/green]")

        # NHL Roster API
        async with NHLRosterScraper() as scraper:
            console.print("\n[bold cyan]═══ Rosters ═══[/bold cyan]")
            rosters = await scraper.scrape_all_rosters(season)
            db.upsert_rosters(rosters)
            total = sum(
                len(r.get("forwards", []))
                + len(r.get("defensemen", []))
                + len(r.get("goalies", []))
                for r in rosters
            )
            console.print(f"  [green]✓ {total} roster entries[/green]")

        # MoneyPuck advanced stats
        async with MoneyPuckScraper() as scraper:
            console.print("\n[bold cyan]═══ Advanced Stats (MoneyPuck) ═══[/bold cyan]")
            skaters = await scraper.scrape_skater_stats(season)
            goalies = await scraper.scrape_goalie_stats(season)
            db.upsert_advanced_stats(skaters + goalies)
            console.print(f"  [green]✓ {len(skaters)} skaters, {len(goalies)} goalies[/green]")

        # PuckPedia contracts
        async with PuckPediaScraper() as scraper:
            console.print("\n[bold cyan]═══ Contracts (PuckPedia) ═══[/bold cyan]")
            console.print("  [dim](Slow scrape to respect their servers)[/dim]")
            contracts = await scraper.scrape_all_contracts()
            db.upsert_contracts(contracts)
            console.print(f"  [green]✓ {len(contracts)} contracts[/green]")

        console.print("\n[bold green]═══ All Done! ═══[/bold green]")

    asyncio.run(run())


@main.command()
@click.argument("team")
@click.pass_context
def show_roster(ctx: click.Context, team: str) -> None:
    """Display team roster in formatted table."""

    async def run() -> None:
        async with NHLRosterScraper() as scraper:
            roster = await scraper.scrape_roster(team.upper())

            console.print(f"\n[bold]{team.upper()} Roster[/bold]")
            console.print(f"[dim]As of {roster['as_of_date'][:10]}[/dim]\n")

            # Forwards
            if roster["forwards"]:
                table = Table(title="Forwards", show_header=True)
                table.add_column("#", style="cyan", width=3)
                table.add_column("Name", style="white")
                table.add_column("Pos", style="green")
                table.add_column("Shoots", style="dim")
                table.add_column("Country", style="dim")

                for p in sorted(roster["forwards"], key=lambda x: x.get("jersey_number") or 99):
                    table.add_row(
                        str(p.get("jersey_number", "")),
                        f"{p['first_name']} {p['last_name']}",
                        p.get("position", ""),
                        p.get("shoots_catches", ""),
                        p.get("birth_country", ""),
                    )
                console.print(table)

            # Defensemen
            if roster["defensemen"]:
                table = Table(title="Defensemen", show_header=True)
                table.add_column("#", style="cyan", width=3)
                table.add_column("Name", style="white")
                table.add_column("Shoots", style="dim")
                table.add_column("Country", style="dim")

                for p in sorted(roster["defensemen"], key=lambda x: x.get("jersey_number") or 99):
                    table.add_row(
                        str(p.get("jersey_number", "")),
                        f"{p['first_name']} {p['last_name']}",
                        p.get("shoots_catches", ""),
                        p.get("birth_country", ""),
                    )
                console.print(table)

            # Goalies
            if roster["goalies"]:
                table = Table(title="Goalies", show_header=True)
                table.add_column("#", style="cyan", width=3)
                table.add_column("Name", style="white")
                table.add_column("Catches", style="dim")
                table.add_column("Country", style="dim")

                for p in sorted(roster["goalies"], key=lambda x: x.get("jersey_number") or 99):
                    table.add_row(
                        str(p.get("jersey_number", "")),
                        f"{p['first_name']} {p['last_name']}",
                        p.get("shoots_catches", ""),
                        p.get("birth_country", ""),
                    )
                console.print(table)

    asyncio.run(run())


@main.command()
@click.argument("player_id", type=int)
@click.pass_context
def show_player(ctx: click.Context, player_id: int) -> None:
    """Show detailed info for a player by ID."""

    async def run() -> None:
        async with NHLRosterScraper() as scraper:
            player = await scraper.scrape_player_details(player_id)

            console.print(f"\n[bold]{player['first_name']} {player['last_name']}[/bold]")
            console.print(
                f"[dim]#{player.get('jersey_number', 'N/A')} • "
                f"{player.get('position', 'N/A')} • "
                f"{player.get('team_abbrev', 'N/A')}[/dim]\n"
            )

            info_table = Table(show_header=False, box=None)
            info_table.add_column("Field", style="cyan")
            info_table.add_column("Value")

            info_table.add_row("Birth Date", player.get("birth_date", "N/A"))
            info_table.add_row(
                "Birthplace", f"{player.get('birth_city', '')}, {player.get('birth_country', '')}"
            )
            info_table.add_row(
                "Height",
                f"{player.get('height_inches', 0) // 12}'{player.get('height_inches', 0) % 12}\""
                if player.get("height_inches")
                else "N/A",
            )
            info_table.add_row("Weight", f"{player.get('weight_pounds', 'N/A')} lbs")
            info_table.add_row("Shoots/Catches", player.get("shoots_catches", "N/A"))

            if player.get("draft_year"):
                info_table.add_row(
                    "Draft",
                    f"{player['draft_year']} R{player.get('draft_round', '?')}, "
                    f"Pick {player.get('draft_pick', '?')} "
                    f"(#{player.get('draft_overall', '?')} overall) "
                    f"by {player.get('draft_team', 'N/A')}",
                )

            console.print(info_table)

            # Career stats summary if available
            career = player.get("career_stats", {})
            if career:
                console.print("\n[bold]Career Stats[/bold]")
                reg = career.get("regularSeason", {})
                if reg:
                    console.print(
                        f"  GP: {reg.get('gamesPlayed', 0)} | G: {reg.get('goals', 0)} | "
                        f"A: {reg.get('assists', 0)} | P: {reg.get('points', 0)}"
                    )

    asyncio.run(run())


@main.command()
@click.option("--season", "-s", help="Season (e.g., 20252026)")
@click.option("--limit", "-l", type=int, help="Max players to scrape")
@click.pass_context
def scrape_game_logs(ctx: click.Context, season: str | None, limit: int | None) -> None:
    """Scrape player game logs from NHL API."""
    db: Database = ctx.obj["db"]

    async def run() -> None:
        # Get player IDs from DB
        with db.get_session() as session:
            player_ids = [r[0] for r in session.query(PlayerRecord.id).all()]

        if limit:
            player_ids = player_ids[:limit]

        if not season:
            async with NHLAPIScraper() as s:
                season_id = await s.get_current_season()
        else:
            season_id = season

        console.print(f"[bold]Scraping game logs for {len(player_ids)} players...[/bold]")

        async with NHLAPIScraper() as scraper:
            scraped = 0
            total_logs = 0
            for i, pid in enumerate(player_ids):
                try:
                    logs = await scraper.scrape_player_game_log(pid, season_id)
                    if logs:
                        db.upsert_game_logs(pid, season_id, logs)
                        scraped += 1
                        total_logs += len(logs)
                except Exception:
                    pass  # Some players may not have game logs
                if (i + 1) % 100 == 0:
                    console.print(f"  [dim]Progress: {i + 1}/{len(player_ids)}[/dim]")

        console.print(
            f"[green]✓ Scraped {total_logs} game log entries for {scraped} players[/green]"
        )

    asyncio.run(run())


@main.command()
@click.option("--season", "-s", help="Season start year (e.g., 2025)")
@click.pass_context
def scrape_shots(ctx: click.Context, season: str | None) -> None:
    """Scrape shot-level data from MoneyPuck."""
    db: Database = ctx.obj["db"]

    async def run() -> None:
        async with MoneyPuckScraper() as scraper:
            console.print("[bold]Downloading MoneyPuck shot data...[/bold]")
            console.print("[dim](This is a large CSV download)[/dim]")
            shots = await scraper.scrape_shot_data(season)
            console.print(f"  Downloaded {len(shots)} shots, saving to database...")
            db.insert_shots(shots)
            console.print(f"[green]✓ Saved {len(shots)} shots[/green]")

    asyncio.run(run())


@main.command()
@click.option(
    "--daily", is_flag=True, help="Only update daily data (games, boxscores, PBP, game logs)"
)
@click.pass_context
def update(ctx: click.Context, daily: bool) -> None:
    """Update all data from all sources.

    Default: full update (all sources).
    --daily: only games, boxscores, play-by-play, and game logs.

    Designed to be called by cron. See OPERATIONS.md for details.
    """
    db: Database = ctx.obj["db"]

    async def run() -> None:
        errors = []

        # --- Always: NHL API core data ---
        async with NHLAPIScraper() as scraper:
            # Games (schedule + scores)
            console.print("[bold]Updating games...[/bold]")
            try:
                games = await scraper.scrape_games()
                db.upsert_games(games)
                console.print(f"  [green]✓ {len(games)} games[/green]")
            except Exception as e:
                errors.append(f"games: {e}")
                console.print(f"  [yellow]⚠ games: {e}[/yellow]")

            # Boxscores for completed games not yet in DB
            console.print("[bold]Updating boxscores...[/bold]")
            try:
                with db.get_session() as session:
                    all_finished = set(
                        r[0]
                        for r in session.query(GameRecord.id)
                        .filter(
                            GameRecord.game_type == "2", GameRecord.game_state.in_(["OFF", "FINAL"])
                        )
                        .all()
                    )
                    already_scraped = set(
                        r[0] for r in session.query(BoxscoreRecord.game_id).distinct().all()
                    )
                    new_game_ids = sorted(all_finished - already_scraped)

                if new_game_ids:
                    scraped = 0
                    for gid in new_game_ids:
                        try:
                            result = await scraper.scrape_boxscore(gid)
                            db.upsert_boxscores(gid, result["players"])
                            scraped += 1
                        except Exception:
                            pass
                    console.print(f"  [green]✓ {scraped} new boxscores[/green]")
                else:
                    console.print("  [dim]No new games to scrape[/dim]")
            except Exception as e:
                errors.append(f"boxscores: {e}")
                console.print(f"  [yellow]⚠ boxscores: {e}[/yellow]")

            # Play-by-play and shifts for new games in the current season.
            # Scoped to the current season on purpose: history is collected by
            # `nhl-stats backfill-pbp`, so a nightly run stays a few minutes long.
            console.print("[bold]Updating play-by-play...[/bold]")
            try:
                current_season = await scraper.get_current_season()
                new_pbp_ids = games_needing_play_by_play(db, [current_season])

                if new_pbp_ids:
                    async with NHLShiftChartScraper() as shift_scraper:
                        report = await backfill_play_by_play(
                            db,
                            new_pbp_ids,
                            scraper.scrape_play_by_play,
                            shift_scraper.scrape_shifts,
                        )
                    console.print(
                        f"  [green]✓ {report.events_written} events and "
                        f"{report.shifts_written} shifts from "
                        f"{report.games_collected} games[/green]"
                    )
                    if report.games_failed:
                        errors.append(f"pbp: {report.games_failed} games failed")
                else:
                    console.print("  [dim]No new PBP to scrape[/dim]")
            except Exception as e:
                errors.append(f"pbp: {e}")
                console.print(f"  [yellow]⚠ pbp: {e}[/yellow]")

            # Game logs for all players
            console.print("[bold]Updating game logs...[/bold]")
            try:
                season_id = await scraper.get_current_season()
                with db.get_session() as session:
                    player_ids = [r[0] for r in session.query(PlayerRecord.id).all()]

                updated = 0
                for pid in player_ids:
                    try:
                        logs = await scraper.scrape_player_game_log(pid, season_id)
                        if logs:
                            db.upsert_game_logs(pid, season_id, logs)
                            updated += 1
                    except Exception:
                        pass
                console.print(f"  [green]✓ game logs for {updated} players[/green]")
            except Exception as e:
                errors.append(f"game_logs: {e}")
                console.print(f"  [yellow]⚠ game_logs: {e}[/yellow]")

        if daily:
            errors.extend(_validate_after_update(db))
            _print_summary(errors)
            return

        # --- Weekly: heavier data ---
        async with NHLAPIScraper() as scraper:
            console.print("[bold]Updating teams/standings...[/bold]")
            try:
                teams = await scraper.scrape_teams()
                db.upsert_teams(teams)
                console.print(f"  [green]✓ {len(teams)} teams[/green]")
            except Exception as e:
                errors.append(f"teams: {e}")
                console.print(f"  [yellow]⚠ teams: {e}[/yellow]")

            console.print("[bold]Updating players...[/bold]")
            try:
                players = await scraper.scrape_players()
                db.upsert_players(players)
                console.print(f"  [green]✓ {len(players)} players[/green]")
            except Exception as e:
                errors.append(f"players: {e}")
                console.print(f"  [yellow]⚠ players: {e}[/yellow]")

        async with NHLRosterScraper() as scraper:
            console.print("[bold]Updating rosters...[/bold]")
            try:
                rosters = await scraper.scrape_all_rosters()
                db.upsert_rosters(rosters)
                total = sum(
                    len(r.get("forwards", []))
                    + len(r.get("defensemen", []))
                    + len(r.get("goalies", []))
                    for r in rosters
                )
                console.print(f"  [green]✓ {total} roster entries[/green]")
            except Exception as e:
                errors.append(f"rosters: {e}")
                console.print(f"  [yellow]⚠ rosters: {e}[/yellow]")

        async with MoneyPuckScraper() as scraper:
            console.print("[bold]Updating advanced stats...[/bold]")
            try:
                skaters = await scraper.scrape_skater_stats()
                goalies = await scraper.scrape_goalie_stats()
                db.upsert_advanced_stats(skaters + goalies)
                console.print(f"  [green]✓ {len(skaters)} skaters, {len(goalies)} goalies[/green]")
            except Exception as e:
                errors.append(f"advanced_stats: {e}")
                console.print(f"  [yellow]⚠ advanced_stats: {e}[/yellow]")

            console.print("[bold]Updating shot data...[/bold]")
            console.print("[dim](This is a large CSV download)[/dim]")
            try:
                shots = await scraper.scrape_shot_data()
                db.insert_shots(shots)
                console.print(f"  [green]✓ {len(shots)} shots[/green]")
            except Exception as e:
                errors.append(f"shots: {e}")
                console.print(f"  [yellow]⚠ shots: {e}[/yellow]")

        errors.extend(_validate_after_update(db))
        _print_summary(errors)

    asyncio.run(run())


@main.command()
@click.pass_context
def injuries(ctx: click.Context) -> None:
    """Update player injury/availability status."""
    from .scrapers.nhl_injuries import NHLInjuriesScraper

    db: Database = ctx.obj["db"]
    errors = []
    try:
        scraper = NHLInjuriesScraper()
        result = asyncio.run(scraper.scrape_all(db))
        click.echo(f"  ✓ {result['players']} players")
        if result["errors"]:
            errors.append(f"teams failed: {result['errors']}")
    except Exception as e:
        errors.append(f"injuries: {e}")
    _print_summary(errors)


# ── Data integrity: validation and backfills ───────────────────────


def _print_check_results(results: list[Any]) -> bool:
    """Render integrity checks. Returns True when every check passed."""
    table = Table(title="Data integrity")
    table.add_column("Check")
    table.add_column("Result")
    table.add_column("Detail")

    for result in results:
        # Marker plus colour: status must not depend on colour alone.
        marker = "[blue]PASS[/blue]" if result.passed else "[bold yellow]FAIL[/bold yellow]"
        table.add_row(result.name, marker, result.detail)

    console.print(table)
    return all(r.passed for r in results)


@main.command()
@click.option("--no-corpus", is_flag=True, help="Skip the play-by-play corpus assertion")
@click.option(
    "--require-seasons",
    help="Comma-separated 8-digit seasons play-by-play must cover (default: derived from schedule)",
)
@click.pass_context
def validate(ctx: click.Context, no_corpus: bool, require_seasons: str | None) -> None:
    """Check stored data for the integrity defects the audit found.

    Exits non-zero when a check fails, so cron and CI can gate on it.
    """
    import sys

    db: Database = ctx.obj["db"]

    passed = _print_check_results(run_integrity_checks(db))

    if not no_corpus:
        seasons = (
            [s.strip() for s in require_seasons.split(",") if s.strip()]
            if require_seasons
            else seasons_requiring_pbp(db)
        )
        if not seasons:
            console.print(
                "[yellow]No season has a complete enough schedule to require "
                "play-by-play yet - corpus assertion skipped.[/yellow]"
            )
        else:
            try:
                counts = assert_pbp_corpus(db, seasons)
            except CorpusError as exc:
                console.print(f"[bold yellow]FAIL[/bold yellow] pbp_corpus: {exc}")
                passed = False
            else:
                covered = ", ".join(f"{s}={counts.get(s, 0)}" for s in seasons)
                console.print(f"[blue]PASS[/blue] pbp_corpus: {covered}")

    if not passed:
        console.print("\n[bold yellow]Data integrity checks failed.[/bold yellow]")
        sys.exit(1)

    console.print("\n[bold blue]All data integrity checks passed.[/bold blue]")


@main.command("backfill-games")
@click.option("--start-season", default=2015, type=int, help="First season start year")
@click.option("--end-season", type=int, help="Last season start year (default: current)")
@click.option("--rate", default=3.0, type=float, help="Requests per second")
@click.pass_context
def backfill_games_cmd(
    ctx: click.Context, start_season: int, end_season: int | None, rate: float
) -> None:
    """Re-scrape schedules so stored games regain their season and date.

    Safe to re-run: existing rows are updated in place, and any season the API
    could not supply is derived from the game id.
    """
    db: Database = ctx.obj["db"]

    async def run() -> None:
        async with NHLAPIScraper(requests_per_second=rate) as scraper:
            last = (
                end_season
                if end_season is not None
                else int((await scraper.get_current_season())[:4])
            )
            seasons = [f"{y}{y + 1}" for y in range(start_season, last + 1)]
            console.print(f"[bold]Backfilling games for {len(seasons)} seasons...[/bold]")

            report = await backfill_games(db, seasons, scraper.scrape_games)

        console.print(f"  [blue]{report.games_written} games written[/blue]")
        console.print(
            f"  [blue]{report.games_repaired_from_ids} seasons derived from game ids[/blue]"
        )
        if report.failures:
            console.print(
                f"  [yellow]{len(report.failures)} seasons failed: {report.failures}[/yellow]"
            )

    asyncio.run(run())


@main.command("backfill-shots")
@click.option("--start-season", default=2018, type=int, help="First MoneyPuck season (start year)")
@click.option("--end-season", type=int, help="Last MoneyPuck season (default: current)")
@click.pass_context
def backfill_shots_cmd(ctx: click.Context, start_season: int, end_season: int | None) -> None:
    """Re-ingest MoneyPuck shot data so situation, is_home and game_id are correct.

    Each season is replaced wholesale, so this is safe to re-run. Downloads are
    large (~20MB per season).
    """
    db: Database = ctx.obj["db"]

    async def run() -> None:
        async with MoneyPuckScraper() as scraper:
            last = end_season if end_season is not None else int(await scraper.get_current_season())
            seasons = [str(y) for y in range(start_season, last + 1)]
            console.print(f"[bold]Re-ingesting shots for {len(seasons)} seasons...[/bold]")

            report = await backfill_shots(db, seasons, scraper.scrape_shot_data)

        console.print(
            f"  [blue]{report.shots_written} shots across {report.seasons_collected} seasons[/blue]"
        )
        if report.failures:
            console.print(
                f"  [yellow]{len(report.failures)} seasons failed: {report.failures}[/yellow]"
            )

    asyncio.run(run())


@main.command("backfill-pbp")
@click.option("--start-season", default=2018, type=int, help="First season start year")
@click.option("--end-season", type=int, help="Last season start year (default: current)")
@click.option("--with-shifts/--no-shifts", default=True, help="Also collect shift charts")
@click.option("--refetch", is_flag=True, help="Re-fetch games that already have events")
@click.option("--limit", type=int, help="Stop after this many games (for testing)")
@click.option("--rate", default=4.0, type=float, help="Requests per second")
@click.pass_context
def backfill_pbp_cmd(
    ctx: click.Context,
    start_season: int,
    end_season: int | None,
    with_shifts: bool,
    refetch: bool,
    limit: int | None,
    rate: float,
) -> None:
    """Backfill play-by-play (and shift charts) for past seasons.

    Resumable and idempotent: games that already have events are skipped unless
    --refetch is given, and a game's rows are replaced rather than appended.
    """
    db: Database = ctx.obj["db"]

    async def run() -> None:
        async with NHLAPIScraper(requests_per_second=rate) as scraper:
            last = (
                end_season
                if end_season is not None
                else int((await scraper.get_current_season())[:4])
            )
            seasons = [f"{y}{y + 1}" for y in range(start_season, last + 1)]

            game_ids = games_needing_play_by_play(db, seasons, skip_existing=not refetch)
            if limit:
                game_ids = game_ids[:limit]

            if not game_ids:
                console.print("[dim]Every game in range already has play-by-play.[/dim]")
                return

            console.print(
                f"[bold]Collecting play-by-play for {len(game_ids)} games "
                f"across {len(seasons)} seasons...[/bold]"
            )

            if with_shifts:
                async with NHLShiftChartScraper(requests_per_second=rate) as shift_scraper:
                    report = await backfill_play_by_play(
                        db, game_ids, scraper.scrape_play_by_play, shift_scraper.scrape_shifts
                    )
            else:
                report = await backfill_play_by_play(db, game_ids, scraper.scrape_play_by_play)

        console.print(
            f"  [blue]{report.events_written} events from {report.games_collected} games[/blue]"
        )
        if report.shifts_written:
            console.print(f"  [blue]{report.shifts_written} shifts[/blue]")
        if report.games_empty:
            console.print(f"  [yellow]{report.games_empty} games returned no events[/yellow]")
        if report.games_failed:
            console.print(f"  [yellow]{report.games_failed} games failed[/yellow]")

    asyncio.run(run())


def _validate_after_update(db: Database) -> list[str]:
    """Run the integrity checks and corpus assertion at the end of an update.

    Returned as errors rather than raised, so a nightly run still reports what it
    did collect while exiting non-zero for cron to notice.
    """
    console.print("[bold]Validating stored data...[/bold]")
    problems = []

    for result in run_integrity_checks(db):
        if not result.passed:
            problems.append(f"integrity/{result.name}: {result.detail}")

    seasons = seasons_requiring_pbp(db)
    if seasons:
        try:
            assert_pbp_corpus(db, seasons)
        except CorpusError as exc:
            problems.append(f"pbp_corpus: {exc}")

    if problems:
        for problem in problems:
            console.print(f"  [yellow]⚠ {problem}[/yellow]")
    else:
        console.print("  [blue]✓ all integrity checks passed[/blue]")

    return problems


def _print_summary(errors: list[str]) -> None:
    """Print update summary and exit with appropriate code."""
    import sys

    if errors:
        console.print(f"\n[yellow]⚠ Completed with {len(errors)} error(s):[/yellow]")
        for err in errors:
            console.print(f"  [yellow]• {err}[/yellow]")
        sys.exit(1)
    else:
        console.print("\n[bold green]✓ All updates complete![/bold green]")


# ── Yahoo Fantasy Commands ─────────────────────────────────────────


@main.group()
@click.option(
    "--league-id",
    "-l",
    envvar="YAHOO_LEAGUE_ID",
    required=True,
    help="Yahoo Fantasy league ID (or set YAHOO_LEAGUE_ID env var)",
)
@click.pass_context
def fantasy(ctx: click.Context, league_id: str) -> None:
    """Yahoo Fantasy hockey commands for managing your team."""
    ctx.obj["yahoo"] = YahooFantasyClient(league_id=league_id)


@fantasy.command()
@click.pass_context
def league_info(ctx: click.Context) -> None:
    """Show league info and settings."""
    yahoo: YahooFantasyClient = ctx.obj["yahoo"]
    info = yahoo.get_league_info()
    settings = yahoo.get_league_settings()

    console.print(f"\n[bold]{info.get('name', 'Unknown League')}[/bold]")
    console.print(f"[dim]League ID: {yahoo.league_id}[/dim]\n")

    if isinstance(settings, dict):
        table = Table(title="League Settings", show_header=False)
        table.add_column("Setting", style="cyan")
        table.add_column("Value")
        for k, v in settings.items():
            if not isinstance(v, (dict, list)):
                table.add_row(str(k), str(v))
        console.print(table)


@fantasy.command(name="standings")
@click.pass_context
def fantasy_standings(ctx: click.Context) -> None:
    """Show fantasy league standings."""
    yahoo: YahooFantasyClient = ctx.obj["yahoo"]
    standings = yahoo.get_league_standings()

    console.print("\n[bold]League Standings[/bold]\n")
    console.print(standings)


@fantasy.command()
@click.option("--team-id", "-t", type=str, help="Team ID (defaults to your team)")
@click.option("--week", "-w", type=int, help="Week number")
@click.pass_context
def roster(ctx: click.Context, team_id: str | None, week: int | None) -> None:
    """Show team roster with player stats."""
    yahoo: YahooFantasyClient = ctx.obj["yahoo"]
    roster_data = yahoo.get_team_roster(team_id=team_id, week=week)

    console.print("\n[bold]Team Roster[/bold]\n")

    if isinstance(roster_data, list):
        table = Table(title="Roster")
        table.add_column("Player", style="cyan")
        table.add_column("Pos", style="green")
        table.add_column("NHL Team", style="dim")
        table.add_column("Status", style="yellow")

        for player in roster_data:
            if isinstance(player, dict):
                name = player.get("name", player.get("full", "Unknown"))
                if isinstance(name, dict):
                    name = name.get("full", "Unknown")
                table.add_row(
                    str(name),
                    str(player.get("display_position", player.get("position_type", ""))),
                    str(player.get("editorial_team_abbr", "")),
                    str(player.get("status", "")),
                )

        console.print(table)
    else:
        console.print(roster_data)


@fantasy.command()
@click.option("--week", "-w", type=int, help="Week number (current if omitted)")
@click.pass_context
def matchup(ctx: click.Context, week: int | None) -> None:
    """Show current matchup details and score."""
    yahoo: YahooFantasyClient = ctx.obj["yahoo"]
    scoreboard = yahoo.get_league_scoreboard(week=week)

    console.print("\n[bold]Matchups[/bold]\n")
    console.print(scoreboard)


@fantasy.command()
@click.pass_context
def teams(ctx: click.Context) -> None:
    """List all teams in the league."""
    yahoo: YahooFantasyClient = ctx.obj["yahoo"]
    teams_data = yahoo.get_my_team()

    console.print("\n[bold]League Teams[/bold]\n")
    console.print(teams_data)


@fantasy.command()
@click.option("--count", "-n", type=int, default=25, help="Number of players to show")
@click.pass_context
def free_agents(ctx: click.Context, count: int) -> None:
    """Show available free agents on waiver wire."""
    yahoo: YahooFantasyClient = ctx.obj["yahoo"]
    players = yahoo.get_league_players(status="FA", count=count)

    console.print("\n[bold]Free Agents[/bold]\n")

    if isinstance(players, list):
        table = Table(title=f"Top {count} Available Players")
        table.add_column("Player", style="cyan")
        table.add_column("Pos", style="green")
        table.add_column("NHL Team", style="dim")
        table.add_column("% Owned", justify="right")

        for player in players:
            if isinstance(player, dict):
                name = player.get("name", player.get("full", "Unknown"))
                if isinstance(name, dict):
                    name = name.get("full", "Unknown")
                table.add_row(
                    str(name),
                    str(player.get("display_position", "")),
                    str(player.get("editorial_team_abbr", "")),
                    str(player.get("percent_owned", {}).get("value", "")),
                )

        console.print(table)
    else:
        console.print(players)


@fantasy.command()
@click.pass_context
def transactions(ctx: click.Context) -> None:
    """Show recent league transactions."""
    yahoo: YahooFantasyClient = ctx.obj["yahoo"]
    txns = yahoo.get_transactions()

    console.print("\n[bold]Recent Transactions[/bold]\n")
    console.print(txns)


if __name__ == "__main__":
    main()
