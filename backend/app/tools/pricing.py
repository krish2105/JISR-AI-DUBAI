"""
pricing.py — Tool: price RFQ lines in INR and AED with invoice-safe rounding (deterministic).

Rule (docs/DECISIONS.md E13): round the UNIT price first, then line total = unit price x quantity,
and quote total = sum of line totals, so every printed number adds up to the cent.
Phase 4 adds Incoterm costs, live FX with source/timestamp and margin floors.
"""

from decimal import ROUND_HALF_UP, Decimal

from app.agents.state import LineItem
from app.profile import BusinessProfile

TWO_PLACES = Decimal("0.01")


def round_money(value: Decimal) -> Decimal:
    """Round to 2 decimal places, half-up (accounting convention), keeping it exact."""
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def money(value: Decimal) -> float:
    """Rounded money as a float for JSON."""
    return float(round_money(value))


def price_lines(items: list[LineItem], profile: BusinessProfile, incoterm: str | None = None) -> dict:
    """Price every item; return the quote document (lines, totals, FX and margin used)."""
    fx = Decimal(str(profile.fx_stub_inr_to_aed))
    margin = Decimal(str(profile.default_margin_pct)) / Decimal(100)
    lines, total_inr, total_aed = [], Decimal(0), Decimal(0)
    for item in items:
        entry = profile.match(item.description)
        cost = Decimal(str(entry.unit_cost_inr if entry else profile.default_unit_cost_inr))
        unit_inr = round_money(cost * (1 + margin))
        unit_aed = round_money(unit_inr * fx)
        qty = Decimal(str(item.quantity))
        line_inr, line_aed = unit_inr * qty, unit_aed * qty
        total_inr += line_inr
        total_aed += line_aed
        lines.append({
            "description": item.description, "quantity": item.quantity, "unit": item.unit,
            "unit_cost_inr": money(cost), "unit_price_inr": money(unit_inr), "unit_price_aed": money(unit_aed),
            "total_inr": money(line_inr), "total_aed": money(line_aed), "catalogue_match": bool(entry),
        })
    return {
        "lines": lines,
        "incoterm": incoterm,
        "margin_pct": profile.default_margin_pct,
        "fx_inr_to_aed": float(fx),
        "fx_source": "STUB fixed rate (Phase 4: live FX with source and timestamp)",
        "total_inr": money(total_inr),
        "total_aed": money(total_aed),
        "validity_days": profile.quote_validity_days,
    }
