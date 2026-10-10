"""
runs.py — API routes for runs and their live event stream.

    POST /runs                  start a run from a message (or a built-in demo sample)
    GET  /runs                  list recent runs of the caller's organisation
    GET  /runs/{id}             one run: status, state, approvals
    GET  /runs/{id}/events      Server-Sent Events: past events, then live ones, until `done`

SSE in one paragraph (beginner notes):
    The browser opens one long HTTP request (EventSource). The server writes lines like
    `id: 7` and `data: {...json...}` followed by a blank line, once per event, and keeps the
    connection open. A comment line `: ping` every 15 s keeps proxies from closing it.
"""

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import org_id_header
from app.api.ratelimit import limit_runs
from app.db.models import Approval, Run, RunEventRow
from app.db.session import session_scope
from app.demo.samples import get_sample
from app.events import TERMINAL_KINDS, RunEvent, bus
from app.runs.service import create_run

router = APIRouter(prefix="/runs", tags=["runs"])
HEARTBEAT_SECONDS = 15


class CreateRunRequest(BaseModel):
    """Body of POST /runs: either a message or a built-in sample id."""

    message: str | None = Field(default=None, max_length=8000)
    sample_id: str | None = None
    channel: str = "form"


@router.post("", status_code=201, dependencies=[Depends(limit_runs)])
async def start_run(body: CreateRunRequest, org_id: str = Depends(org_id_header)) -> dict:
    """Create a run and start the agents in the background; returns the run id at once."""
    message, channel = body.message, body.channel
    if body.sample_id:
        sample = get_sample(body.sample_id)
        if sample is None:
            raise HTTPException(404, "Unknown sample")
        message, channel = sample.message, sample.channel
    if not message or not message.strip():
        raise HTTPException(422, "Provide a message or a sample_id")
    run_id = await create_run(message=message, channel=channel, org_id=org_id, sample_id=body.sample_id)
    return {"run_id": run_id}


@router.get("")
async def list_runs(limit: int = 20, org_id: str = Depends(org_id_header)) -> list[dict]:
    """Most recent runs first."""
    async with session_scope() as db:
        rows = (await db.scalars(select(Run).where(Run.org_id == org_id)
                                 .order_by(Run.created_at.desc()).limit(min(limit, 100)))).all()
    return [{"id": r.id, "status": r.status, "channel": r.channel, "sample_id": r.sample_id,
             "created_at": r.created_at.isoformat()} for r in rows]


@router.get("/{run_id}")
async def get_run(run_id: str, org_id: str = Depends(org_id_header)) -> dict:
    """Full detail of one run (404 if it belongs to another organisation)."""
    async with session_scope() as db:
        run = await db.get(Run, run_id)
        if run is None or run.org_id != org_id:
            raise HTTPException(404, "Run not found")
        approvals = (await db.scalars(select(Approval).where(Approval.run_id == run_id))).all()
    return {
        "id": run.id, "status": run.status, "channel": run.channel, "sample_id": run.sample_id,
        "created_at": run.created_at.isoformat(), "message_redacted": run.raw_redacted, "state": run.state,
        "approvals": [{"id": a.id, "title": a.title, "status": a.status, "risk": a.risk} for a in approvals],
    }


def _sse(event: RunEvent) -> str:
    """Format one event as an SSE message."""
    return f"id: {event.seq}\ndata: {event.model_dump_json()}\n\n"


async def event_stream(run_id: str, after: int = 0) -> AsyncIterator[str]:
    """Yield stored events after `after`, then live events, until a terminal event.

    We subscribe BEFORE reading the database so no event can slip through the gap between
    "read history" and "start listening"; duplicates are skipped by sequence number.
    """
    queue = bus.subscribe(run_id)
    try:
        async with session_scope() as db:
            rows = (await db.scalars(select(RunEventRow).where(RunEventRow.run_id == run_id, RunEventRow.seq > after)
                                     .order_by(RunEventRow.seq))).all()
        last = after
        for row in rows:
            event = RunEvent(run_id=row.run_id, seq=row.seq, ts=row.ts, agent=row.agent, kind=row.kind,
                             payload=row.payload, risk=row.risk)
            yield _sse(event)
            last = event.seq
            if event.kind in TERMINAL_KINDS:
                return
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_SECONDS)
            except TimeoutError:
                yield ": ping\n\n"
                continue
            if event.seq <= last:
                continue
            yield _sse(event)
            last = event.seq
            if event.kind in TERMINAL_KINDS:
                return
    finally:
        bus.unsubscribe(run_id, queue)


@router.get("/{run_id}/events")
async def run_events(
    run_id: str,
    after: int = 0,
    last_event_id: str | None = Header(default=None),
    org_id: str = Depends(org_id_header),
) -> StreamingResponse:
    """Server-Sent Events stream of a run's events (history first, then live).

    Browsers reconnect automatically and send `Last-Event-ID`; we resume after it so a
    dropped connection never duplicates or loses steps.
    """
    if last_event_id and last_event_id.isdigit():
        after = max(after, int(last_event_id))
    async with session_scope() as db:
        run = await db.get(Run, run_id)
        if run is None or run.org_id != org_id:
            raise HTTPException(404, "Run not found")
    return StreamingResponse(
        event_stream(run_id, after),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},   # stop proxies buffering
    )


def parse_sse(text: str) -> list[dict]:
    """Helper for tests and scripts: turn an SSE body back into a list of event dicts."""
    return [json.loads(line[len("data: "):]) for line in text.splitlines() if line.startswith("data: ")]
