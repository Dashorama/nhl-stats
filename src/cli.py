"""Command-line interface for NHL scraper."""

import asyncio
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from .scrapers import NHLAPIScraper
from .storage import Database
from .utils import setup_logging

console = Console()


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging")
@click.option("--json-logs", is_flag=True, help="Output logs as JSON")
@click.pass_context
def main(ctx: click.Context, verbose: bool, json_logs: bool) -> None:
    """NHL Analytics Scraper - Collect hockey data from multiple sources."""
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


if __name__ == "__main__":
    main()
