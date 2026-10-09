"""
events.py — Run events: the live story of what the agents are doing (FROZEN CONTRACT).

Why this file exists:
    Every visible thing in the dashboard (the timeline, the agent graph, later the 3D graph)
    and every replay recording is driven by one stream of `RunEvent`s. Agents call
    `emitter.emit(...)`; the event is saved to the database (so it survives restarts and can
    be replayed) and pushed to any browser listening on `GET /runs/{id}/events` (SSE).

How the live push works (beginner notes):
    `EventBus` keeps, per run, a set of asyncio queues: one per open browser connection.
    `publish` drops the event into each queue; the SSE endpoint reads from its queue.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

EventKind = Literal[
    "run_started",        # a run was created
    "agent_started",      # a node began work
    "agent_finished",     # a node finished (payload has its short "why" and outputs)
    "plan",               # the supervisor's plan
    "tool_call",          # an agent called a tool (pricing, FX, retrieval, ...)
    "tool_result",        # the tool's (summarised) result
    "retrieval_attempt",  # one retrieval try in the corrective loop (Phase 5)
    "policy_decision",    # governance evaluated an action: allow / require_approval / block
    "approval_needed",    # an action is waiting in the approval inbox
    "approval_decided",   # a human approved, edited or rejected it
    "blocked",            # governance blocked an action or the run
    "error",              # something failed (with recovery info)
    "done",               # terminal: nothing more will happen in this run
]

# Kinds after which the stream for a run can close.
TERMINAL_KINDS: frozenset[str] = frozenset({"done"})

Risk = Literal["low", "medium", "high"]


class RunEvent(BaseModel):
    """One step in a run, as stored and as sent to the browser."""

    run_id: str
    seq: int                                   # 1, 2, 3... ordering within the run
    ts: datetime = Field(default_factory=lambda: datetime.now(UTC))
    agent: str                                 # one of state.AGENTS, or "human"/"system"
    kind: EventKind
    payload: dict = Field(default_factory=dict)
    risk: Risk | None = None


class EventBus:
    """In-process publish/subscribe of run events, keyed by run id."""

    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue[RunEvent]]] = defaultdict(set)

    def subscribe(self, run_id: str) -> asyncio.Queue[RunEvent]:
        """Open a queue that receives every future event of this run."""
        queue: asyncio.Queue[RunEvent] = asyncio.Queue()
        self._subscribers[run_id].add(queue)
        return queue

    def unsubscribe(self, run_id: str, queue: asyncio.Queue[RunEvent]) -> None:
        """Close a queue (called when the browser disconnects)."""
        self._subscribers[run_id].discard(queue)
        if not self._subscribers[run_id]:
            self._subscribers.pop(run_id, None)

    def publish(self, event: RunEvent) -> None:
        """Deliver an event to every listener of its run (never blocks)."""
        for queue in list(self._subscribers.get(event.run_id, ())):
            queue.put_nowait(event)


# One bus for the whole API process.
bus = EventBus()
