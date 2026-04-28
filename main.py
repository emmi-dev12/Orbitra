"""ORBITRA CORE — entry point."""

import asyncio
import argparse
import logging
import sys
import os

# Ensure orbitra root is on path
sys.path.insert(0, os.path.dirname(__file__))

from db.database import init_db
from core.engine import Engine
from core.scorer import expand_queries
from ui.tui import (
    print_banner, main_menu, select_mode, select_profile,
    get_query, get_seed_urls, review_queries, confirm_launch,
    get_accuracy_goal, language_chooser, run_job_tui,
    show_job_history, analyze_website_tui,
)
import prefs as _prefs
from rich.console import Console

console = Console()
log = logging.getLogger("orbitra")


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    # Silence noisy libs
    logging.getLogger("playwright").setLevel(logging.ERROR)
    logging.getLogger("httpx").setLevel(logging.ERROR)
    logging.getLogger("httpcore").setLevel(logging.ERROR)


async def run_crawl_job(engine: Engine):
    mode = select_mode()
    profile = select_profile()
    query = get_query(mode)

    seeds = []
    if mode == "personal":
        seeds = get_seed_urls()

    # Generate and review expanded queries using saved language prefs
    forced_langs = _prefs.get("expansion_langs") or None
    raw_expanded = expand_queries(query, mode, forced_langs=forced_langs)
    confirmed_queries = review_queries(raw_expanded)

    accuracy_goal = get_accuracy_goal()

    if not confirm_launch(query, mode, profile, confirmed_queries, seeds, accuracy_goal):
        console.print("[dim]Cancelled.[/dim]")
        return

    job_id = engine.create_job(
        query=query,
        mode=mode,
        profile=profile,
        seed_urls=seeds,
        expanded_queries=confirmed_queries,
        accuracy_goal=accuracy_goal,
    )

    # Run job + TUI concurrently — both are async, event loop serves both
    job_task = asyncio.create_task(engine.run_job(job_id))
    await run_job_tui(job_id, engine, query, mode, profile)
    await job_task


async def run_analyze(engine: Engine):
    url = analyze_website_tui()
    result = await engine.analyze_website(url)

    if result.get("error"):
        console.print(f"[red]Error: {result['error']}[/red]")
        return

    w = result.get("website_intel", {})
    p = result.get("page_extract", {})

    from rich.table import Table
    from rich import box

    table = Table(box=box.ROUNDED, border_style="cyan", padding=(0,2))
    table.add_column("[dim]Field[/dim]", width=18)
    table.add_column("Value")

    table.add_row("Title", w.get("title","—"))
    table.add_row("Description", (w.get("description","—"))[:80])
    table.add_row("Logo", w.get("logo_url","—") or "—")
    table.add_row("Language", p.get("language","—"))
    table.add_row("Word Count", str(p.get("word_count",0)))
    table.add_row("CMS", w.get("cms","—") or "—")
    table.add_row("Framework", w.get("framework","—") or "—")
    table.add_row("CDN", w.get("cdn","—") or "—")
    table.add_row("Tech Stack", ", ".join(w.get("tech_hints",[])[:6]) or "—")
    table.add_row("Schema Types", ", ".join(w.get("schema_types",[])[:5]) or "—")
    table.add_row("Colors", "  ".join(w.get("color_palette",[])[:6]) or "—")
    table.add_row("Emails", ", ".join(p.get("entities",{}).get("emails",[])[:5]) or "—")
    table.add_row("Phones", ", ".join(p.get("entities",{}).get("phones",[])[:5]) or "—")
    table.add_row("WeChat", ", ".join(p.get("entities",{}).get("wechat",[])[:5]) or "—")
    table.add_row("Social", ", ".join(w.get("social_links",{}).keys()) or "—")
    table.add_row("Nav Items", str(len(w.get("navigation",[]))))
    table.add_row("Has Schema", "Yes" if w.get("schema_types") else "No")

    console.print(table)


async def launch_dashboard():
    import uvicorn
    from web.server import app

    console.print("\n[bold cyan]Launching ORBITRA dashboard...[/bold cyan]")
    console.print("[dim]Open: http://localhost:7331[/dim]\n")

    config = uvicorn.Config(app, host="127.0.0.1", port=7331, log_level="warning")
    server = uvicorn.Server(config)
    await server.serve()


async def interactive_loop():
    engine = Engine()

    while True:
        try:
            choice = main_menu()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye.[/dim]")
            break

        if choice == "1":
            try:
                await run_crawl_job(engine)
            except KeyboardInterrupt:
                console.print("\n[yellow]Job interrupted.[/yellow]")

        elif choice == "2":
            try:
                await run_analyze(engine)
            except KeyboardInterrupt:
                console.print("\n[yellow]Cancelled.[/yellow]")

        elif choice == "3":
            show_job_history()

        elif choice == "4":
            try:
                await launch_dashboard()
            except KeyboardInterrupt:
                console.print("\n[dim]Dashboard stopped.[/dim]")

        elif choice == "5":
            language_chooser()

        elif choice == "6":
            console.print("[dim]Goodbye.[/dim]")
            break


def main():
    parser = argparse.ArgumentParser(description="ORBITRA CORE — Web Intelligence Engine")
    parser.add_argument("--dashboard", action="store_true", help="Launch dashboard directly")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    parser.add_argument("--port", type=int, default=7331, help="Dashboard port")
    args = parser.parse_args()

    setup_logging(args.verbose)
    init_db()

    print_banner()

    if args.dashboard:
        asyncio.run(launch_dashboard())
    else:
        asyncio.run(interactive_loop())


if __name__ == "__main__":
    main()
