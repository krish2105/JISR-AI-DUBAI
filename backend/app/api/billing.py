"""
billing.py — Plans, usage and plan changes (Phase 19). TEST MODE: no payment is taken; a plan change is recorded
and audited so the flow and the quotas can be demonstrated (Stripe needs a registered company: DECISIONS M2).

    GET  /billing/plans     the public plans (pricing page)                                   (public)
    GET  /billing           this organisation's plan, quotas and usage this month             (settings.business)
    POST /billing/plan      change plan (test mode)                                           (billing.manage)
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import require
from app.auth.service import Principal
from app.billing.service import catalogue, usage
from app.db.models import Organisation
from app.db.session import session_scope
from app.governance.audit import append_audit

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/plans")
def plans() -> dict:
    cat = catalogue()
    public = {k: {**{f: v[f] for f in ("name", "price_inr_month", "quotes_per_month", "seats", "features")},
                  "note": v.get("note"), "price_aed_month_reference": round(v["price_inr_month"]
                                                                              * cat["inr_to_aed_reference"])}
              for k, v in cat["plans"].items() if v.get("public", True)}
    return {"plans": public, "currency": "INR", "status": "hypothesis: to be validated in the pilot", "test_mode": True}


@router.get("")
async def billing(principal: Principal = Depends(require("settings.business"))) -> dict:
    return {**await usage(principal.org_id), "test_mode": True}


class PlanBody(BaseModel):
    plan: str = Field(max_length=30)


@router.post("/plan")
async def change_plan(body: PlanBody, principal: Principal = Depends(require("billing.manage"))) -> dict:
    plans_ = catalogue()["plans"]
    if principal.is_sandbox:
        raise HTTPException(403, "The demo sandbox has a fixed plan.")
    if body.plan not in plans_ or not plans_[body.plan].get("public", True):
        raise HTTPException(422, "Choose one of the plans on the pricing page.")
    async with session_scope() as db:
        org = await db.get(Organisation, principal.org_id)
        before = org.plan or catalogue()["default_plan"]
        org.plan = body.plan
        await append_audit(db, org_id=principal.org_id, actor=principal.actor, action="billing.plan_changed",
                           details={"before": before, "after": body.plan, "mode": "test (no payment)"})
    return {**await usage(principal.org_id), "test_mode": True}
