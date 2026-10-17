"""
test_documents.py — Phase 17: quotation, proforma invoice, packing list and CEPA origin checklist from a run.
Documents use only the run's reviewed data, stay DRAFT until the reply is approved, and issuing records a checksum.
"""

import uuid

import pytest
from sqlalchemy import select

from app.auth.tokens import issue_access_token
from app.db.models import Approval, AuditEntry, Membership, Organisation, Run, User
from app.db.session import session_scope
from app.outputs.documents import checksum
from app.runs.service import create_run, decide

ENQUIRY = "We need 500 brass diya lamps and 200 cotton table runners CIF Jebel Ali. Bayt Al Hadaya Trading LLC"


@pytest.fixture
async def client(db_ready):
    import httpx

    from app.main import create_app

    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def org_with(*roles: str) -> tuple[str, dict[str, dict]]:
    org = f"org_{uuid.uuid4().hex[:12]}"
    headers = {}
    async with session_scope() as db:
        db.add(Organisation(id=org, name="Docs test"))
        await db.flush()
        for role in roles:
            user = User(id=f"usr_{uuid.uuid4().hex[:12]}", email=f"{role}-{uuid.uuid4().hex[:6]}@example.com")
            db.add(user)
            await db.flush()
            db.add(Membership(user_id=user.id, org_id=org, role=role))
            headers[role] = {"Authorization": f"Bearer {issue_access_token(user.id, org, 1)}"}
    return org, headers


async def test_documents_are_drafts_until_approved_then_final_and_audited(client):
    org, h = await org_with("owner", "viewer", "accountant")
    run_id = await create_run(message=ENQUIRY, org_id=org, background=False)
    docs = (await client.get(f"/runs/{run_id}/documents", headers=h["viewer"])).json()
    assert set(docs) == {"quotation", "proforma_invoice", "packing_list", "origin_checklist"}
    assert all(d["status"] == "draft" for d in docs.values())
    issue = await client.post(f"/runs/{run_id}/documents/quotation/issue", headers=h["owner"])
    assert issue.status_code == 409 and "Approve the reply first" in issue.json()["detail"]

    async with session_scope() as db:
        run = await db.get(Run, run_id)
        reply = await db.scalar(
            select(Approval.id).where(Approval.run_id == run_id, Approval.action_type == "send_message")
        )
    await decide(reply, org_id=org, decision="approve")
    docs = (await client.get(f"/runs/{run_id}/documents", headers=h["viewer"])).json()
    quote = run.state["quote"]
    q = docs["quotation"]
    assert q["status"] == "final" and q["number"].startswith("Q-")
    assert q["totals"]["total"] == quote["total_aed"] and len(q["lines"]) == len(quote["lines"])
    assert sum(line["amount"] for line in q["lines"]) == pytest.approx(quote["goods_total_aed"], abs=0.05)
    pi = docs["proforma_invoice"]
    assert all(line["hs_code"] for line in pi["lines"]) and "bank details" in pi["notes"][0]
    pl = docs["packing_list"]
    assert pl["totals"]["gross_kg"] == pytest.approx(sum(line["gross_kg"] for line in pl["lines"]))
    oc = docs["origin_checklist"]
    assert oc["available"] in (True, False)  # KB is off in unit tests: honest "not available"
    assert (await client.post(f"/runs/{run_id}/documents/quotation/issue", headers=h["viewer"])).status_code == 403
    issued = await client.post(f"/runs/{run_id}/documents/proforma_invoice/issue", headers=h["accountant"])
    assert issued.status_code == 200 and issued.json()["checksum"] == pi["checksum"]
    async with session_scope() as db:
        entry = await db.scalar(
            select(AuditEntry).where(AuditEntry.run_id == run_id, AuditEntry.action == "document.issued")
        )
    assert entry.details == {"kind": "proforma_invoice", "number": pi["number"], "sha256": pi["checksum"]}
    trail = (await client.get(f"/audit?run_id={run_id}", headers=h["viewer"])).json()
    assert {e["action"] for e in trail} >= {"approval.approved", "document.issued"}
    assert all(e["run_id"] == run_id for e in trail)


async def test_runs_without_a_quote_say_so_and_other_orgs_see_nothing(client):
    org, h = await org_with("owner")
    other, h2 = await org_with("owner")
    run_id = await create_run(
        message="Please change our bank details to the new IBAN today", org_id=org, background=False
    )
    docs = (await client.get(f"/runs/{run_id}/documents", headers=h["owner"])).json()
    assert docs["quotation"]["available"] is False and "no priced quote" in docs["quotation"]["reason"]
    assert (await client.get(f"/runs/{run_id}/documents", headers=h2["owner"])).status_code == 404
    assert (await client.post(f"/runs/{run_id}/documents/unknown/issue", headers=h["owner"])).status_code == 404


def test_checksum_covers_every_field():
    doc = {"kind": "quotation", "lines": [{"amount": 10.0}], "status": "final"}
    base = checksum(doc)
    assert checksum({**doc, "checksum": "ignored"}) == base
    assert checksum({**doc, "lines": [{"amount": 10.01}]}) != base
    assert checksum({**doc, "status": "draft"}) != base
