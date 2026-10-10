"""
a2a_server.py — Jisr as an A2A agent: a buyer's procurement agent can request a quotation, agent to agent.

Why this file exists:
    Gulf buyers increasingly run their own procurement agents. The Agent2Agent protocol (A2A 1.0, Linux Foundation)
    lets such an agent discover Jisr (Agent Card at /.well-known/agent-card.json) and send an RFQ as a task. The rules
    do not change because the requester is a machine:
      * the RFQ goes through the same pipeline (redaction, injection guard, quote, CEPA, documents, trust, governance);
      * a malicious agent message (prompt injection, bank-detail change) is REJECTED with the policy reason;
      * the quotation only reaches the buyer agent after the owner approves it: approval completes the A2A task
        through app/channels/outbox.py, the single door out. Until then the task stays "working".

Official SDK: a2a-sdk 1.2 (protobuf types). Tasks live in memory (a restart forgets open A2A tasks; the run and
its approval survive in the database).
"""

from datetime import UTC, datetime

from a2a.helpers import get_data_parts, get_message_text, new_data_part, new_task_from_user_message, new_text_part
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import add_a2a_routes_to_fastapi, create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.types import AgentCapabilities, AgentCard, AgentInterface, AgentSkill, Artifact, Message, Role, TaskState
from sqlalchemy import select

from app.channels.inbound import contact_key
from app.config import get_settings
from app.db.models import Contact, Run, RunEventRow
from app.db.session import session_scope
from app.governance.audit import append_audit
from app.profile import get_business_profile

TASK_STORE = InMemoryTaskStore()
_CALL_CONTEXTS: dict[str, object] = {}       # task id -> the caller's context (needed to update the task later)


def agent_card(base_url: str) -> AgentCard:
    """What a buyer agent learns about Jisr before talking to it."""
    seller = get_business_profile().seller_name
    return AgentCard(
        name=f"Jisr export desk — {seller}",
        description=("Quotations for Indian handicrafts and home textiles delivered to the UAE: INR/AED prices with "
                     "Incoterm charges, a CEPA duty analysis with official citations, and the export document pack. "
                     "Every quotation is approved by the seller before it is returned."),
        version="0.9.0",
        supported_interfaces=[AgentInterface(url=f"{base_url}/a2a", protocol_binding="JSONRPC",
                                             protocol_version="1.0")],
        capabilities=AgentCapabilities(streaming=False, push_notifications=False),
        default_input_modes=["text/plain", "application/json"],
        default_output_modes=["application/json", "text/plain"],
        skills=[AgentSkill(
            id="request_quotation", name="Request a quotation",
            description=("Send products, quantities, destination and Incoterm (text in English or Arabic, or JSON "
                         "{items:[{description, quantity, unit}], incoterm, destination}). The task completes with the "
                         "approved quotation; it stays 'working' while the seller reviews it."),
            tags=["quotation", "rfq", "india-uae", "cepa", "handicrafts"],
            examples=["300 brass diya lamps and 200 cotton table runners, CIF Jebel Ali, before 15 December",
                      '{"items":[{"description":"pashmina shawls","quantity":100}],'
                      '"incoterm":"CIF","destination":"Dubai"}'],
            input_modes=["text/plain", "application/json"], output_modes=["application/json", "text/plain"])],
    )


def rfq_text(message: Message) -> str:
    """The RFQ as text: the message text plus structured data parts written out (the parser reads both)."""
    text = get_message_text(message)
    for data in get_data_parts(list(message.parts)):
        if isinstance(data, dict):
            def qty(v):                                 # JSON numbers arrive as floats ("4.0")
                return int(v) if isinstance(v, float) and v.is_integer() else v

            items = "; ".join(f"{qty(i.get('quantity', ''))} {i.get('unit', 'pcs')} {i.get('description', '')}".strip()
                              for i in data.get("items", []) if isinstance(i, dict))
            text += f"\nWe need {items}. {data.get('incoterm', '')} {data.get('destination', '')}".rstrip()
            if data.get("buyer"):
                text += f"\n— {data['buyer']}"
    return text.strip()


class JisrQuoteExecutor(AgentExecutor):
    """Runs Jisr's agents for an A2A request; the reply is delivered only after the owner's approval."""

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        from app.runs.service import create_run

        task = context.current_task or new_task_from_user_message(context.message)
        if context.current_task is None:
            await event_queue.enqueue_event(task)
        _CALL_CONTEXTS[task.id] = context.call_context
        updater = TaskUpdater(event_queue, task.id, task.context_id)
        await updater.start_work()

        org = get_settings().default_org_id
        address = f"{task.id}|{task.context_id}"
        key = contact_key(org, "a2a", address)
        async with session_scope() as db:
            contact = await db.get(Contact, key)
            if contact is None:
                db.add(Contact(contact_key=key, org_id=org, channel="a2a", address=address,
                               last_inbound_at=datetime.now(UTC)))
        text = rfq_text(context.message)
        run_id = await create_run(message=text or "(empty request)", channel="a2a", org_id=org, contact_key=key,
                                  meta={"source": "a2a", "a2a_task": task.id}, background=False)
        async with session_scope() as db:
            run = await db.get(Run, run_id)
            errored = await db.scalar(select(RunEventRow.id).where(RunEventRow.run_id == run_id,
                                                                    RunEventRow.kind == "error").limit(1))
        if errored is not None:                         # a technical failure is not a policy decision
            await updater.failed(updater.new_agent_message(
                [new_text_part("The request could not be processed; the seller has been notified."),
                 new_data_part({"run_id": run_id, "status": "failed"})]))
            return
        if run.status == "blocked":
            await updater.reject(updater.new_agent_message(
                [new_text_part("Request refused by the seller's governance policies (the message asked for an action "
                               "that is never performed automatically). A person at the seller will review it."),
                 new_data_part({"run_id": run_id, "status": "rejected",
                                "flags": run.state.get("injection_flags", [])})]))
            return
        await updater.update_status(TaskState.TASK_STATE_WORKING, updater.new_agent_message(
            [new_text_part("Quotation prepared. The seller is reviewing it; this task completes when it is approved."),
             new_data_part({"run_id": run_id, "status": run.status})]))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        task = context.current_task
        if task is not None:
            await TaskUpdater(event_queue, task.id, task.context_id).cancel()


async def deliver(address: str, payload: dict, org_id: str) -> dict:
    """Complete the buyer agent's task with the APPROVED reply (called only by the outbox)."""
    task_id = address.split("|", 1)[0]
    ctx = _CALL_CONTEXTS.get(task_id)
    task = await TASK_STORE.get(task_id, ctx) if ctx is not None else None
    if task is None:
        async with session_scope() as db:
            await append_audit(db, org_id=org_id, actor="channel:a2a", action="a2a.task_unavailable",
                               details={"task_id": task_id})
        return {"channel": "a2a", "delivered": False}
    reply = Message(message_id=f"msg-{task_id[:8]}-reply", context_id=task.context_id, task_id=task.id,
                    role=Role.ROLE_AGENT, parts=[new_text_part(payload.get("text", ""))])
    task.status.state = TaskState.TASK_STATE_COMPLETED
    task.status.message.CopyFrom(reply)
    quote = {k: payload.get(k) for k in ("total_aed", "incoterm", "language", "min_effective_margin_pct")
             if payload.get(k) is not None}
    task.artifacts.append(Artifact(artifact_id=f"quote-{task_id[:8]}", name="approved_quotation",
                                   parts=[new_data_part(quote), new_text_part(payload.get("text", ""))]))
    await TASK_STORE.save(task, ctx)
    return {"channel": "a2a", "delivered": True, "task_id": task_id}


def mount(app, base_url: str) -> None:
    """Add the Agent Card and the JSON-RPC endpoint (/a2a) to the FastAPI app."""
    card = agent_card(base_url)
    handler = DefaultRequestHandler(agent_executor=JisrQuoteExecutor(), task_store=TASK_STORE, agent_card=card)
    add_a2a_routes_to_fastapi(app, agent_card_routes=create_agent_card_routes(card),
                              jsonrpc_routes=create_jsonrpc_routes(handler, rpc_url="/a2a"))
