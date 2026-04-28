"""ORBITRA CORE — SQLite database layer with WAL mode."""

import sqlite3
import json
import time
from pathlib import Path
from typing import Any
from contextlib import contextmanager
from config import DB_PATH


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def db():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                mode TEXT NOT NULL,
                query TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING',
                profile TEXT NOT NULL DEFAULT 'medium',
                created_at INTEGER NOT NULL,
                finished_at INTEGER,
                page_count INTEGER DEFAULT 0,
                seed_count INTEGER DEFAULT 0,
                error TEXT
            );

            CREATE TABLE IF NOT EXISTS pages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                url TEXT NOT NULL,
                score INTEGER DEFAULT 0,
                depth INTEGER DEFAULT 0,
                content_json TEXT,
                entities_json TEXT,
                score_breakdown_json TEXT,
                crawled_at INTEGER,
                FOREIGN KEY (job_id) REFERENCES jobs(id)
            );

            CREATE TABLE IF NOT EXISTS graph_edges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                from_url TEXT NOT NULL,
                to_url TEXT NOT NULL,
                anchor_text TEXT,
                weight REAL DEFAULT 1.0,
                FOREIGN KEY (job_id) REFERENCES jobs(id)
            );

            CREATE TABLE IF NOT EXISTS query_expansions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                original TEXT NOT NULL,
                expanded TEXT NOT NULL,
                FOREIGN KEY (job_id) REFERENCES jobs(id)
            );

            CREATE INDEX IF NOT EXISTS idx_pages_job_id ON pages(job_id);
            CREATE INDEX IF NOT EXISTS idx_pages_score ON pages(score DESC);
            CREATE INDEX IF NOT EXISTS idx_edges_job_id ON graph_edges(job_id);
            CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
        """)


# --- Job operations ---

def create_job(job_id: str, mode: str, query: str, profile: str) -> None:
    with db() as conn:
        conn.execute(
            "INSERT INTO jobs (id, mode, query, status, profile, created_at) VALUES (?,?,?,?,?,?)",
            (job_id, mode, query, "PENDING", profile, int(time.time()))
        )


def update_job_status(job_id: str, status: str, error: str | None = None) -> None:
    with db() as conn:
        if status in ("DONE", "FAILED", "CANCELLED"):
            conn.execute(
                "UPDATE jobs SET status=?, finished_at=?, error=? WHERE id=?",
                (status, int(time.time()), error, job_id)
            )
        else:
            conn.execute("UPDATE jobs SET status=? WHERE id=?", (status, job_id))


def increment_job_pages(job_id: str) -> None:
    with db() as conn:
        conn.execute("UPDATE jobs SET page_count = page_count + 1 WHERE id=?", (job_id,))


def get_job(job_id: str) -> dict | None:
    with db() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        return dict(row) if row else None


def list_jobs() -> list[dict]:
    with db() as conn:
        rows = conn.execute("SELECT * FROM jobs ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]


# --- Page operations ---

def upsert_page(job_id: str, url: str, score: int, depth: int,
                content: dict, entities: dict, breakdown: dict) -> None:
    with db() as conn:
        conn.execute("""
            INSERT INTO pages (job_id, url, score, depth, content_json, entities_json,
                               score_breakdown_json, crawled_at)
            VALUES (?,?,?,?,?,?,?,?)
            ON CONFLICT DO NOTHING
        """, (job_id, url, score, depth,
              json.dumps(content), json.dumps(entities),
              json.dumps(breakdown), int(time.time())))
        conn.execute("UPDATE jobs SET page_count = page_count + 1 WHERE id=?", (job_id,))


def get_pages(job_id: str, min_score: int = 0, limit: int = 500) -> list[dict]:
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM pages WHERE job_id=? AND score>=? ORDER BY score DESC LIMIT ?",
            (job_id, min_score, limit)
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["content"] = json.loads(d.pop("content_json") or "{}")
            d["entities"] = json.loads(d.pop("entities_json") or "{}")
            d["score_breakdown"] = json.loads(d.pop("score_breakdown_json") or "{}")
            result.append(d)
        return result


# --- Graph operations ---

def insert_edges(job_id: str, edges: list[tuple[str, str, str]]) -> None:
    with db() as conn:
        conn.executemany(
            "INSERT INTO graph_edges (job_id, from_url, to_url, anchor_text) VALUES (?,?,?,?)",
            [(job_id, f, t, a) for f, t, a in edges]
        )


def get_graph(job_id: str) -> dict:
    with db() as conn:
        edges = conn.execute(
            "SELECT from_url, to_url, anchor_text FROM graph_edges WHERE job_id=?",
            (job_id,)
        ).fetchall()
        nodes = set()
        edge_list = []
        for e in edges:
            nodes.add(e["from_url"])
            nodes.add(e["to_url"])
            edge_list.append({"from": e["from_url"], "to": e["to_url"], "label": e["anchor_text"]})
        return {"nodes": list(nodes), "edges": edge_list}


# --- Query expansion storage ---

def save_expansions(job_id: str, original: str, expanded: list[str]) -> None:
    with db() as conn:
        conn.executemany(
            "INSERT INTO query_expansions (job_id, original, expanded) VALUES (?,?,?)",
            [(job_id, original, e) for e in expanded]
        )
