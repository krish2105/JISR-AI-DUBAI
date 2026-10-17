"""
documents.py — Quotation, proforma invoice, packing list and CEPA origin checklist from a run (Phase 17).

Rules:
- Built ONLY from the run's stored data (quote, document draft, duty analysis) and the organisation's profile; no model
  writes anything here, so every number on a document is the number the owner reviewed.
- A document is FINAL only when the run's reply was approved (or sent); otherwise it is a DRAFT and says so.
- Each document carries a SHA-256 checksum of its canonical content; issuing a final document records the checksum
  in the audit chain, so a printed copy can later be matched to what Jisr produced.
- Labels are bilingual (English / Arabic), as UAE trade documents commonly are.
"""

import hashlib
import json
from datetime import UTC, datetime

from app.profile import BusinessProfile

KINDS = ("quotation", "proforma_invoice", "packing_list", "origin_checklist")
TITLES = {
    "quotation": ("Quotation", "عرض سعر"),
    "proforma_invoice": ("Proforma invoice", "فاتورة مبدئية"),
    "packing_list": ("Packing list", "قائمة التعبئة"),
    "origin_checklist": ("CEPA origin evidence checklist", "قائمة أدلة المنشأ (سيبا)"),
}
PREFIX = {"quotation": "Q", "proforma_invoice": "PI", "packing_list": "PL", "origin_checklist": "OC"}


def checksum(doc: dict) -> str:
    """SHA-256 of the document's canonical JSON (without the checksum field itself)."""
    body = {k: v for k, v in doc.items() if k != "checksum"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")).hexdigest()


def _number(kind: str, run_id: str, created_at: datetime) -> str:
    return f"{PREFIX[kind]}-{created_at:%Y%m%d}-{run_id.removeprefix('run_')[:6].upper()}"


def _parties(state: dict, profile: BusinessProfile) -> tuple[dict, dict]:
    rfq = state.get("rfq") or {}
    seller = {"name": profile.seller_name, "country": "India", "port_of_loading": profile.logistics.origin_port}
    buyer = {"name": rfq.get("buyer_name") or "Buyer", "country": rfq.get("buyer_country") or "AE"}
    return seller, buyer


def build_documents(*, run_id: str, state: dict, profile: BusinessProfile, created_at: datetime,
                    approved: bool) -> dict[str, dict]:
    """All four documents for a run. Missing inputs give an `available: false` document with the reason."""
    quote = state.get("quote") or {}
    draft = (state.get("docs") or {}).get("draft") or {}
    duty = state.get("duty") or {}
    seller, buyer = _parties(state, profile)
    status = "final" if approved else "draft"
    issued = created_at.astimezone(UTC).date().isoformat()
    currency = quote.get("fx", {}).get("quote_currency") or profile.quote_currency
    base = {"run_id": run_id, "status": status, "date": issued, "seller": seller, "buyer": buyer}
    docs: dict[str, dict] = {}

    lines = quote.get("lines") or []
    if lines:
        priced = [{"description": ln["description"], "quantity": ln["quantity"], "unit": ln.get("unit", "pcs"),
                   "unit_price": ln["unit_price_aed"], "amount": ln["total_aed"],
                   "unit_price_inr": ln.get("unit_price_inr"), "catalogue_match": ln.get("catalogue_match", False)}
                  for ln in lines]
        charges = [{"description": c["description"], "amount": c["total_aed"]} for c in quote.get("charges") or []]
        totals = {"goods": quote.get("goods_total_aed"), "charges": quote.get("charges_total_aed"),
                  "total": quote.get("total_aed"), "total_inr": quote.get("total_inr"),
                  "fx_inr_to_aed": quote.get("fx_inr_to_aed"), "fx_source": quote.get("fx_source")}
        terms = {"incoterm": quote.get("incoterm"), "incoterm_assumed": quote.get("incoterm_assumed", False),
                 "validity_days": quote.get("validity_days"), "currency": currency,
                 "destination_country": quote.get("destination_country")}
        notes = list(quote.get("notes") or [])
        docs["quotation"] = {**base, "lines": priced, "charges": charges, "totals": totals, "terms": terms,
                             "notes": notes}
        hs_by_desc = {ln["description"]: ln.get("hs_code") for ln in (draft.get("invoice") or {}).get("lines", [])}
        docs["proforma_invoice"] = {**base,
                                    "lines": [{**p, "hs_code": hs_by_desc.get(p["description"])} for p in priced],
                                    "charges": charges, "totals": totals, "terms": terms,
                                    "notes": ["Payment terms and bank details are provided by the seller separately "
                                              "and are never changed by message."]}
        shipment = quote.get("shipment") or {}
        pack = (draft.get("packing_list") or {}).get("lines") or []
        docs["packing_list"] = {**base, "lines": [{"description": p["description"], "hs_code": p.get("hs_code"),
                                                   "quantity": p["quantity"], "gross_kg": p.get("gross_kg")}
                                                  for p in pack],
                                "totals": {"gross_kg": round(sum((p.get("gross_kg") or 0) for p in pack), 2),
                                           "cbm": shipment.get("cbm"), "packages": None},
                                "terms": {"port_of_loading": seller["port_of_loading"],
                                          "incoterm": quote.get("incoterm")},
                                "notes": ["Weights are estimates from the catalogue; confirm after packing."]}
    else:
        for kind in ("quotation", "proforma_invoice", "packing_list"):
            docs[kind] = {**base, "available": False, "reason": "This run has no priced quote."}

    duty_lines = duty.get("lines") or []
    if duty_lines:
        docs["origin_checklist"] = {
            **base,
            "lines": [{"description": ln.get("description"),
                       "hs_candidates": [c.get("best_line") for c in (ln.get("hs_candidates") or [])][:3],
                       "rule": (ln.get("rule") or {}).get("text"), "rule_ref": (ln.get("rule") or {}).get("page_label"),
                       "evidence_needed": ln.get("evidence_needed") or [],
                       "needs_human_check": bool(ln.get("needs_human_check"))} for ln in duty_lines],
            "common_requirements": [r.get("text") for r in duty.get("common_requirements") or []],
            "notes": [duty.get("note") or "Origin rules from the India–UAE CEPA Final Agreement (Annex 3B); "
                      "confirm with your customs adviser before claiming the preference."],
        }
    else:
        docs["origin_checklist"] = {**base, "available": False, "reason": "No CEPA analysis for this run."}

    for kind, doc in docs.items():
        doc["kind"], doc["title"], doc["title_ar"] = kind, *TITLES[kind]
        doc["number"] = _number(kind, run_id, created_at)
        doc.setdefault("available", True)
        doc["checksum"] = checksum(doc)
    return docs
