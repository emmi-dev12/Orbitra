"""ORBITRA CORE — Rich-based TUI interface."""

import asyncio
import logging
import sys
import threading
from typing import Callable

import readchar
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
from rich.prompt import Prompt, Confirm
from rich.text import Text
from rich.layout import Layout
from rich.live import Live
from rich.columns import Columns
from rich.rule import Rule
from rich import box

from config import PROFILES, Mode, Profile
from core.scorer import expand_queries
import prefs as _prefs

console = Console()


class _TUILogHandler(logging.Handler):
    """During Live sessions, captures log records into an events list instead of stdout."""
    def __init__(self):
        super().__init__()
        self._events: list[str] | None = None

    def attach(self, events: list[str]):
        self._events = events

    def detach(self):
        self._events = None

    def emit(self, record: logging.LogRecord):
        if self._events is not None:
            self._events.append(f"[dim]ℹ {record.getMessage()[:100]}[/dim]")


_tui_handler = _TUILogHandler()
logging.getLogger("orbitra").addHandler(_tui_handler)

BANNER = r"""
[bold purple]
   ██████╗ ██████╗ ██████╗ ██╗████████╗██████╗  █████╗
  ██╔═══██╗██╔══██╗██╔══██╗██║╚══██╔══╝██╔══██╗██╔══██╗
  ██║   ██║██████╔╝██████╔╝██║   ██║   ██████╔╝███████║
  ██║   ██║██╔══██╗██╔══██╗██║   ██║   ██╔══██╗██╔══██║
  ╚██████╔╝██║  ██║██████╔╝██║   ██║   ██║  ██║██║  ██║
   ╚═════╝ ╚═╝  ╚═╝╚═════╝ ╚═╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝
[/bold purple]
[dim]  CORE ENGINE v1.0 — Deterministic Web Intelligence[/dim]
[dim]  No AI. No APIs. Pure algorithms.[/dim]
"""


def print_banner():
    console.print(BANNER)


def main_menu() -> str:
    saved_langs = _prefs.get("expansion_langs") or []
    lang_hint = f"[dim]langs: {', '.join(saved_langs) if saved_langs else 'auto'}[/dim]"
    console.print(Panel(
        f"[1] Run crawl job\n"
        f"[2] Analyze website\n"
        f"[3] View job history\n"
        f"[4] Launch dashboard\n"
        f"[5] Language settings  {lang_hint}\n"
        f"[6] Exit",
        title="[bold cyan]ORBITRA CORE[/bold cyan]",
        border_style="purple",
        padding=(1, 4),
    ))
    return Prompt.ask("[bold]Select option[/bold]", choices=["1","2","3","4","5","6"])


def select_mode() -> Mode:
    console.print("\n[bold]Crawl Mode:[/bold]")
    console.print("  [cyan]1[/cyan] Personal   — analyze specific URLs you provide")
    console.print("  [cyan]2[/cyan] Research   — discover & map a topic landscape")
    console.print("  [cyan]3[/cyan] Lead Gen   — find business contacts & emails\n")
    choice = Prompt.ask("Select mode", choices=["1","2","3"])
    return {"1":"personal","2":"research","3":"leadgen"}[choice]


def select_profile() -> Profile:
    console.print("\n[bold]Concurrency Profile:[/bold]")
    for name, p in PROFILES.items():
        console.print(f"  [cyan]{list(PROFILES).index(name)+1}[/cyan] {name.capitalize():8} — {p.max_pages} pages, {p.max_browsers} browsers")
    console.print()
    choice = Prompt.ask("Select profile", choices=["1","2","3"])
    return list(PROFILES.keys())[int(choice)-1]


def get_query(mode: Mode) -> str:
    hints = {
        "personal": "Enter URL(s) or search query",
        "research": "Enter research topic (e.g. 'sports camps Southeast Asia')",
        "leadgen": "Enter niche/industry to find leads (e.g. 'football academy Thailand')",
    }
    console.print()
    return Prompt.ask(f"[bold]{hints[mode]}[/bold]")


def get_seed_urls() -> list[str]:
    console.print("\n[dim]Enter seed URLs (one per line, empty line to finish):[/dim]")
    seeds = []
    while True:
        url = Prompt.ask("  URL", default="")
        if not url:
            break
        seeds.append(url.strip())
    return seeds


def review_queries(queries: list[str]) -> list[str]:
    """Show generated queries, allow editing before crawl starts."""
    console.print("\n[bold]Generated Search Queries:[/bold]\n")
    for i, q in enumerate(queries, 1):
        console.print(f"  [cyan]{i:2}[/cyan]  {q}")

    console.print()
    action = Prompt.ask(
        "Review queries",
        choices=["run","edit","add","remove"],
        default="run",
        show_choices=True,
    )

    if action == "edit":
        idx = int(Prompt.ask("Query number to edit")) - 1
        if 0 <= idx < len(queries):
            queries[idx] = Prompt.ask("New query", default=queries[idx])

    elif action == "add":
        new_q = Prompt.ask("New query to add")
        queries.append(new_q)

    elif action == "remove":
        raw = Prompt.ask("Query number(s) to remove (e.g. 9 or 9,10,11)")
        indices = []
        for part in raw.replace(" ", "").split(","):
            try:
                indices.append(int(part) - 1)
            except ValueError:
                pass
        for idx in sorted(set(indices), reverse=True):
            if 0 <= idx < len(queries):
                console.print(f"[dim]Removed: {queries.pop(idx)}[/dim]")

    if action != "run":
        # Show updated list and recurse for another round
        return review_queries(queries)

    return queries


def language_chooser() -> list[str]:
    """Interactively pick expansion languages. Persists choice to ~/.orbitra/prefs.json."""
    from lang_expansions import LANGUAGES
    saved = _prefs.get("expansion_langs") or []

    console.print()
    console.print(Panel(
        "[bold]Query Expansion Languages[/bold]\n\n"
        "ORBITRA can expand your queries into multiple languages to find more results.\n"
        "[dim]Leave blank to auto-detect from query region.[/dim]\n\n"
        "[bold]Available codes:[/bold]\n" +
        "  ".join(f"[cyan]{code}[/cyan]={info['native']}"
                  for code, info in LANGUAGES.items()),
        title="[bold purple]Language Settings[/bold purple]",
        border_style="purple",
        padding=(1, 2),
    ))
    if saved:
        console.print(f"\n[dim]Current setting: [cyan]{', '.join(saved)}[/cyan]  (Enter to keep)[/dim]")

    raw = Prompt.ask(
        "\n[bold]Enter language codes separated by commas[/bold] (or 'auto' / Enter to auto-detect)",
        default="auto" if not saved else ",".join(saved),
    ).strip().lower()

    if raw in ("", "auto"):
        result: list[str] = []
    else:
        valid = set(LANGUAGES.keys())
        result = [c.strip() for c in raw.split(",") if c.strip() in valid]
        unknown = [c.strip() for c in raw.split(",") if c.strip() and c.strip() not in valid]
        if unknown:
            console.print(f"[yellow]Unknown codes ignored: {', '.join(unknown)}[/yellow]")

    _prefs.set_key("expansion_langs", result)
    label = ", ".join(result) if result else "auto-detect"
    console.print(f"[dim]Saved: [cyan]{label}[/cyan][/dim]")
    return result


def get_accuracy_goal() -> int:
    """Ask user for target accuracy % (0–100). Affects lead threshold and scoring."""
    console.print()
    console.print("[bold]Accuracy Goal:[/bold]")
    console.print("  Controls lead quality threshold and scoring strictness.")
    console.print("  [dim]0   = broad/fast — everything with a contact counts as a lead[/dim]")
    console.print("  [dim]50  = balanced (recommended)[/dim]")
    console.print("  [dim]100 = strict — only high-confidence, high-content pages qualify[/dim]")
    console.print()
    while True:
        raw = Prompt.ask("[bold]Accuracy goal (0–100)[/bold]", default="50")
        try:
            val = int(raw.strip().rstrip("%"))
            if 0 <= val <= 100:
                return val
        except ValueError:
            pass
        console.print("[red]Enter a number between 0 and 100.[/red]")


def confirm_launch(query: str, mode: Mode, profile: Profile,
                   queries: list[str], seeds: list[str],
                   accuracy_goal: int = 50) -> bool:
    p = PROFILES[profile]
    lead_thresh = int(accuracy_goal * 0.35)
    console.print()
    console.print(Panel(
        f"[bold]Query:[/bold]    {query}\n"
        f"[bold]Mode:[/bold]     {mode}\n"
        f"[bold]Profile:[/bold]  {profile} ({p.max_pages} pages, {p.max_browsers} browsers)\n"
        f"[bold]Accuracy:[/bold] {accuracy_goal}%  [dim](lead min score: {lead_thresh})[/dim]\n"
        f"[bold]Queries:[/bold]  {len(queries)} expanded\n"
        f"[bold]Seeds:[/bold]    {len(seeds)} provided",
        title="[bold yellow]Launch Configuration[/bold yellow]",
        border_style="yellow",
    ))
    return Confirm.ask("\n[bold]Launch crawl job?[/bold]", default=True)


def _render_compact(job_id: str, query: str, mode: str, profile: str,
                    status: str, stats: dict, events: list[str]) -> Panel:
    status_color = {"RUNNING":"yellow","DONE":"green","FAILED":"red","CANCELLED":"dim"}.get(status,"white")
    feed = "\n".join(events[-12:]) or "[dim]Initializing...[/dim]"
    content = (
        f"[bold]Job:[/bold] [cyan]{job_id}[/cyan]  "
        f"[bold]Query:[/bold] {query[:55]}  "
        f"[bold]Mode:[/bold] {mode}  [bold]Profile:[/bold] {profile}\n\n"
        f"  [{status_color}]{status}[/{status_color}]  "
        f"Crawled: [green]{stats.get('crawled',0)}[/green]  "
        f"Failed: [red]{stats.get('failed',0)}[/red]  "
        f"Leads: [cyan]{stats.get('leads',0)}[/cyan]  "
        f"Queued: [dim]{stats.get('queued',0)}[/dim]\n\n"
        f"[bold dim]Live feed:[/bold dim]\n{feed}\n\n"
        f"[dim]Press [bold]E[/bold] to expand · [bold]Q[/bold] to cancel[/dim]"
    )
    return Panel(content, title="[bold purple]◈ ORBITRA CORE[/bold purple]", border_style="purple")


def _render_expanded(job_id: str, query: str, mode: str, profile: str,
                     status: str, stats: dict, events: list[str],
                     entities_seen: dict, top_pages: list[dict]) -> Panel:
    status_color = {"RUNNING":"yellow","DONE":"green","FAILED":"red","CANCELLED":"dim"}.get(status,"white")

    # Left column — stats + top pages
    crawled = stats.get('crawled', 0)
    failed  = stats.get('failed', 0)
    leads   = stats.get('leads', 0)
    queued  = stats.get('queued', 0)

    left = (
        f"[bold purple]◈ JOB[/bold purple] [cyan]{job_id}[/cyan]\n"
        f"[dim]Query:[/dim] {query[:50]}\n"
        f"[dim]Mode:[/dim]  {mode}   [dim]Profile:[/dim] {profile}\n\n"
        f"[{status_color}]● {status}[/{status_color}]\n\n"
        f"[bold]Stats[/bold]\n"
        f"  Crawled  [green]{crawled:>6}[/green]\n"
        f"  Failed   [red]{failed:>6}[/red]\n"
        f"  Leads    [cyan]{leads:>6}[/cyan]\n"
        f"  Queued   [dim]{queued:>6}[/dim]\n\n"
    )

    if top_pages:
        left += "[bold]Top Pages[/bold]\n"
        for p in top_pages[:8]:
            score = p.get('score', 0)
            url = p.get('url', '')[:45]
            sc = "green" if score >= 60 else "yellow" if score >= 30 else "red"
            left += f"  [{sc}]{score:3d}[/{sc}] {url}\n"

    if entities_seen.get("emails"):
        left += f"\n[bold]Emails Found[/bold]\n"
        for e in list(entities_seen["emails"])[:6]:
            left += f"  [green]{e}[/green]\n"

    if entities_seen.get("wechat"):
        left += f"\n[bold]WeChat IDs[/bold]\n"
        for w in list(entities_seen["wechat"])[:6]:
            left += f"  [purple]{w}[/purple]\n"

    # Right column — full live feed
    feed = "\n".join(events[-40:]) or "[dim]Initializing...[/dim]"
    right = f"[bold]Live Feed[/bold]\n\n{feed}"

    # Side-by-side using rule separator
    cols = Columns([
        Panel(left, border_style="dim", width=52),
        Panel(right, border_style="dim"),
    ], expand=True)

    return Panel(
        cols,
        title="[bold purple]◈ ORBITRA CORE — EXPANDED VIEW[/bold purple]  [dim](E to collapse · Q to cancel)[/dim]",
        border_style="purple",
    )


async def run_job_tui(job_id: str, engine, query: str, mode: Mode, profile: str):
    """Async live TUI. Press E to toggle expanded view, Q to cancel.

    Flicker fix: all log output is captured into the events list via _TUILogHandler.
    The Live display uses auto_refresh=False and refreshes only after state changes,
    preventing console write conflicts that cause visible flicker.
    """
    events: list[str] = []
    job_status = "RUNNING"
    expanded = False
    dirty = True  # True when we need a redraw
    entities_seen: dict[str, set] = {"emails": set(), "phones": set(), "wechat": set()}
    top_pages: list[dict] = []

    # Capture all log output into events during live session
    _tui_handler.attach(events)

    def on_progress(event):
        nonlocal job_status, dirty
        dirty = True
        msg = event.get("event", "")
        if msg == "page_done":
            sc = event.get("score", 0)
            url = event.get("url", "")[:80]
            events.append(f"[green]✓[/green] [{sc:3d}] {url}")
            top_pages.append({"url": url, "score": sc})
            top_pages.sort(key=lambda x: x["score"], reverse=True)
            for ent in event.get("emails", []):
                entities_seen["emails"].add(ent)
            for ent in event.get("wechat", []):
                entities_seen["wechat"].add(ent)
        elif msg == "seeds_found":
            events.append(f"[cyan]⬡[/cyan] Found {event.get('count', 0)} seed URLs")
        elif msg == "discovering":
            events.append("[cyan]⬡[/cyan] Discovering — DDG + Yahoo + Brave + CommonCrawl...")
        elif msg == "started":
            events.append(f"[cyan]▶[/cyan] Job started — {len(event.get('queries', []))} queries")
        elif msg == "log":
            events.append(f"[dim]ℹ[/dim] {event.get('msg','')}")
        elif msg == "progress":
            s = event.get("stats", {})
            events.append(
                f"[dim]↻[/dim] crawled={s.get('crawled',0)} "
                f"failed={s.get('failed',0)} leads={s.get('leads',0)}"
            )
        elif msg == "outputs_written":
            events.append(f"[cyan]↓[/cyan] Outputs written → {event.get('path','')}")
        elif msg == "done":
            events.append("[bold cyan]✦ Job complete[/bold cyan]")
            job_status = "DONE"
        elif msg == "failed":
            events.append(f"[red]✗ Failed: {event.get('error', '')}[/red]")
            job_status = "FAILED"
        elif msg == "cancelled":
            job_status = "CANCELLED"

    engine.on_progress(on_progress)

    # Non-blocking key reader thread
    key_queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_event_loop()

    def _key_reader():
        while job_status == "RUNNING":
            try:
                k = readchar.readkey().lower()
                loop.call_soon_threadsafe(key_queue.put_nowait, k)
            except Exception:
                break

    key_thread = threading.Thread(target=_key_reader, daemon=True)
    key_thread.start()

    # auto_refresh=False: we control when redraws happen, eliminating flicker
    # from_renderables=True keeps the panel at the bottom of existing output
    with Live(console=console, auto_refresh=False, transient=False,
              vertical_overflow="crop") as live:
        while True:
            # Drain key queue
            while not key_queue.empty():
                key = key_queue.get_nowait()
                dirty = True
                if key == "e":
                    expanded = not expanded
                elif key == "q" and job_status == "RUNNING":
                    engine.cancel_job(job_id)
                    events.append("[yellow]⚠ Cancellation requested...[/yellow]")

            stats = engine.get_stats(job_id) or {}

            if job_status == "RUNNING":
                from db.database import get_job as _gj
                db_job = _gj(job_id)
                if db_job and db_job["status"] in ("DONE", "FAILED", "CANCELLED"):
                    job_status = db_job["status"]
                    dirty = True

            # Only redraw when something changed
            if dirty:
                if expanded:
                    live.update(_render_expanded(
                        job_id, query, mode, profile, job_status,
                        stats, events, entities_seen, top_pages[:8]
                    ))
                else:
                    live.update(_render_compact(
                        job_id, query, mode, profile, job_status, stats, events
                    ))
                live.refresh()
                dirty = False

            if job_status in ("DONE", "FAILED", "CANCELLED"):
                break

            await asyncio.sleep(0.25)

    _tui_handler.detach()
    console.print()
    if job_status == "DONE":
        console.print(f"[bold green]✦ Job complete![/bold green] Results → [cyan]results/jobs/{job_id}/[/cyan]")
        console.print(f"  [dim]results.json  leads.csv  graph.json  raw_pages.json[/dim]")
    elif job_status == "FAILED":
        console.print("[bold red]✗ Job failed.[/bold red]")
    elif job_status == "CANCELLED":
        console.print("[yellow]⚠ Job cancelled.[/yellow]")


def show_job_history():
    from db.database import list_jobs, get_pages
    jobs = list_jobs()
    if not jobs:
        console.print("[dim]No jobs found.[/dim]")
        return

    table = Table(title="Job History", box=box.ROUNDED, border_style="purple",
                  show_lines=False, padding=(0,1))
    table.add_column("ID", style="cyan", width=10)
    table.add_column("Query", width=30)
    table.add_column("Mode", width=10)
    table.add_column("Profile", width=8)
    table.add_column("Status", width=10)
    table.add_column("Pages", justify="right", width=6)
    table.add_column("Created", width=18)

    for j in jobs:
        status_style = {
            "DONE":"green","RUNNING":"yellow","FAILED":"red",
            "CANCELLED":"dim","PENDING":"blue"
        }.get(j["status"],"white")

        created = ""
        if j.get("created_at"):
            import datetime
            created = datetime.datetime.fromtimestamp(j["created_at"]).strftime("%Y-%m-%d %H:%M")

        table.add_row(
            j["id"],
            j["query"][:28],
            j["mode"],
            j["profile"],
            f"[{status_style}]{j['status']}[/{status_style}]",
            str(j.get("page_count",0)),
            created,
        )

    console.print(table)

    detail = Prompt.ask("\nEnter job ID to view details (or Enter to skip)", default="")
    if detail:
        _show_job_detail(detail)


def _show_job_detail(job_id: str):
    from db.database import get_job, get_pages
    job = get_job(job_id)
    if not job:
        console.print(f"[red]Job {job_id} not found[/red]")
        return

    pages = get_pages(job_id, min_score=0, limit=20)

    table = Table(title=f"Top Pages — Job {job_id}", box=box.SIMPLE,
                  border_style="cyan", padding=(0,1))
    table.add_column("Score", width=6, justify="right")
    table.add_column("URL", width=60)
    table.add_column("Contacts", width=10)
    table.add_column("Lang", width=6)

    for p in pages[:20]:
        e = p.get("entities",{})
        c = p.get("content",{})
        has_contacts = bool(e.get("emails") or e.get("phones") or e.get("wechat"))
        score_style = "green" if p["score"] >= 60 else "yellow" if p["score"] >= 30 else "red"
        table.add_row(
            f"[{score_style}]{p['score']}[/{score_style}]",
            p["url"][:58],
            "[green]✓[/green]" if has_contacts else "",
            c.get("language","")[:5],
        )

    console.print(table)


def analyze_website_tui():
    """Single URL website analysis mode."""
    url = Prompt.ask("\n[bold]Enter URL to analyze[/bold]")
    console.print(f"\n[dim]Analyzing {url}...[/dim]\n")
    return url
