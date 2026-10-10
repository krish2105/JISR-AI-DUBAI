"""
emitter.py — How agents report progress: save an event, then push it live.

Why this file exists:
    Every RunEvent must (1) get the next sequence number for its run, (2) be stored in
    `run_events` so the timeline and replays survive restarts, and (3) be published on the
    event bus so open browsers see it at once. Doing all three in one helper means no agent
    can forget a step.
"""

import asyncio
from collections import defaultdict

from sqlalchemy import func, select

from app.db.models import RunEventRow
from app.db.session import session_scope
from app.events import RunEvent, bus
from app.governance.passports import ToolNotAllowed, check_tool

# One lock per run so two concurrent emits can never get the same sequence number.
_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)


async def emit(run_id: str, agent: str, kind: str, payload: dict | None = None, risk: str | None = None) -> RunEvent:
    """Store and publish one event; returns it with its sequence number filled in."""
    async with _locks[run_id]:
        async with session_scope() as db:
            last_seq = await db.scalar(select(func.max(RunEventRow.seq)).where(RunEventRow.run_id == run_id))
            event = RunEvent(run_id=run_id, seq=(last_seq or 0) + 1, agent=agent, kind=kind,
                             payload=payload or {}, risk=risk)
            db.add(RunEventRow(run_id=run_id, seq=event.seq, ts=event.ts, agent=agent, kind=kind,
                               payload=event.payload, risk=risk))
    bus.publish(event)          # after commit, so a listener can always re-read it from the DB
    return event


class RunEmitter:
    """Per-run helper handed to every agent node through LangGraph's config."""

    def __init__(self, run_id: str, delay_ms: int = 0) -> None:
        self.run_id = run_id
        self.delay_ms = delay_ms

    async def emit(self, agent: str, kind: str, payload: dict | None = None, risk: str | None = None) -> RunEvent:
        """Emit an event for this run. A tool call outside the agent's passport is refused (and shown)."""
        if kind == "tool_call":
            try:
                check_tool(agent, str((payload or {}).get("tool", "")))
            except ToolNotAllowed as exc:
                await emit(self.run_id, agent, "blocked", {"tool": (payload or {}).get("tool"),
                                                            "reasons": [str(exc)], "rule_ids": ["PASSPORT"]}, "high")
                raise
        return await emit(self.run_id, agent, kind, payload, risk)

    async def pace(self) -> None:
        """Short pause between steps so a human can follow the live demo (0 in tests)."""
        if self.delay_ms > 0:
            await asyncio.sleep(self.delay_ms / 1000)
