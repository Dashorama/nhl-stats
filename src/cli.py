"""Command-line interface for NHL scraper."""

import asyncio
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from .scrapers import NHLAPIScraper, NHLRosterScraper, MoneyPuckScraper, PuckPediaScraper
from .storage import Database, GameRecord, PlayerRecord, BoxscoreRecord, PlayByPlayRecord
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

    async def run():
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

    async def run():
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

    async def run():
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

    async def run():
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

    async def run():
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

    async def run():
        async with NHLRosterScraper() as scraper:
            if team:
                console.print(f"[bold]Scraping roster for {team}...[/bold]")
                roster = await scraper.scrape_roster(team, season)
                db.upsert_rosters([roster])
                total = len(roster.get("forwards", [])) + len(roster.get("defensemen", [])) + len(roster.get("goalies", []))
                console.print(f"[green]✓ Scraped {total} players for {team}[/green]")
            else:
                console.print("[bold]Scraping all team rosters...[/bold]")
                rosters = await scraper.scrape_all_rosters(season)
                db.upsert_rosters(rosters)
                total = sum(
                    len(r.get("forwards", [])) + len(r.get("defensemen", [])) + len(r.get("goalies", []))
                    for r in rosters
                )
                console.print(f"[green]✓ Scraped {total} players across {len(rosters)} teams[/green]")

    asyncio.run(run())


@main.command()
@click.option("--season", "-s", help="Season year (e.g., 2024)")
@click.pass_context
def scrape_advanced(ctx: click.Context, season: str | None) -> None:
    """Scrape advanced stats from MoneyPuck."""
    db: Database = ctx.obj["db"]

    async def run():
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

    async def run():
        async with PuckPediaScraper() as scraper:
            if team:
                console.print(f"[bold]Scraping contracts for {team}...[/bold]")
                contracts = await scraper.scrape_team_contracts(team)
                db.upsert_contracts(contracts)
                console.print(f"[green]✓ Scraped {len(contracts)} contracts[/green]")
            else:
                console.print("[bold]Scraping all team contracts...[/bold]")
                console.print("[dim](This may take a while to be respectful to PuckPedia's servers)[/dim]")
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

    async def run():
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

    async def run():
        # Get completed regular season game IDs from DB
        with db.get_session() as session:
            query = session.query(GameRecord.id).filter(
                GameRecord.game_type == "2",
                GameRecord.game_state.in_(["OFF", "FINAL"])
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

    async def run():
        with db.get_session() as session:
            query = session.query(GameRecord.id).filter(
                GameRecord.game_type == "2",
                GameRecord.game_state.in_(["OFF", "FINAL"])
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
                        console.print(f"  [dim]Progress: {i + 1}/{len(game_ids)} ({total_events} events)[/dim]")
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

    async def run():
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
                len(r.get("forwards", [])) + len(r.get("defensemen", [])) + len(r.get("goalies", []))
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

    async def run():
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

    async def run():
        async with NHLRosterScraper() as scraper:
            player = await scraper.scrape_player_details(player_id)

            console.print(f"\n[bold]{player['first_name']} {player['last_name']}[/bold]")
            console.print(f"[dim]#{player.get('jersey_number', 'N/A')} • {player.get('position', 'N/A')} • {player.get('team_abbrev', 'N/A')}[/dim]\n")

            info_table = Table(show_header=False, box=None)
            info_table.add_column("Field", style="cyan")
            info_table.add_column("Value")

            info_table.add_row("Birth Date", player.get("birth_date", "N/A"))
            info_table.add_row("Birthplace", f"{player.get('birth_city', '')}, {player.get('birth_country', '')}")
            info_table.add_row("Height", f"{player.get('height_inches', 0) // 12}'{player.get('height_inches', 0) % 12}\"" if player.get("height_inches") else "N/A")
            info_table.add_row("Weight", f"{player.get('weight_pounds', 'N/A')} lbs")
            info_table.add_row("Shoots/Catches", player.get("shoots_catches", "N/A"))

            if player.get("draft_year"):
                info_table.add_row(
                    "Draft",
                    f"{player['draft_year']} R{player.get('draft_round', '?')}, Pick {player.get('draft_pick', '?')} (#{player.get('draft_overall', '?')} overall) by {player.get('draft_team', 'N/A')}"
                )

            console.print(info_table)

            # Career stats summary if available
            career = player.get("career_stats", {})
            if career:
                console.print("\n[bold]Career Stats[/bold]")
                reg = career.get("regularSeason", {})
                if reg:
                    console.print(f"  GP: {reg.get('gamesPlayed', 0)} | G: {reg.get('goals', 0)} | A: {reg.get('assists', 0)} | P: {reg.get('points', 0)}")

    asyncio.run(run())


@main.command()
@click.option("--season", "-s", help="Season (e.g., 20252026)")
@click.option("--limit", "-l", type=int, help="Max players to scrape")
@click.pass_context
def scrape_game_logs(ctx: click.Context, season: str | None, limit: int | None) -> None:
    """Scrape player game logs from NHL API."""
    db: Database = ctx.obj["db"]

    async def run():
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

        console.print(f"[green]✓ Scraped {total_logs} game log entries for {scraped} players[/green]")

    asyncio.run(run())


@main.command()
@click.option("--season", "-s", help="Season start year (e.g., 2025)")
@click.pass_context
def scrape_shots(ctx: click.Context, season: str | None) -> None:
    """Scrape shot-level data from MoneyPuck."""
    db: Database = ctx.obj["db"]

    async def run():
        async with MoneyPuckScraper() as scraper:
            console.print("[bold]Downloading MoneyPuck shot data...[/bold]")
            console.print("[dim](This is a large CSV download)[/dim]")
            shots = await scraper.scrape_shot_data(season)
            console.print(f"  Downloaded {len(shots)} shots, saving to database...")
            db.insert_shots(shots)
            console.print(f"[green]✓ Saved {len(shots)} shots[/green]")

    asyncio.run(run())


@main.command()
@click.option("--daily", is_flag=True, help="Only update daily data (games, boxscores, PBP, game logs)")
@click.pass_context
def update(ctx: click.Context, daily: bool) -> None:
    """Update all data from all sources.

    Default: full update (all sources).
    --daily: only games, boxscores, play-by-play, and game logs.

    Designed to be called by cron. See OPERATIONS.md for details.
    """
    db: Database = ctx.obj["db"]

    async def run():
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
                        r[0] for r in session.query(GameRecord.id).filter(
                            GameRecord.game_type == "2",
                            GameRecord.game_state.in_(["OFF", "FINAL"])
                        ).all()
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

            # Play-by-play for new games
            console.print("[bold]Updating play-by-play...[/bold]")
            try:
                with db.get_session() as session:
                    already_pbp = set(
                        r[0] for r in session.query(PlayByPlayRecord.game_id).distinct().all()
                    )
                    new_pbp_ids = sorted(all_finished - already_pbp)

                if new_pbp_ids:
                    scraped = 0
                    total_events = 0
                    for gid in new_pbp_ids:
                        try:
                            events = await scraper.scrape_play_by_play(gid)
                            db.insert_play_by_play(gid, events)
                            scraped += 1
                            total_events += len(events)
                        except Exception:
                            pass
                    console.print(f"  [green]✓ {total_events} events from {scraped} games[/green]")
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
                    len(r.get("forwards", [])) + len(r.get("defensemen", [])) + len(r.get("goalies", []))
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

        _print_summary(errors)

    asyncio.run(run())


@main.command()
@click.pass_context
def injuries(ctx: click.Context) -> None:
    """Update player injury/availability status."""
    import asyncio as _asyncio
    from .scrapers.nhl_injuries import NHLInjuriesScraper
    db: Database = ctx.obj["db"]
    errors = []
    try:
        scraper = NHLInjuriesScraper()
        result = _asyncio.run(scraper.scrape_all(db))
        click.echo(f"  ✓ {result['players']} players")
        if result["errors"]:
            errors.append(f"teams failed: {result['errors']}")
    except Exception as e:
        errors.append(f"injuries: {e}")
    _print_summary(errors)


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


if __name__ == "__main__":
    main()
