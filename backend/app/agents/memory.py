"""
memory.py — Buyer memory: what Jisr learned about a buyer in earlier runs (Phase 9b).

Why this file exists:
    A real exporter remembers that "Bayt Al Hadaya always buys CIF Jebel Ali and pays on time". Jisr keeps the same
    kind of FACTS per buyer (counts, last Incoterm, languages, last quote total, high-risk signals seen before) so
    agents can use them, visibly:
      * the quote agent fills a missing Incoterm from the buyer's last order, and flags it for review;
      * the trust agent shows "returning buyer, N quotes sent" (positive) or "earlier high-risk signal" (warning).
    Memory is per organisation and per hashed contact; it holds no message text and no personal data.
"""

from datetime import UTC, datetime

from app.db.models import BuyerMemory
from app.db.session import session_scope


async def recall(org_id: str, contact_key: str | None) -> dict | None:
    """The buyer's memory as a plain dict, or None for a first-time (or anonymous) buyer."""
    if not contact_key:
        return None
    async with session_scope() as db:
        row = await db.get(BuyerMemory, (contact_key, org_id))
    if row is None or row.runs == 0:
        return None
    return {"runs": row.runs, "quotes_sent": row.quotes_sent, "last_incoterm": row.last_incoterm,
            "last_quote_total_aed": row.last_quote_total_aed, "languages": row.languages,
            "risk_signals": row.risk_signals, "first_seen": row.first_seen.isoformat(),
            "last_seen": row.last_seen.isoformat()}


async def remember_run(org_id: str, contact_key: str | None, state: dict) -> None:
    """Update the buyer's memory after a run (called once the agents finished)."""
    if not contact_key:
        return
    rfq, quote = state.get("rfq") or {}, state.get("quote") or {}
    high = [s["signal"] for s in state.get("buyer_signals", []) if s.get("risk") == "high"]
    async with session_scope() as db:
        row = await db.get(BuyerMemory, (contact_key, org_id))
        if row is None:
            row = BuyerMemory(contact_key=contact_key, org_id=org_id, runs=0, quotes_sent=0, languages=[],
                              risk_signals=[])
            db.add(row)
        row.runs += 1
        row.last_seen = datetime.now(UTC)
        if rfq.get("incoterm") and not quote.get("incoterm_assumed"):
            row.last_incoterm = rfq["incoterm"]
        if quote.get("total_aed"):
            row.last_quote_total_aed = quote["total_aed"]
        if rfq.get("language") and rfq["language"] not in row.languages:
            row.languages = [*row.languages, rfq["language"]]
        row.risk_signals = sorted(set(row.risk_signals) | set(high))


async def remember_sent(org_id: str, contact_key: str | None) -> None:
    """Count a quote that was approved and delivered."""
    if not contact_key:
        return
    async with session_scope() as db:
        row = await db.get(BuyerMemory, (contact_key, org_id))
        if row is not None:
            row.quotes_sent += 1
