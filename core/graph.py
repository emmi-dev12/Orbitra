"""ORBITRA CORE — crawl graph with BFS frontier and score-based prioritization."""

import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from urllib.parse import urlparse

from config import MAX_PAGES_PER_DOMAIN, MIN_SCORE_THRESHOLD, MAX_DEPTH

log = logging.getLogger("orbitra.graph")


@dataclass
class GraphNode:
    url: str
    score: int = 0
    depth: int = 0
    status: str = "pending"  # pending | crawled | skipped | failed


@dataclass
class CrawlGraph:
    nodes: dict[str, GraphNode] = field(default_factory=dict)
    edges: list[tuple[str, str, str]] = field(default_factory=list)  # (from, to, anchor)
    inbound_count: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    domain_counts: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    # BFS frontier: list of (priority, url) — lower priority = crawled first
    _frontier: list[tuple[float, str]] = field(default_factory=list)
    _in_frontier: set[str] = field(default_factory=set)

    def add_seed(self, url: str, depth: int = 0) -> None:
        if url not in self.nodes:
            node = GraphNode(url=url, depth=depth)
            self.nodes[url] = node
            domain = urlparse(url).netloc
            self._push_frontier(url, score=0, depth=depth)

    def add_edge(self, from_url: str, to_url: str, anchor: str = "") -> None:
        self.edges.append((from_url, to_url, anchor))
        self.inbound_count[to_url] += 1

        if to_url not in self.nodes:
            depth = self.nodes[from_url].depth + 1 if from_url in self.nodes else 1
            self.nodes[to_url] = GraphNode(url=to_url, depth=depth)

    def update_score(self, url: str, score: int) -> None:
        if url in self.nodes:
            self.nodes[url].score = score
            self.nodes[url].status = "crawled"

    def mark_failed(self, url: str) -> None:
        if url in self.nodes:
            self.nodes[url].status = "failed"

    def mark_skipped(self, url: str) -> None:
        if url in self.nodes:
            self.nodes[url].status = "skipped"

    def should_crawl(self, url: str) -> bool:
        node = self.nodes.get(url)
        if not node:
            return False
        if node.status != "pending":
            return False
        if node.depth > MAX_DEPTH:
            return False
        domain = urlparse(url).netloc
        if self.domain_counts[domain] >= MAX_PAGES_PER_DOMAIN:
            return False
        return True

    def prune_low_value(self) -> int:
        """Remove pending nodes scoring below threshold after first pass."""
        pruned = 0
        for url, node in list(self.nodes.items()):
            if node.status == "crawled" and node.score < MIN_SCORE_THRESHOLD:
                # Mark children of low-value nodes as skipped
                children = [to for (f, to, _) in self.edges if f == url]
                for child in children:
                    child_node = self.nodes.get(child)
                    if child_node and child_node.status == "pending":
                        child_node.status = "skipped"
                        pruned += 1
        return pruned

    def next_urls(self, batch_size: int = 10) -> list[str]:
        """Return next batch sorted by score DESC, depth ASC."""
        pending = [
            node for node in self.nodes.values()
            if node.status == "pending"
        ]
        # Sort: higher score first (negative for priority), then shallower depth
        pending.sort(key=lambda n: (-n.score, n.depth))
        result = []
        for node in pending[:batch_size]:
            if self.should_crawl(node.url):
                domain = urlparse(node.url).netloc
                self.domain_counts[domain] += 1
                result.append(node.url)
        return result

    def discover_links(self, from_url: str, links: list[tuple[str, str]],
                       same_domain_only: bool = False) -> int:
        """Add links as edges + pending nodes. Returns count added."""
        from_domain = urlparse(from_url).netloc
        added = 0
        for url, anchor in links:
            if url in self.nodes:
                # Still record the edge even if node exists
                self.add_edge(from_url, url, anchor)
                continue

            to_domain = urlparse(url).netloc
            if same_domain_only and to_domain != from_domain:
                # Add edge but don't add as crawlable node
                self.add_edge(from_url, url, anchor)
                continue

            node = GraphNode(url=url, depth=(self.nodes[from_url].depth + 1
                                             if from_url in self.nodes else 1))
            self.nodes[url] = node
            self.add_edge(from_url, url, anchor)
            added += 1
        return added

    def _push_frontier(self, url: str, score: int, depth: int) -> None:
        if url not in self._in_frontier:
            self._in_frontier.add(url)
            self._frontier.append((-score, url))

    def to_export(self) -> dict:
        nodes_list = [
            {
                "id": url,
                "score": node.score,
                "depth": node.depth,
                "status": node.status,
                "domain": urlparse(url).netloc,
            }
            for url, node in self.nodes.items()
        ]
        edges_list = [
            {"from": f, "to": t, "label": a}
            for f, t, a in self.edges
        ]
        return {
            "nodes": nodes_list,
            "edges": edges_list,
            "stats": {
                "total_nodes": len(self.nodes),
                "total_edges": len(self.edges),
                "crawled": sum(1 for n in self.nodes.values() if n.status == "crawled"),
                "pending": sum(1 for n in self.nodes.values() if n.status == "pending"),
                "failed": sum(1 for n in self.nodes.values() if n.status == "failed"),
                "skipped": sum(1 for n in self.nodes.values() if n.status == "skipped"),
            }
        }

    def top_pages(self, n: int = 100) -> list[GraphNode]:
        crawled = [n for n in self.nodes.values() if n.status == "crawled"]
        crawled.sort(key=lambda x: x.score, reverse=True)
        return crawled[:n]
