"""
rbac.py — Suite: does role-based access control behave as the exporter expects? (Phase 13)

Scenarios: data/gold/rbac_scenarios.yaml (33 rows written from the plan's permission table, not from rbac.yaml).
Each row runs through the REAL HTTP API (FastAPI app in-process) with real signed tokens for a fresh organisation
that has one member per role.
Metrics:
    rbac_scenario_pass_rate   rows whose outcome (allowed / denied) matches the expectation
    unsafe_allow_rate         rows expected to be DENIED that were allowed (must be 0)
"""

import uuid

import httpx
import yaml

from app.auth.tokens import issue_access_token
from app.db.models import Approval, Membership, Organisation, Run, User
from app.db.session import session_scope
from app.governance.rbac import ROLES
from eval.common import REPO, EvalContext, SuiteResult


async def _org() -> tuple[str, dict[str, str], dict[str, str]]:
    org_id = f"org_{uuid.uuid4().hex[:12]}"
    tokens, users = {}, {}
    async with session_scope() as db:
        db.add(Organisation(id=org_id, name="Eval exports", plan="growth"))  # 10 seats: one member per role
        await db.flush()
        for role in ROLES:
            user = User(id=f"usr_{uuid.uuid4().hex[:12]}", email=f"{role}-{uuid.uuid4().hex[:8]}@eval.invalid")
            db.add(user)
            await db.flush()
            db.add(Membership(user_id=user.id, org_id=org_id, role=role))
            tokens[role], users[role] = issue_access_token(user.id, org_id, 1), user.id
    return org_id, tokens, users


async def _held(org_id: str, risk: str, reminder: bool, created_by: str | None) -> tuple[str, str]:
    run_id, apr_id = f"run_{uuid.uuid4().hex[:12]}", f"apr_{uuid.uuid4().hex[:12]}"
    payload = {"text": "Dear buyer, please find our quotation.", "language": "en", "channel": "form"}
    if reminder:
        payload["kind"] = "collection_reminder"
    async with session_scope() as db:
        db.add(Run(id=run_id, org_id=org_id, status="needs_approval", raw_redacted="eval", state={},
                   created_by=created_by))
        await db.flush()
        db.add(Approval(id=apr_id, run_id=run_id, org_id=org_id, action_type="send_message", title="Reply",
                        payload=payload, reason="eval", evidence=[], risk=risk, rule_id="P-OUT-001"))
    return run_id, apr_id


async def run(ctx: EvalContext) -> SuiteResult:
    """Play every scenario through the API."""
    from app.main import create_app

    rows = yaml.safe_load((REPO / "data" / "gold" / "rbac_scenarios.yaml").read_text(encoding="utf-8"))
    passed = unsafe = 0
    failures = []
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://eval") as client:
        org, tokens, users = await _org()
        other_org, _, _ = await _org()
        for row in rows:
            headers = {"Authorization": f"Bearer {tokens[row['role']]}"}
            if row["kind"] == "decide":
                _, apr = await _held(org, row["risk"], row.get("reminder", False),
                                     users[row["role"]] if row.get("own") else None)
                body = {"override_reason": row["override"]} if row.get("override") else {}
                r = await client.post(f"/approvals/{apr}/approve", headers=headers, json=body)
            elif row["kind"] == "route":
                r = await client.request(row["method"], row["path"], headers=headers, json=row.get("body"))
            else:                                            # cross_org
                other_run, _ = await _held(other_org, "low", False, None)
                r = await client.get(f"/runs/{other_run}", headers=headers)
            allowed = r.status_code < 300
            ok = allowed == (row["expect"] == "allow")
            passed += ok
            unsafe += allowed and row["expect"] == "deny"
            if not ok:
                failures.append({"id": row["id"], "role": row["role"], "expected": row["expect"],
                                 "status": r.status_code, "detail": r.text[:160], "why": row["why"]})
    n = len(rows)
    return SuiteResult("rbac", n, {"rbac_scenario_pass_rate": passed / n, "unsafe_allow_rate": unsafe / n}, {},
                       failures, ["Scenarios are the owner's expectations from the plan's permission table; they "
                                  "are played through the real API with real tokens."])
