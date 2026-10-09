"""
pricing.py — Tool: price an RFQ into a full quote (goods + Incoterm charges) in INR and AED, deterministically.

Why this file exists:
    Pricing is money: it must be exact, explainable and governed. No model is involved here.

Rules (docs/DECISIONS.md E13, Q2-Q4):
    * Round the UNIT price first; line total = unit price x quantity; quote total = sum of all lines.
    * Mark-up on cost = default margin; volume tiers discount a line; the owner's MINIMUM margin is never
      crossed automatically (price is held at the floor and flagged for the owner).
    * Incoterm decides which shipment costs the seller carries; each is a separate, labelled quote line.
    * Every quote carries its FX rate with source and timestamp, and flags anything a human must review.

Who pays what (seller's side), cumulative:
    EXW: nothing beyond the goods          FCA/FAS/FOB: + inland freight, export clearance
    CFR/CPT: + main freight                CIF/CIP: + insurance (110% of CIF value)
    DAP/DPU: + insurance, destination delivery          DDP: + import clearance, import duty
"""

from decimal import ROUND_HALF_UP, Decimal

from app.agents.state import LineItem
from app.profile import BusinessProfile
from app.tools.fx import FxRate

TWO_PLACES = Decimal("0.01")

SCOPE: dict[str, list[str]] = {
    "EXW": [],
    "FCA": ["inland", "export"], "FAS": ["inland", "export"], "FOB": ["inland", "export"],
    "CFR": ["inland", "export", "freight"], "CPT": ["inland", "export", "freight"],
    "CIF": ["inland", "export", "freight", "insurance"], "CIP": ["inland", "export", "freight", "insurance"],
    "DAP": ["inland", "export", "freight", "insurance", "delivery"],
    "DPU": ["inland", "export", "freight", "insurance", "delivery"],
    "DDP": ["inland", "export", "freight", "insurance", "delivery", "clearance", "duty"],
}
DEFAULT_INCOTERM = "FOB"


def round_money(value: Decimal) -> Decimal:
    """Round to 2 decimal places, half-up (accounting convention), keeping it exact."""
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def money(value: Decimal) -> float:
    """Rounded money as a float for JSON."""
    return float(round_money(value))


def _d(x: float) -> Decimal:
    """Exact decimal from a float (via its string form)."""
    return Decimal(str(x))


def price_quote(items: list[LineItem], profile: BusinessProfile, fx: FxRate, incoterm: str | None = None,
                country: str | None = None) -> dict:
    """Price goods and Incoterm charges; return the quote document with totals, FX provenance and flags."""
    rate = _d(fx.rate)
    flags: list[str] = []
    term = (incoterm or "").upper() or None
    if term not in SCOPE:
        flags.append("incoterm_not_stated" if not term else "incoterm_unknown")
        term = DEFAULT_INCOTERM
    if fx.stale:
        flags.append("fx_stale")

    # ---------- goods lines ----------
    floor, cap = _d(profile.min_margin_pct), _d(profile.max_discount_pct)
    lines, kg_total, cbm_total, margins = [], Decimal(0), Decimal(0), []
    for item in items:
        entry = profile.match(item.description)
        if entry is None:
            flags.append("unpriced_item")
        cost = _d(entry.unit_cost_inr if entry else profile.default_unit_cost_inr)
        qty = _d(item.quantity)
        list_inr = round_money(cost * (1 + _d(profile.default_margin_pct) / 100))
        discount = _d(profile.volume_discount(float(qty)))
        if discount > cap:
            flags.append("discount_above_cap")
        unit_inr = round_money(list_inr * (1 - discount / 100))
        margin = (unit_inr - cost) / cost * 100
        if margin < floor:                                    # never cross the owner's floor automatically
            unit_inr = round_money(cost * (1 + floor / 100))
            margin = (unit_inr - cost) / cost * 100
            flags.append("held_at_margin_floor")
        if item.target_price is not None and _d(item.target_price) < round_money(unit_inr * rate):
            flags.append("target_below_quote")
            target_inr = _d(item.target_price) / rate
            if (target_inr - cost) / cost * 100 < floor:
                flags.append("target_below_floor")
        unit_aed = round_money(unit_inr * rate)
        margins.append(margin)
        kg_total += qty * _d(entry.kg if entry else profile.default_kg)
        cbm_total += qty * _d(entry.cbm if entry else profile.default_cbm)
        lines.append({
            "description": item.description, "quantity": item.quantity, "unit": item.unit,
            "catalogue_item": entry.name if entry else None, "catalogue_match": entry is not None,
            "unit_cost_inr": money(cost), "list_price_inr": money(list_inr), "discount_pct": float(discount),
            "unit_price_inr": money(unit_inr), "unit_price_aed": money(unit_aed),
            "effective_margin_pct": float(round_money(margin)),
            "total_inr": money(unit_inr * qty), "total_aed": money(unit_aed * qty),
        })

    goods_inr = sum((_d(ln["total_inr"]) for ln in lines), Decimal(0))
    goods_aed = sum((_d(ln["total_aed"]) for ln in lines), Decimal(0))

    # ---------- Incoterm charges (one line per cost the seller carries) ----------
    lg = profile.logistics
    country = country if country and country != "unknown" else "unknown"
    charges: list[dict] = []

    def add(code: str, description: str, basis: str, aed: Decimal | None = None, inr: Decimal | None = None) -> None:
        """Add a charge given in one currency; convert the other once and round both."""
        aed = round_money(aed if aed is not None else inr * rate)
        inr = round_money(inr if inr is not None else aed / rate)
        charges.append({"code": code, "description": description, "basis": basis,
                        "total_aed": float(aed), "total_inr": float(inr)})

    scope = SCOPE[term]
    if "inland" in scope:
        basis = f"{float(round_money(kg_total))} kg x INR {lg.inland_freight_inr_per_kg}/kg"
        add("inland", f"Inland freight to {lg.origin_port}", basis, inr=kg_total * _d(lg.inland_freight_inr_per_kg))
    if "export" in scope:
        add("export", "Export clearance and documentation", "per shipment", inr=_d(lg.export_clearance_inr))
    freight_cbm = max(cbm_total, _d(lg.min_cbm))
    if "freight" in scope:
        per_cbm = _d(lg.ocean_freight_aed_per_cbm.get(country, lg.ocean_freight_aed_per_cbm["unknown"]))
        basis = f"{float(round_money(freight_cbm))} CBM x AED {per_cbm}/CBM"
        add("freight", f"Ocean freight {lg.origin_port} -> {country}", basis, aed=freight_cbm * per_cbm)
    if "insurance" in scope:
        cif_base = goods_aed + sum((_d(c["total_aed"]) for c in charges), Decimal(0))
        add("insurance", "Cargo insurance", f"{lg.insurance_pct}% of 110% of CIF value",
            aed=cif_base * Decimal("1.10") * _d(lg.insurance_pct) / 100)
    if "delivery" in scope:
        add("delivery", "Destination delivery", "per shipment", aed=_d(lg.destination_delivery_aed))
    if "clearance" in scope:
        add("clearance", "Import clearance (broker)", "per shipment", aed=_d(lg.destination_clearance_aed))
    if "duty" in scope:
        cif_codes = ("inland", "export", "freight", "insurance")
        cif_value = goods_aed + sum((_d(c["total_aed"]) for c in charges if c["code"] in cif_codes), Decimal(0))
        add("duty", f"Import duty {lg.import_duty_pct}% of CIF value (before any CEPA preference)",
            lg.import_duty_source, aed=cif_value * _d(lg.import_duty_pct) / 100)

    charges_inr = sum((_d(c["total_inr"]) for c in charges), Decimal(0))
    charges_aed = sum((_d(c["total_aed"]) for c in charges), Decimal(0))
    return {
        "lines": lines,
        "charges": charges,
        "incoterm": term,
        "incoterm_assumed": "incoterm_not_stated" in flags or "incoterm_unknown" in flags,
        "destination_country": country,
        "shipment": {"kg": float(round_money(kg_total)), "cbm": float(round_money(cbm_total)),
                     "freight_cbm": float(round_money(freight_cbm))},
        "margin_pct": profile.default_margin_pct,
        "min_effective_margin_pct": float(round_money(min(margins))) if margins else None,
        "fx_inr_to_aed": fx.rate,
        "fx": fx.model_dump(),
        "fx_source": fx.source,
        "goods_total_inr": money(goods_inr), "goods_total_aed": money(goods_aed),
        "charges_total_inr": money(charges_inr), "charges_total_aed": money(charges_aed),
        "total_inr": money(goods_inr + charges_inr),
        "total_aed": money(goods_aed + charges_aed),
        "validity_days": profile.quote_validity_days,
        "pricing_flags": sorted(set(flags)),
        "notes": ["Logistics costs are estimates; confirm with the forwarder before sending.",
                  "Import duty shown before any CEPA preference; see the CEPA analysis."],
    }


def price_lines(items: list[LineItem], profile: BusinessProfile, incoterm: str | None = None) -> dict:
    """Backward-compatible helper (Phase 1-3 callers): goods only, fixed demo rate, EXW scope."""
    from app.tools.fx import fixed_rate

    return price_quote(items, profile, fixed_rate(profile.fx_stub_inr_to_aed), "EXW", None) | {"incoterm": incoterm}
