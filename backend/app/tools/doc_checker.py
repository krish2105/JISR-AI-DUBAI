"""
doc_checker.py — Tool: cross-check an export document set for the mistakes that hold shipments at customs.

Why this file exists:
    A wrong HS code on the certificate of origin, a quantity that differs between invoice and packing list, or a
    transshipment without a through bill of lading can cost the CEPA preference or days at the port. These checks
    are deterministic code (never a model): the same documents always give the same findings, and every finding
    says which field, what was expected, what was found and how to fix it.

Contract (frozen in Phase 2, used by the eval suite `docs`):
    check_document_set(documents) -> list of findings
        {"type", "field", "severity", "message", "fix", "expected", "found", "rule_ref"}
    Types: hs_mismatch, qty_mismatch, line_total_mismatch, invoice_total_mismatch, missing_coo,
           missing_export_declaration, currency_mismatch, weight_inconsistency, consignment_gap.

Input shape (keys are optional; a missing document is itself a finding where the treaty needs it):
    invoice {currency, lines[{description, hs_code, quantity, unit_price, amount}], total}, quote_currency,
    packing_list {lines[{hs_code, quantity, net_kg, gross_kg}]}, certificate_of_origin {present, hs_codes[]},
    cepa_preference_claimed, shipping {transshipment_port, through_bill_of_lading}, export_declaration
    {shipping_bill_no}

Values are normalised before comparing ("6214.20.10" == "62142010", "500 pcs" == 500, "52,840.00" == 52840),
so harmless formatting differences never raise a finding (measured by the clean noisy sets in the eval).
"""

import re
from typing import Any

IS_STUB = False

# Treaty references for findings that affect the CEPA preference (resolved to cited passages by the Docs agent).
RULE_REFS = {
    "missing_coo": "CEPA Article 3.13",          # proof of origin needed to claim the preference
    "consignment_gap": "CEPA Article 3.12",      # direct consignment / transport through a third country
    "hs_mismatch": "CEPA Article 3.13",          # the certificate must describe the goods actually shipped
}
SEVERITY = {
    "missing_coo": "high", "consignment_gap": "high", "hs_mismatch": "high", "missing_export_declaration": "high",
    "qty_mismatch": "medium", "invoice_total_mismatch": "medium", "line_total_mismatch": "medium",
    "currency_mismatch": "medium", "weight_inconsistency": "medium",
}


# ---------------------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------------------


def hs_digits(value: Any) -> str:
    """HS code as digits only ('6214.20.10' -> '62142010'); empty string when absent."""
    return re.sub(r"\D", "", str(value or ""))


def same_hs(a: Any, b: Any) -> bool:
    """Two HS codes agree if, after normalisation, the shorter is a prefix of the longer (at least a 4-digit heading).

    A certificate may legitimately give 6 digits (the harmonised level) where the invoice gives 8, and a seller's
    catalogue may only hold the heading; the comparison then happens at the level both documents give.
    """
    x, y = hs_digits(a), hs_digits(b)
    if not x or not y:
        return True                                     # nothing to compare: absence is checked elsewhere
    short, long_ = sorted((x, y), key=len)
    return len(short) >= 4 and long_.startswith(short)


def number(value: Any) -> float | None:
    """A number from a value or a string like '1,200 pcs' / 'AED 52,840.00'; None when there is none."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    m = re.search(r"-?\d[\d,]*(?:\.\d+)?", str(value))
    return float(m.group().replace(",", "")) if m else None


def _money_tolerance(quantity: float | None) -> float:
    """A unit price rounded to cents can move a line total by up to half a cent per unit."""
    return max(0.05, (quantity or 0) * 0.005)


# ---------------------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------------------


def _finding(kind: str, field: str, message: str, fix: str, expected: Any = None, found: Any = None) -> dict:
    return {"type": kind, "field": field, "severity": SEVERITY[kind], "message": message, "fix": fix,
            "expected": expected, "found": found, "rule_ref": RULE_REFS.get(kind)}


def _norm_desc(text: Any) -> str:
    """Description for matching: lower case, punctuation removed."""
    return re.sub(r"\W+", " ", str(text or "").lower()).strip()


def _match_packing(inv_lines: list[dict], pl_lines: list[dict]) -> dict[int, int]:
    """Invoice line -> packing-list line. Documents from different systems list goods in different orders, so lines
    are matched by description; position is used only when a packing line has no description."""
    mapping: dict[int, int] = {}
    used: set[int] = set()
    for i, ln in enumerate(inv_lines):
        d = _norm_desc(ln.get("description"))
        j = next((j for j, p in enumerate(pl_lines) if j not in used and d and _norm_desc(p.get("description")) == d),
                 None)
        if j is None and i < len(pl_lines) and i not in used and not _norm_desc(pl_lines[i].get("description")):
            j = i
        if j is not None:
            mapping[i] = j
            used.add(j)
    return mapping


def _line_checks(inv_lines: list[dict], pl_lines: list[dict], coo: dict) -> list[dict]:
    """Per-line arithmetic and cross-document checks."""
    out = []
    for i, ln in enumerate(inv_lines):
        qty, price, amount = number(ln.get("quantity")), number(ln.get("unit_price")), number(ln.get("amount"))
        if qty is not None and price is not None and amount is not None:
            expected = round(qty * price, 2)
            if abs(expected - amount) > _money_tolerance(qty):
                out.append(_finding("line_total_mismatch", f"invoice.line[{i}].amount",
                                    f"Invoice line {i + 1}: {qty:g} x {price:,.2f} = {expected:,.2f}, "
                                    f"but the line says {amount:,.2f}.",
                                    "Correct the line amount (quantity x unit price).", expected, amount))
    for i, j in _match_packing(inv_lines, pl_lines).items():
        ln, pl = inv_lines[i], pl_lines[j]
        qty, pl_qty = number(ln.get("quantity")), number(pl.get("quantity"))
        if qty is not None and pl_qty is not None and abs(qty - pl_qty) > 1e-6:
            out.append(_finding("qty_mismatch", f"packing_list.line[{j}].quantity",
                                f"{ln.get('description', f'Line {i + 1}')}: invoice quantity {qty:g}, "
                                f"packing list {pl_qty:g}.",
                                "Make the packing list match the goods invoiced (or re-issue the invoice).",
                                qty, pl_qty))
        if not same_hs(ln.get("hs_code"), pl.get("hs_code")):
            out.append(_finding("hs_mismatch", f"packing_list.line[{j}].hs_code",
                                f"{ln.get('description', f'Line {i + 1}')}: invoice HS {ln.get('hs_code')}, "
                                f"packing list HS {pl.get('hs_code')}.",
                                "Use one confirmed HS code on every document.",
                                hs_digits(ln.get("hs_code")), hs_digits(pl.get("hs_code"))))
    # Certificate of origin: every invoice code must appear on it (in any order); leftovers are mismatches.
    coo_codes = (coo.get("hs_codes") or []) if coo.get("present", True) else []
    free = list(range(len(coo_codes)))
    unmatched = []
    for i, ln in enumerate(inv_lines):
        k = next((k for k in free if same_hs(ln.get("hs_code"), coo_codes[k])), None)
        if k is None:
            unmatched.append(i)
        else:
            free.remove(k)
    for i, k in zip(unmatched, free, strict=False):
        ln = inv_lines[i]
        out.append(_finding("hs_mismatch", f"certificate_of_origin.line[{k}].hs_code",
                            f"{ln.get('description', f'Line {i + 1}')}: invoice HS {ln.get('hs_code')}, "
                            f"certificate of origin HS {coo_codes[k]}.",
                            "Amend the certificate application so it describes the goods on the invoice; a "
                            "mismatch can cost the CEPA preference.",
                            hs_digits(ln.get("hs_code")), hs_digits(coo_codes[k])))
    for j, pl in enumerate(pl_lines):
        net, gross = number(pl.get("net_kg")), number(pl.get("gross_kg"))
        if net is not None and gross is not None and net > gross + 0.01:
            out.append(_finding("weight_inconsistency", f"packing_list.line[{j}].net_kg",
                                f"Packing list line {j + 1}: net weight {net:g} kg is more than gross {gross:g} kg.",
                                "Re-weigh or correct net/gross weights (net excludes packaging).",
                                f"<= {gross:g}", net))
    return out


def check_document_set(documents: dict, stage: str = "shipment") -> list[dict]:
    """Return consistency findings for one document set (empty list = no issues found).

    stage="draft" (a quote-stage pack prepared by Jisr): only cross-document consistency is checked; documents that
    do not exist yet (shipping bill, issued certificate) are to-dos in the pack, not mistakes.
    """
    inv = documents.get("invoice") or {}
    inv_lines = inv.get("lines") or []
    pl_lines = (documents.get("packing_list") or {}).get("lines") or []
    coo = documents.get("certificate_of_origin") or {"present": False}
    findings = _line_checks(inv_lines, pl_lines, coo)

    total, amounts = number(inv.get("total")), [number(ln.get("amount")) for ln in inv_lines]
    if total is not None and amounts and None not in amounts:
        expected = round(sum(amounts), 2)
        if abs(expected - total) > 0.05:
            findings.append(_finding("invoice_total_mismatch", "invoice.total",
                                     f"Invoice total {total:,.2f} differs from the sum of its lines {expected:,.2f}.",
                                     "Recalculate the invoice total.", expected, total))

    if stage != "draft" and documents.get("cepa_preference_claimed") and not coo.get("present", False):
        findings.append(_finding("missing_coo", "certificate_of_origin",
                                 "CEPA preference is claimed but there is no certificate of origin.",
                                 "Apply for a CEPA certificate of origin before shipment, or drop the preference "
                                 "claim and pay the MFN duty.", "certificate present", "missing"))

    declaration = documents.get("export_declaration") or {}
    if stage != "draft" and not str(declaration.get("shipping_bill_no") or "").strip():
        findings.append(_finding("missing_export_declaration", "export_declaration.shipping_bill_no",
                                 "No shipping bill / export declaration number.",
                                 "File the shipping bill on ICEGATE and add its number to the pack.", "number", None))

    quote_ccy = str(documents.get("quote_currency") or "").strip().upper()
    inv_ccy = str(inv.get("currency") or "").strip().upper()
    if quote_ccy and inv_ccy and quote_ccy != inv_ccy:
        findings.append(_finding("currency_mismatch", "invoice.currency",
                                 f"Invoice is in {inv_ccy} but the agreed quote/LC currency is {quote_ccy}.",
                                 f"Issue the invoice in {quote_ccy} (banks reject LC documents in another currency).",
                                 quote_ccy, inv_ccy))

    shipping = documents.get("shipping") or {}
    if shipping.get("transshipment_port") and not shipping.get("through_bill_of_lading"):
        findings.append(_finding("consignment_gap", "shipping.transshipment_port",
                                 f"Goods are transshipped via {shipping['transshipment_port']} without a through bill "
                                 "of lading.",
                                 "Get a through bill of lading or customs proof that the goods stayed under customs "
                                 "control in the third country; otherwise the preference can be refused.",
                                 "through bill of lading", "none"))

    # One finding per (type, field), in document order.
    seen: set[tuple[str, str]] = set()
    return [f for f in findings if (f["type"], f["field"]) not in seen and not seen.add((f["type"], f["field"]))]
