"""
mcp_server.py — Jisr as an MCP server: other AI assistants (e.g. Claude Desktop) can use its trade skills, governed.

Why this file exists:
    The Model Context Protocol lets an assistant call tools on another system. Jisr exposes what it is good at
    (analyse an enquiry end to end, answer CEPA questions with citations, classify goods, check export documents,
    read the approval inbox and governance state) and deliberately NOT what must stay human: there is no tool to
    approve, send, change bank details or turn governance off. Every call is written to the audit chain with the
    actor "mcp" and must be in the MCP passport (app/governance/passports.yaml).

Run:
    stdio (Claude Desktop):   uv --directory backend run python -m app.interop.mcp_server
    HTTP (hosted):            mounted by app/main.py at /mcp (streamable HTTP), bearer token MCP_TOKEN required
SDK: official `mcp` Python SDK 2.x (`MCPServer`, formerly FastMCP).
"""

import asyncio

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from app.config import get_settings
from app.db.session import init_db, session_scope
from app.governance.audit import append_audit
from app.governance.passports import check_tool

READ_ONLY = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False)

mcp = MCPServer(
    name="jisr",
    title="Jisr AI — governed India→UAE trade agent",
    instructions=("Jisr prepares quotes, CEPA duty analyses with official citations, document checks and buyer "
                  "signals for an Indian exporter selling to the UAE. It never sends anything: replies wait for the "
                  "owner's approval in Jisr. Facts come only from cited official sources or are flagged "
                  "'needs human check'."),
    version="0.9.0",
)


async def _audit(tool: str, details: dict) -> None:
    """Every MCP call is checked against the passport and recorded in the audit chain."""
    check_tool("mcp", tool)
    async with session_scope() as db:
        await append_audit(db, org_id=get_settings().default_org_id, actor="mcp", action=f"mcp.{tool}",
                           details=details)


@mcp.tool(annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False,
                                      open_world_hint=False))
async def analyse_enquiry(message: str) -> dict:
    """Run Jisr's agents on a buyer enquiry: quote (INR/AED), CEPA duty analysis, document check and buyer signals.

    Nothing is sent to anyone: the drafted reply waits for the owner's approval inside Jisr.
    """
    from sqlalchemy import select

    from app.db.models import Approval, Run
    from app.runs.service import create_run

    await _audit("analyse_enquiry", {"chars": len(message)})
    run_id = await create_run(message=message[:8000], channel="form", background=False)
    async with session_scope() as db:
        run = await db.get(Run, run_id)
        approvals = (await db.scalars(select(Approval).where(Approval.run_id == run_id))).all()
    return _summary(run, approvals)


def _pick(d: dict, keys: tuple[str, ...]) -> dict:
    return {k: d.get(k) for k in keys}


def _summary(run, approvals) -> dict:
    """A compact, model-friendly view of a finished run."""
    s = run.state
    quote, duty = s.get("quote") or {}, s.get("duty") or {}
    cepa_lines = [{"description": ln.get("description"),
                   "hs": (ln.get("hs_candidates") or [{}])[0].get("best_line"),
                   "rule": (ln.get("rule") or {}).get("text"), "needs_human_check": ln.get("needs_human_check")}
                  for ln in duty.get("lines", [])]
    return {
        "run_id": run.id, "status": run.status,
        "quote": {**_pick(quote, ("total_aed", "total_inr", "incoterm")), "flags": quote.get("pricing_flags", []),
                  "lines": [_pick(ln, ("description", "quantity", "unit_price_aed", "total_aed"))
                            for ln in quote.get("lines", [])]},
        "cepa": {"status": duty.get("status"), "saving_up_to_aed": duty.get("max_potential_saving_aed"),
                 "lines": cepa_lines},
        "document_issues": [_pick(f, ("type", "field", "message", "fix")) for f in s.get("doc_issues", [])],
        "buyer_signals": [_pick(x, ("signal", "risk", "evidence")) for x in s.get("buyer_signals", [])],
        "waiting_for_owner": [{"approval_id": a.id, "title": a.title, "risk": a.risk} for a in approvals
                              if a.status == "pending"],
        "note": "Nothing was sent. The owner approves, edits or rejects the reply in Jisr.",
    }


@mcp.tool(annotations=READ_ONLY)
async def ask_cepa(question: str) -> dict:
    """Answer a question about the India-UAE CEPA, UAE tariff or export procedures from official sources only.

    Every claim cites the document, issuer, date and page; when nothing relevant is found the answer is
    'needs human check' instead of a guess.
    """
    from app.rag.agentic import answer_question
    from app.rag.citations import resolve
    from app.rag.index import index_exists
    from app.rag.retriever import get_retriever

    await _audit("ask_cepa", {"chars": len(question)})
    if not index_exists():
        return {"status": "knowledge_base_unavailable", "needs_human_check": True}
    ans = await answer_question(question[:2000])
    kb = get_retriever().kb
    return {"claims": [{"text": c.text, "sources": [resolve(kb, cid) for cid in c.citations]} for c in ans.claims],
            "needs_human_check": ans.needs_human_check, "note": ans.note}


@mcp.tool(annotations=READ_ONLY)
async def classify_hs(description: str) -> dict:
    """Top-3 UAE tariff headings for a product description, with the tariff line text, duty and a confidence."""
    from app.rag.index import index_exists
    from app.rag.retriever import classify_hs as classify
    from app.rag.retriever import get_retriever

    await _audit("classify_hs", {"chars": len(description)})
    if not index_exists():
        return {"status": "knowledge_base_unavailable", "needs_human_check": True}
    cands = await asyncio.to_thread(classify, get_retriever(), description[:500])
    return {"candidates": [{"heading": c.heading, "tariff_line": c.best_line, "description": c.best_line_desc,
                            "duty_pct": c.duty_pct, "confidence": c.confidence} for c in cands],
            "needs_human_check": True, "source": "Dubai Customs Integrated Customs Tariff (12-digit master)"}


@mcp.tool(annotations=READ_ONLY)
async def check_export_documents(documents: dict) -> dict:
    """Cross-check an export document set (invoice, packing list, certificate of origin, shipping details,
    export declaration) and return each inconsistency with the field, what was expected and how to fix it."""
    from app.tools.doc_checker import check_document_set

    await _audit("check_export_documents", {"keys": sorted(documents)[:10]})
    findings = check_document_set(documents)
    return {"issues": findings, "ok": not findings}


@mcp.tool(annotations=READ_ONLY)
async def list_pending_approvals() -> list[dict]:
    """What is waiting for the owner's decision (read only: approving is only possible inside Jisr)."""
    from sqlalchemy import select

    from app.db.models import Approval

    await _audit("list_pending_approvals", {})
    async with session_scope() as db:
        rows = (await db.scalars(select(Approval).where(Approval.org_id == get_settings().default_org_id,
                                                        Approval.status == "pending")
                                 .order_by(Approval.created_at.desc()).limit(20))).all()
    return [{"approval_id": a.id, "title": a.title, "risk": a.risk, "rules": a.rule_id,
             "created_at": a.created_at.isoformat()} for a in rows]


@mcp.tool(annotations=READ_ONLY)
async def governance_status() -> dict:
    """The kill switch, the autonomy level of every action type and the policy rules (read only)."""
    from app.api.governance import governance_status as status

    await _audit("governance_status", {})
    return await status(get_settings().default_org_id)


async def _main() -> None:
    await init_db()
    await mcp.run_stdio_async()


if __name__ == "__main__":
    asyncio.run(_main())
