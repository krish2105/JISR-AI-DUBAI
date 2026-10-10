"""
test_supervisor_p9.py — Explainable re-planning, clarification instead of guessing, buyer memory (Phase 9).
"""

from sqlalchemy import select

from app.agents.memory import recall
from app.agents.nodes import route_after_pricing
from app.db.models import Run, RunEventRow
from app.db.session import session_scope
from app.runs.service import create_run


async def _run(message: str, contact_key: str | None = None) -> tuple[Run, list[RunEventRow]]:
    run_id = await create_run(message=message, contact_key=contact_key, background=False)
    async with session_scope() as db:
        run = await db.get(Run, run_id)
        events = (await db.scalars(select(RunEventRow).where(RunEventRow.run_id == run_id)
                                   .order_by(RunEventRow.seq))).all()
    return run, events


def _path(events) -> list[str]:
    return [e.agent for e in events if e.kind == "agent_finished"]


def test_routing_rules():
    assert route_after_pricing({"lines": []})[0] == "trust"
    assert route_after_pricing({"lines": [1], "destination_country": "SA"})[0] == "docs"
    assert route_after_pricing({"lines": [1], "destination_country": "AE"})[0] == "duty"
    assert route_after_pricing({"lines": [1], "destination_country": "unknown"})[0] == "duty"


async def test_missing_details_ask_instead_of_guessing(db_ready):
    run, events = await _run("Hi, please send me your catalogue and price list.")
    assert "duty" not in _path(events) and "docs" not in _path(events) and "trust" in _path(events)
    assert run.state["drafts"][-1]["kind"] == "clarification"
    assert any(e.kind == "plan" and e.payload.get("replan") for e in events)


async def test_cepa_step_skipped_outside_the_uae(db_ready):
    _, events = await _run("We need 200 brass lamps CIF Riyadh, Saudi Arabia.")
    assert "duty" not in _path(events) and "docs" in _path(events)


async def test_buyer_memory_fills_incoterm_and_is_shown(db_ready):
    await _run("We need 100 brass lamps CIF Jebel Ali.", contact_key="buyer-1")
    memory = await recall("demo", "buyer-1")
    assert memory["runs"] == 1 and memory["last_incoterm"] == "CIF"
    run, _ = await _run("Again 50 brass lamps please, same as before.", contact_key="buyer-1")
    assert run.state["quote"]["incoterm"] == "CIF"
    assert "incoterm_from_memory" in run.state["quote"]["pricing_flags"]          # still reviewed (P-PRICE-001)
    assert "returning_buyer" in {s["signal"] for s in run.state["buyer_signals"]}
    assert (await recall("demo", "buyer-1"))["runs"] == 2
    assert await recall("demo", "someone-else") is None


async def test_memory_holds_facts_not_text(db_ready):
    await _run("We need 100 brass lamps CIF Jebel Ali. Payment will be made by a third party company.",
               contact_key="buyer-2")
    memory = await recall("demo", "buyer-2")
    assert memory["risk_signals"] == ["third_party_payment"]
    assert "brass" not in str(memory) and "Payment" not in str(memory)
