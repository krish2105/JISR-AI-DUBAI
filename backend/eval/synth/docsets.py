"""
docsets.py — 40 synthetic export document sets, about half with seeded mistakes.

Why this file exists:
    The Document Consistency Checker (Phase 6) must catch the mistakes that delay shipments.
    We generate complete, internally consistent sets (invoice, packing list, certificate of origin,
    shipping details, export declaration), then deliberately plant 1-2 known mistakes in half
    of them. The planted mistakes ARE the gold labels: recall and false-positive rate are exact.

Mistake types (one field each):
    hs_mismatch                 HS code differs between invoice and packing list or certificate of origin
    qty_mismatch                quantity differs between invoice and packing list
    line_total_mismatch         invoice line amount != quantity x unit price
    invoice_total_mismatch      invoice total != sum of line amounts
    missing_coo                 no certificate of origin although CEPA preference is claimed
    missing_export_declaration  no shipping bill / export declaration number
    currency_mismatch           invoice currency differs from the quote/LC currency
    weight_inconsistency        net weight greater than gross weight on the packing list
    consignment_gap             goods transshipped via a third country with no through bill of lading

HS codes: 8-digit codes that exist in the Dubai Customs tariff master (old-code column). They are
consistent TEST FIXTURES for cross-document checks, not classification advice.

v4 (Phase 6): 20 more sets (doc_041-060) carry BENIGN FORMAT NOISE applied after planting: dotted HS codes,
6-digit codes on the certificate, quantities like "500 pcs", amounts like "52,840.00", lower-case currency.
Clean noisy sets must give no findings (false alarms on formatting are what make checkers unusable).
"""

import copy
import random
import re

# (description, HS code from the tariff master, unit price AED range, net kg per unit)
GOODS = [
    ("Wooden statuettes and ornaments", "44201900", (18, 60), 0.6),
    ("Shawls of wool, not knitted", "62142010", (35, 120), 0.25),
    ("Printed cotton bed linen", "63022100", (25, 80), 0.9),
    ("Other articles of copper (brass trays)", "74192090", (20, 75), 1.1),
    ("Lamps and lighting fittings", "94051900", (22, 95), 0.8),
]
SELLERS = ["Jaipur Heritage Crafts (demo)", "Pink City Exports (demo)", "Amer Artisans Pvt Ltd (demo)"]
BUYERS = ["Bayt Al Hadaya Trading LLC", "Desert Rose Gifts FZE", "Gulf Star General Trading", "Marina Home Decor LLC"]
PORTS_LOADING = ["Mundra", "Nhava Sheva"]
PORTS_DISCHARGE = ["Jebel Ali", "Khalifa Port", "Sharjah"]
MISTAKES = ["hs_mismatch", "qty_mismatch", "line_total_mismatch", "invoice_total_mismatch", "missing_coo",
            "missing_export_declaration", "currency_mismatch", "weight_inconsistency", "consignment_gap"]


def _money(x: float) -> float:
    """Round to cents."""
    return round(x + 1e-9, 2)


def _clean_set(rng: random.Random, idx: int) -> dict:
    """A fully consistent document set."""
    lines, packing = [], []
    for desc, hs, (lo, hi), kg in rng.sample(GOODS, rng.choice([1, 2, 3])):
        qty = rng.choice([50, 100, 150, 200, 300, 500, 800])
        price = _money(rng.uniform(lo, hi))
        lines.append({"description": desc, "hs_code": hs, "quantity": qty, "unit_price": price,
                      "amount": _money(qty * price)})
        net = _money(qty * kg)
        packing.append({"description": desc, "hs_code": hs, "quantity": qty, "packages": max(1, qty // 50),
                        "net_kg": net, "gross_kg": _money(net * 1.12)})
    total = _money(sum(ln["amount"] for ln in lines))
    port_l, port_d = rng.choice(PORTS_LOADING), rng.choice(PORTS_DISCHARGE)
    return {
        "invoice": {"invoice_no": f"INV-{2600 + idx}", "seller": rng.choice(SELLERS), "buyer": rng.choice(BUYERS),
                    "currency": "AED", "incoterm": rng.choice(["CIF", "CFR", "FOB"]), "lines": lines, "total": total},
        "quote_currency": "AED",
        "packing_list": {"lines": packing},
        "certificate_of_origin": {"present": True, "certificate_no": f"CEPA-IN-{90000 + idx}",
                                  "hs_codes": [ln["hs_code"] for ln in lines], "origin_criterion": "PSR (Annex 3B)"},
        "cepa_preference_claimed": True,
        "shipping": {"port_of_loading": port_l, "port_of_discharge": port_d, "transshipment_port": None,
                     "through_bill_of_lading": True},
        "export_declaration": {"shipping_bill_no": f"SB{rng.randint(1000000, 9999999)}"},
    }


def _plant(rng: random.Random, ds: dict, mistake: str) -> dict:
    """Apply one mistake in place; return the gold issue record."""
    inv, pl = ds["invoice"], ds["packing_list"]
    i = rng.randrange(len(inv["lines"]))
    if mistake == "hs_mismatch":
        wrong = "44209090" if not inv["lines"][i]["hs_code"].startswith("4420") else "94052100"
        target = rng.choice(["packing_list", "certificate_of_origin"])
        if target == "packing_list":
            pl["lines"][i]["hs_code"] = wrong
        else:
            ds["certificate_of_origin"]["hs_codes"][i] = wrong
        return {"type": mistake, "field": f"{target}.line[{i}].hs_code"}
    if mistake == "qty_mismatch":
        pl["lines"][i]["quantity"] += rng.choice([-20, 10, 50])
        return {"type": mistake, "field": f"packing_list.line[{i}].quantity"}
    if mistake == "line_total_mismatch":
        inv["lines"][i]["amount"] = _money(inv["lines"][i]["amount"] + rng.choice([-50, 12.5, 100]))
        inv["total"] = _money(sum(ln["amount"] for ln in inv["lines"]))       # total stays consistent with lines
        return {"type": mistake, "field": f"invoice.line[{i}].amount"}
    if mistake == "invoice_total_mismatch":
        inv["total"] = _money(inv["total"] + rng.choice([-100, 250, 1000]))
        return {"type": mistake, "field": "invoice.total"}
    if mistake == "missing_coo":
        ds["certificate_of_origin"] = {"present": False}
        return {"type": mistake, "field": "certificate_of_origin"}
    if mistake == "missing_export_declaration":
        ds["export_declaration"] = {"shipping_bill_no": None}
        return {"type": mistake, "field": "export_declaration.shipping_bill_no"}
    if mistake == "currency_mismatch":
        inv["currency"] = rng.choice(["USD", "INR"])
        return {"type": mistake, "field": "invoice.currency"}
    if mistake == "weight_inconsistency":
        pl["lines"][i]["net_kg"] = _money(pl["lines"][i]["gross_kg"] * 1.2)
        return {"type": mistake, "field": f"packing_list.line[{i}].net_kg"}
    if mistake == "consignment_gap":
        ds["shipping"].update(transshipment_port=rng.choice(["Salalah", "Colombo"]), through_bill_of_lading=False)
        return {"type": mistake, "field": "shipping.transshipment_port"}
    raise ValueError(mistake)


def _dotted(code: str) -> str:
    """'62142010' -> '6214.20.10' (how codes are often printed)."""
    return f"{code[:4]}.{code[4:6]}.{code[6:]}" if len(code) == 8 else code


def _format_noise(rng: random.Random, ds: dict, issues: list[dict]) -> None:
    """Harmless formatting differences, as real documents from different systems have them, including a different
    line ORDER on the packing list and the certificate (gold field indices are remapped to the new order)."""
    inv, pl = ds["invoice"], ds["packing_list"]
    order = list(range(len(pl["lines"])))
    rng.shuffle(order)                                   # new position j holds old line order[j]
    pl["lines"] = [pl["lines"][k] for k in order]
    coo_codes = ds["certificate_of_origin"].get("hs_codes")
    if coo_codes:
        ds["certificate_of_origin"]["hs_codes"] = [coo_codes[k] for k in order]
    new_pos = {old: new for new, old in enumerate(order)}
    for issue in issues:
        m = re.match(r"(packing_list|certificate_of_origin)\.line\[(\d+)\](.*)", issue["field"])
        if m:
            issue["field"] = f"{m.group(1)}.line[{new_pos[int(m.group(2))]}]{m.group(3)}"
    for ln in inv["lines"]:
        ln["hs_code"] = _dotted(ln["hs_code"])
        ln["amount"] = f"{ln['amount']:,.2f}"
    inv["total"] = f"AED {inv['total']:,.2f}"
    ccy = inv["currency"]
    inv["currency"] = rng.choice([ccy.lower(), f"{ccy} ", ccy.title()])     # same currency, different spelling
    for ln in pl["lines"]:
        ln["quantity"] = f"{ln['quantity']} pcs"
        ln["net_kg"] = f"{ln['net_kg']} kg"
    coo = ds["certificate_of_origin"]
    if coo.get("present"):
        coo["hs_codes"] = [c[:6] if rng.random() < 0.5 else _dotted(c) for c in coo["hs_codes"]]


def generate_docsets(seed: int = 20261009) -> list[dict]:
    """20 clean sets + 20 sets with 1-2 planted mistakes (every mistake type appears at least twice)."""
    rng = random.Random(seed + 1)
    rows = []
    # Cycle through mistake types so each appears at least twice across the 20 faulty sets.
    cycle = MISTAKES * 3
    for idx in range(1, 41):
        ds = _clean_set(rng, idx)
        issues = []
        if idx % 2 == 0:                                   # even ids carry mistakes
            first = cycle[(idx // 2) - 1]
            chosen = [first]
            if rng.random() < 0.35:
                second = rng.choice([m for m in MISTAKES if m != first])
                chosen.append(second)
            for m in chosen:
                issues.append(_plant(rng, ds, m))
        rows.append({
            "id": f"doc_{idx:03d}",
            "split": "test" if idx > 32 else ("dev" if idx > 24 else "train"),
            "documents": copy.deepcopy(ds),
            "labels": {"issues": issues, "clean": not issues},
        })
    noise_rng = random.Random(seed + 2)
    for idx in range(41, 61):                            # v4: format-noise sets
        ds = _clean_set(noise_rng, idx)
        issues = [_plant(noise_rng, ds, MISTAKES[(idx // 2) % len(MISTAKES)])] if idx % 2 == 0 else []
        _format_noise(noise_rng, ds, issues)
        rows.append({
            "id": f"doc_{idx:03d}",
            "split": "test" if idx > 52 else ("dev" if idx > 46 else "train"),
            "documents": copy.deepcopy(ds),
            "labels": {"issues": issues, "clean": not issues, "format_noise": True},
        })
    return rows
