"""ORBITRA CORE — job orchestrator. Wires crawler, extractor, scorer, graph, DB."""

import asyncio
import csv
import json
import logging
import time
import uuid
from pathlib import Path
from typing import AsyncIterator, Callable

from config import PROFILES, RESULTS_DIR, MAX_DEPTH, Profile, Mode
from core.crawler import Crawler
from core.extractor import extract
from core.graph import CrawlGraph
from core.scorer import score_page, expand_queries
from modules.discovery import discover_urls
from modules.website import analyze_website
from db.database import (
    create_job, update_job_status, upsert_page,
    insert_edges, get_pages, save_expansions, get_job
)

log = logging.getLogger("orbitra.engine")


class JobCancelledError(Exception):
    pass


class CrawlJob:
    def __init__(self, job_id: str, query: str, mode: Mode, profile: Profile,
                 seed_urls: list[str] | None = None,
                 expanded_queries: list[str] | None = None,
                 accuracy_goal: int = 50,
                 progress_cb: Callable[[dict], None] | None = None):
        self.job_id = job_id
        self.query = query
        self.mode = mode
        self.profile = profile
        self.seed_urls = seed_urls or []
        self.expanded_queries = expanded_queries or expand_queries(query, mode)
        self.accuracy_goal = max(0, min(100, accuracy_goal))
        # Lead min score: 0%→0, 50%→17, 100%→35
        self.lead_min_score = int(self.accuracy_goal * 0.35)
        # Penalty multiplier: 50%→1.0, 100%→1.5, 0%→0.5
        self.penalty_scale = 0.5 + self.accuracy_goal / 100.0
        self.progress_cb = progress_cb or (lambda x: None)
        self._cancelled = False
        self._task: asyncio.Task | None = None

        self.stats = {
            "crawled": 0, "failed": 0, "skipped": 0,
            "queued": 0, "leads": 0, "start_time": 0,
            "accuracy_goal": self.accuracy_goal,
        }

    def cancel(self):
        self._cancelled = True
        if self._task:
            self._task.cancel()

    def _emit(self, event: str, **kwargs):
        self.progress_cb({"event": event, "job_id": self.job_id,
                          "stats": dict(self.stats), **kwargs})

    async def run(self):
        self.stats["start_time"] = time.time()
        create_job(self.job_id, self.mode, self.query, self.profile)
        update_job_status(self.job_id, "RUNNING")
        save_expansions(self.job_id, self.query, self.expanded_queries)
        self._emit("started", queries=self.expanded_queries)

        try:
            await self._run_crawl()
            await self._write_outputs()
            update_job_status(self.job_id, "DONE")
            self._emit("done")
        except JobCancelledError:
            update_job_status(self.job_id, "CANCELLED")
            self._emit("cancelled")
        except Exception as e:
            log.exception(f"Job {self.job_id} failed: {e}")
            update_job_status(self.job_id, "FAILED", error=str(e))
            self._emit("failed", error=str(e))

    async def _run_crawl(self):
        concurrency = PROFILES[self.profile]
        graph = CrawlGraph()

        # Discovery phase
        self._emit("discovering")
        self._emit("log", msg="Discovery started — querying DDG + Bing + CommonCrawl...")
        try:
            seeds = await discover_urls(
                self.expanded_queries,
                self.mode,
                seed_urls=self.seed_urls
            )
        except Exception as e:
            self._emit("log", msg=f"Discovery error: {e} — continuing with seed_urls only")
            seeds = list(self.seed_urls)

        if self._cancelled:
            raise JobCancelledError()

        if not seeds:
            self._emit("log", msg="ERROR: No seed URLs found. Check network or add manual seed URLs.")
            raise RuntimeError("Discovery returned 0 seeds. Add seed URLs manually or check network.")

        for seed in seeds:
            graph.add_seed(seed, depth=0)
        self.stats["queued"] = len(seeds)
        self._emit("seeds_found", count=len(seeds))
        self._emit("log", msg=f"Found {len(seeds)} seed URLs — starting crawl")

        async with Crawler(concurrency) as crawler:
            batch_num = 0
            while True:
                if self._cancelled:
                    raise JobCancelledError()

                batch = graph.next_urls(batch_size=min(concurrency.max_pages, 20))
                if not batch:
                    self._emit("log", msg=f"Crawl complete — no more URLs in frontier")
                    break

                batch_num += 1
                self._emit("log", msg=f"Batch {batch_num}: crawling {len(batch)} URLs")
                tasks = [self._process_url(crawler, graph, url) for url in batch]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # Log any unexpected exceptions from gather
                for i, r in enumerate(results):
                    if isinstance(r, Exception):
                        log.warning(f"Batch task exception [{batch[i]}]: {r}")

                pruned = graph.prune_low_value()
                if pruned:
                    self._emit("log", msg=f"Pruned {pruned} low-value nodes")

                self._emit("progress")

        self._graph = graph

    async def _process_url(self, crawler: Crawler, graph: CrawlGraph, url: str):
        if self._cancelled:
            return
        if crawler.is_seen(url):
            graph.mark_skipped(url)
            return

        try:
            result = await crawler.fetch(url)
        except Exception as e:
            log.warning(f"Fetch exception {url}: {e}")
            graph.mark_failed(url)
            self.stats["failed"] += 1
            return

        if not result.ok:
            graph.mark_failed(url)
            self.stats["failed"] += 1
            return

        # Extract
        try:
            page = extract(url, result.html)
        except Exception as e:
            log.warning(f"Extract failed {url}: {e}")
            graph.mark_failed(url)
            self.stats["failed"] += 1
            return

        # Discover links before scoring (so inbound counts are more accurate over time)
        links = crawler.extract_links(url, result.html)
        node_depth = graph.nodes[url].depth if url in graph.nodes else 0
        same_domain = self.mode == "personal"  # personal mode = same domain only
        graph.discover_links(url, links, same_domain_only=same_domain)

        # Score (pass penalty_scale so accuracy goal affects scoring strictness)
        inbound = graph.inbound_count.get(url, 0)
        score_result = score_page(page, self.expanded_queries, self.mode, inbound,
                                  penalty_scale=self.penalty_scale)
        graph.update_score(url, score_result.total)

        # Persist
        upsert_page(
            job_id=self.job_id,
            url=url,
            score=score_result.total,
            depth=node_depth,
            content={
                "title": page.title,
                "headings": page.headings,
                "main_text": page.main_text[:5000],
                "word_count": page.word_count,
                "language": page.language,
                "metadata": page.metadata,
                "schema_org": page.schema_org[:3],
            },
            entities=page.entities,
            breakdown=score_result.breakdown,
        )

        # Store edges batch
        edge_batch = [(url, lurl, anchor) for lurl, anchor in links[:50]]
        insert_edges(self.job_id, edge_batch)

        self.stats["crawled"] += 1
        has_contacts = bool(
            page.entities.get("emails") or
            page.entities.get("phones") or
            page.entities.get("wechat")
        )
        if has_contacts:
            self.stats["leads"] += 1

        self._emit("page_done",
                   url=url,
                   score=score_result.total,
                   emails=page.entities.get("emails", []),
                   phones=page.entities.get("phones", []),
                   wechat=page.entities.get("wechat", []),
                   has_contacts=has_contacts)

    async def _write_outputs(self):
        job_dir = Path(RESULTS_DIR) / self.job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        pages = get_pages(self.job_id, min_score=0, limit=10000)

        # results.json — top pages by score
        results = sorted(pages, key=lambda p: p["score"], reverse=True)
        (job_dir / "results.json").write_text(
            json.dumps(results, indent=2, ensure_ascii=False)
        )

        # raw_pages.json — all pages with full content
        (job_dir / "raw_pages.json").write_text(
            json.dumps(pages, indent=2, ensure_ascii=False)
        )

        # graph.json
        graph_data = self._graph.to_export() if hasattr(self, "_graph") else {}
        (job_dir / "graph.json").write_text(
            json.dumps(graph_data, indent=2, ensure_ascii=False)
        )

        # leads.csv — pages with contact info meeting accuracy threshold
        leads = [p for p in pages if (
            p["score"] >= self.lead_min_score and (
                p["entities"].get("emails") or
                p["entities"].get("phones") or
                p["entities"].get("wechat")
            )
        )]
        leads.sort(key=lambda p: p["score"], reverse=True)

        with open(job_dir / "leads.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["url", "score", "title", "emails", "phones",
                             "wechat", "line_ids", "organizations", "locations", "language"])
            for p in leads:
                e = p["entities"]
                c = p["content"]
                writer.writerow([
                    p["url"], p["score"], c.get("title", ""),
                    "; ".join(e.get("emails", [])),
                    "; ".join(e.get("phones", [])),
                    "; ".join(e.get("wechat", [])),
                    "; ".join(e.get("line_ids", [])),
                    "; ".join(e.get("organizations", [])),
                    "; ".join(e.get("locations", [])),
                    c.get("language", ""),
                ])

        # meta.json
        elapsed = time.time() - self.stats["start_time"]
        meta = {
            "job_id": self.job_id,
            "query": self.query,
            "mode": self.mode,
            "profile": self.profile,
            "expanded_queries": self.expanded_queries,
            "stats": self.stats,
            "elapsed_seconds": round(elapsed, 1),
            "output_files": ["results.json", "raw_pages.json", "graph.json", "leads.csv", "meta.json"],
        }
        (job_dir / "meta.json").write_text(json.dumps(meta, indent=2))

        log.info(f"Job {self.job_id} outputs written to {job_dir}")
        self._emit("outputs_written", path=str(job_dir), leads=len(leads))


class Engine:
    """Manages multiple concurrent CrawlJobs."""

    def __init__(self):
        self._jobs: dict[str, CrawlJob] = {}
        self._progress_callbacks: list[Callable[[dict], None]] = []

    def on_progress(self, cb: Callable[[dict], None]):
        self._progress_callbacks.append(cb)

    def _broadcast(self, event: dict):
        for cb in self._progress_callbacks:
            try:
                cb(event)
            except Exception:
                pass

    def create_job(self, query: str, mode: Mode, profile: Profile,
                   seed_urls: list[str] | None = None,
                   expanded_queries: list[str] | None = None,
                   accuracy_goal: int = 50) -> str:
        job_id = str(uuid.uuid4())[:8]
        job = CrawlJob(
            job_id=job_id,
            query=query,
            mode=mode,
            profile=profile,
            seed_urls=seed_urls,
            expanded_queries=expanded_queries,
            accuracy_goal=accuracy_goal,
            progress_cb=self._broadcast,
        )
        self._jobs[job_id] = job
        return job_id

    async def run_job(self, job_id: str):
        job = self._jobs.get(job_id)
        if not job:
            raise ValueError(f"Unknown job: {job_id}")
        task = asyncio.create_task(job.run())
        job._task = task
        await task

    def cancel_job(self, job_id: str):
        job = self._jobs.get(job_id)
        if job:
            job.cancel()

    def get_stats(self, job_id: str) -> dict | None:
        job = self._jobs.get(job_id)
        return job.stats if job else None

    async def analyze_website(self, url: str) -> dict:
        """Single-URL website intelligence analysis."""
        from config import PROFILES
        profile = PROFILES["light"]
        async with Crawler(profile) as crawler:
            result = await crawler.fetch(url)
        if not result.ok:
            return {"error": result.error, "url": url}

        intel = analyze_website(url, result.html)
        page = extract(url, result.html)

        return {
            "url": url,
            "website_intel": intel.__dict__,
            "page_extract": {
                "title": page.title,
                "headings": page.headings,
                "word_count": page.word_count,
                "language": page.language,
                "entities": page.entities,
                "metadata": page.metadata,
            }
        }
