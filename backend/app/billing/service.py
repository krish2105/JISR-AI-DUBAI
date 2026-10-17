"""
service.py — Plans, monthly usage and quota checks (Phase 19, DECISIONS M1–M2).

Usage is metered from the organisation's own run records (no separate counter to drift): quotes this month = runs
created since the 1st (UTC). Over quota → 402 with a clear message; nothing already running is affected. Seats
count active members plus pending invitations.
"""

from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

import yaml
from sqlalchemy import func, select

from app.db.models import Invitation, Membership, Organisation, Run
from app.db.session import session_scope

PLANS_FILE = Path(__file__).with_name("plans.yaml")


class QuotaExceeded(Exception):
    """The organisation's plan does not allow this (HTTP 402)."""


@lru_cache
def catalogue() -> dict:
    return yaml.safe_load(PLANS_FILE.read_text(encoding="utf-8"))


def plan_by_key(key: str | None) -> tuple[str, dict]:
    plans = catalogue()["plans"]
    key = key if key in plans else catalogue()["default_plan"]
    return key, plans[key]


def month_start(now: datetime | None = None) -> datetime:
    now = now or datetime.now(UTC)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


async def org_plan(db, org_id: str) -> tuple[str, dict]:
    org = await db.get(Organisation, org_id)
    if org is not None and org.is_sandbox:
        return plan_by_key("sandbox")
    return plan_by_key(org.plan if org is not None else None)


async def usage(org_id: str) -> dict:
    """Plan, limits and this month's usage for one organisation."""
    async with session_scope() as db:
        key, plan = await org_plan(db, org_id)
        quotes = await db.scalar(select(func.count()).select_from(Run).where(
            Run.org_id == org_id, Run.created_at >= month_start())) or 0
        seats = (await db.scalar(select(func.count()).select_from(Membership).where(
            Membership.org_id == org_id, Membership.status == "active")) or 0) + (await db.scalar(
            select(func.count()).select_from(Invitation).where(
                Invitation.org_id == org_id, Invitation.accepted_at.is_(None), Invitation.revoked_at.is_(None),
                Invitation.expires_at > datetime.now(UTC))) or 0)
    return {"plan": key, "plan_name": plan["name"], "price_inr_month": plan["price_inr_month"],
            "features": plan["features"], "period_start": month_start().isoformat(),
            "quotes": {"used": quotes, "limit": plan["quotes_per_month"]},
            "seats": {"used": seats, "limit": plan["seats"]}}


async def check_quote_quota(org_id: str) -> None:
    """Raise QuotaExceeded when the organisation used this month's quotes."""
    u = await usage(org_id)
    if u["quotes"]["used"] >= u["quotes"]["limit"]:
        raise QuotaExceeded(f"Your {u['plan_name']} plan includes {u['quotes']['limit']} enquiries a month and they "
                            "are used up. Upgrade in Settings → Billing, or wait for the 1st of next month.")


async def check_seat(org_id: str) -> None:
    """Raise QuotaExceeded when inviting one more person would exceed the plan's seats."""
    u = await usage(org_id)
    if u["seats"]["used"] >= u["seats"]["limit"]:
        raise QuotaExceeded(f"Your {u['plan_name']} plan includes {u['seats']['limit']} seats (members and pending "
                            "invitations). Upgrade to invite more people.")
