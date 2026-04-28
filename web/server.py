"""ORBITRA CORE — FastAPI dashboard server."""

import asyncio
import json
import logging
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import (
    FileResponse, HTMLResponse, JSONResponse, StreamingResponse
)
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from db.database import init_db, list_jobs, get_job, get_pages, get_graph
from core.engine import Engine
from core.scorer import expand_queries

log = logging.getLogger("orbitra.server")

app = FastAPI(title="ORBITRA CORE", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

engine = Engine()
_sse_queues: list[asyncio.Queue] = []

STATIC_DIR = Path(__file__).parent / "static"


@app.on_event("startup")
async def startup():
    init_db()
    engine.on_progress(_broadcast_sse)
    log.info("ORBITRA CORE server started")


def _broadcast_sse(event: dict):
    data = json.dumps(event)
    for q in list(_sse_queues):
        try:
            q.put_nowait(data)
        except asyncio.QueueFull:
            pass


# --- Static files ---

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    html_path = STATIC_DIR / "dashboard.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text())
    return HTMLResponse("<h1>ORBITRA CORE</h1><p>Dashboard not found.</p>")


# --- SSE stream for live progress ---

@app.get("/events")
async def events():
    q: asyncio.Queue = asyncio.Queue(maxsize=100)
    _sse_queues.append(q)

    async def generate() -> AsyncGenerator[str, None]:
        try:
            while True:
                try:
                    data = await asyncio.wait_for(q.get(), timeout=30)
                    yield f"data: {data}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            if q in _sse_queues:
                _sse_queues.remove(q)

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# --- Jobs ---

class JobRequest(BaseModel):
    query: str
    mode: str = "research"
    profile: str = "medium"
    seed_urls: list[str] = []
    expanded_queries: list[str] = []


@app.get("/jobs")
async def list_jobs_endpoint():
    return list_jobs()


@app.get("/job/{job_id}")
async def get_job_endpoint(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    job["live_stats"] = engine.get_stats(job_id)
    return job


@app.post("/jobs")
async def create_job(req: JobRequest):
    if req.mode not in ("personal", "research", "leadgen"):
        raise HTTPException(400, "mode must be personal|research|leadgen")
    if req.profile not in ("light", "medium", "heavy"):
        raise HTTPException(400, "profile must be light|medium|heavy")

    expanded = req.expanded_queries or expand_queries(req.query, req.mode)
    job_id = engine.create_job(
        query=req.query,
        mode=req.mode,
        profile=req.profile,
        seed_urls=req.seed_urls,
        expanded_queries=expanded,
    )
    asyncio.create_task(engine.run_job(job_id))
    return {"job_id": job_id, "status": "RUNNING", "expanded_queries": expanded}


@app.delete("/job/{job_id}")
async def cancel_job(job_id: str):
    engine.cancel_job(job_id)
    return {"job_id": job_id, "status": "CANCELLED"}


# --- Pages ---

@app.get("/pages/{job_id}")
async def get_pages_endpoint(
    job_id: str,
    min_score: int = Query(0, ge=0, le=100),
    limit: int = Query(200, ge=1, le=1000),
):
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    pages = get_pages(job_id, min_score=min_score, limit=limit)
    return {"job_id": job_id, "count": len(pages), "pages": pages}


@app.get("/page/{job_id}/inspect")
async def inspect_page(job_id: str, url: str = Query(...)):
    pages = get_pages(job_id, min_score=0, limit=10000)
    for p in pages:
        if p["url"] == url:
            return p
    raise HTTPException(404, "Page not found in job")


# --- Graph ---

@app.get("/graph/{job_id}")
async def get_graph_endpoint(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    graph = get_graph(job_id)
    return graph


# --- Query expansion preview ---

@app.get("/expand")
async def expand(query: str = Query(...), mode: str = Query("research")):
    expanded = expand_queries(query, mode)
    return {"query": query, "mode": mode, "expanded": expanded}


# --- Website analysis ---

@app.post("/analyze")
async def analyze_site(url: str = Query(...)):
    result = await engine.analyze_website(url)
    return result


# --- Download CSV ---

@app.get("/download/{job_id}/csv")
async def download_csv(job_id: str):
    csv_path = Path("results/jobs") / job_id / "leads.csv"
    if not csv_path.exists():
        raise HTTPException(404, "CSV not ready")
    return FileResponse(str(csv_path), filename=f"orbitra_{job_id}_leads.csv",
                        media_type="text/csv")


@app.get("/download/{job_id}/json")
async def download_json(job_id: str):
    json_path = Path("results/jobs") / job_id / "results.json"
    if not json_path.exists():
        raise HTTPException(404, "Results not ready")
    return FileResponse(str(json_path), filename=f"orbitra_{job_id}_results.json",
                        media_type="application/json")


@app.get("/download/{job_id}/graph")
async def download_graph(job_id: str):
    path = Path("results/jobs") / job_id / "graph.json"
    if not path.exists():
        raise HTTPException(404, "Graph not ready")
    return FileResponse(str(path), filename=f"orbitra_{job_id}_graph.json",
                        media_type="application/json")


# --- Stats ---

@app.get("/stats")
async def global_stats():
    jobs = list_jobs()
    return {
        "total_jobs": len(jobs),
        "done": sum(1 for j in jobs if j["status"] == "DONE"),
        "running": sum(1 for j in jobs if j["status"] == "RUNNING"),
        "failed": sum(1 for j in jobs if j["status"] == "FAILED"),
        "total_pages": sum(j.get("page_count", 0) for j in jobs),
    }
