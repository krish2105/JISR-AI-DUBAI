"""
pricing.py — Suite: invoice arithmetic invariants on every gold item list (deterministic).

For the gold items of every enquiry we price the quote and check, to the cent:
    line total = unit price x quantity (INR and AED)
    quote total = sum of line totals (INR and AED)
    AED unit price = round(INR unit price x FX)
    no negative or zero prices
pricing_invariant_pass_rate must be 1.0 (hard gate). No model is involved.
"""

from decimal import Decimal

from app.agents.state import LineItem
from app.profile import get_business_profile
from app.tools.pricing import price_lines, round_money
from eval.common import EvalContext, SuiteResult, load


def violations(quote: dict) -> list[str]:
    """List every broken invariant in one priced quote."""
    problems = []
    fx = Decimal(str(quote["fx_inr_to_aed"]))
    for ln in quote["lines"]:
        qty = Decimal(str(ln["quantity"]))
        if round_money(Decimal(str(ln["unit_price_aed"])) * qty) != Decimal(str(ln["total_aed"])):
            problems.append(f"AED line total {ln['description']}")
        if round_money(Decimal(str(ln["unit_price_inr"])) * qty) != Decimal(str(ln["total_inr"])):
            problems.append(f"INR line total {ln['description']}")
        if round_money(Decimal(str(ln["unit_price_inr"])) * fx) != Decimal(str(ln["unit_price_aed"])):
            problems.append(f"FX conversion {ln['description']}")
        if ln["unit_price_inr"] <= 0:
            problems.append(f"non-positive price {ln['description']}")
    for cur in ("aed", "inr"):
        total = sum(Decimal(str(ln[f"total_{cur}"])) for ln in quote["lines"])
        if round_money(total) != Decimal(str(quote[f"total_{cur}"])):
            problems.append(f"{cur.upper()} quote total")
    return problems


async def run(ctx: EvalContext) -> SuiteResult:
    """Price the gold items of every enquiry and check the invariants."""
    profile = get_business_profile()
    rows = load("enquiries", ctx)
    failures, passed = [], 0
    for row in rows:
        items = [LineItem(description=i["description_en"], quantity=i["quantity"], unit=i["unit"])
                 for i in row["labels"]["items"]]
        problems = violations(price_lines(items, profile, row["labels"]["incoterm"]))
        if problems:
            failures.append({"id": row["id"], "problems": problems})
        else:
            passed += 1
    n = len(rows) or 1
    return SuiteResult("pricing", len(rows), {"pricing_invariant_pass_rate": passed / n}, {}, failures)
