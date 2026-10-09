"""
pricing.py — Suite: invoice arithmetic and pricing-policy invariants on every gold item list (deterministic).

For the gold items, Incoterm and destination of every enquiry we price a full quote (goods + Incoterm charges,
fixed demo FX) and check, to the cent:
    line total = unit price x quantity (INR and AED); AED unit = round(INR unit x FX)
    goods total = sum of lines; charges total = sum of charges; quote total = goods + charges (INR and AED)
    the charge lines are exactly those the Incoterm puts on the seller (EXW none ... DDP everything)
    no line is below the owner's minimum margin; no negative or zero prices
pricing_invariant_pass_rate must be 1.0 (hard gate). No model is involved.
"""

from decimal import Decimal

from app.agents.state import LineItem
from app.profile import get_business_profile
from app.tools.fx import fixed_rate
from app.tools.pricing import DEFAULT_INCOTERM, SCOPE, price_quote, round_money
from eval.common import EvalContext, SuiteResult, load


def _d(x: float) -> Decimal:
    return Decimal(str(x))


def violations(quote: dict, min_margin_pct: float | None = None) -> list[str]:
    """List every broken invariant in one priced quote."""
    problems = []
    fx = _d(quote["fx_inr_to_aed"])
    for ln in quote["lines"]:
        qty = _d(ln["quantity"])
        if round_money(_d(ln["unit_price_aed"]) * qty) != _d(ln["total_aed"]):
            problems.append(f"AED line total {ln['description']}")
        if round_money(_d(ln["unit_price_inr"]) * qty) != _d(ln["total_inr"]):
            problems.append(f"INR line total {ln['description']}")
        if round_money(_d(ln["unit_price_inr"]) * fx) != _d(ln["unit_price_aed"]):
            problems.append(f"FX conversion {ln['description']}")
        if ln["unit_price_inr"] <= 0:
            problems.append(f"non-positive price {ln['description']}")
        if min_margin_pct is not None and ln.get("effective_margin_pct", 100) < min_margin_pct - 0.01:
            problems.append(f"below margin floor {ln['description']}")
    for cur in ("aed", "inr"):
        goods = sum((_d(ln[f"total_{cur}"]) for ln in quote["lines"]), Decimal(0))
        charges = sum((_d(c[f"total_{cur}"]) for c in quote.get("charges", [])), Decimal(0))
        if "goods_total_aed" in quote:
            if round_money(goods) != _d(quote[f"goods_total_{cur}"]):
                problems.append(f"{cur.upper()} goods total")
            if round_money(charges) != _d(quote[f"charges_total_{cur}"]):
                problems.append(f"{cur.upper()} charges total")
        if round_money(goods + charges) != _d(quote[f"total_{cur}"]):
            problems.append(f"{cur.upper()} quote total")
    if "charges" in quote:
        expected = SCOPE.get(quote["incoterm"], SCOPE[DEFAULT_INCOTERM])
        if [c["code"] for c in quote["charges"]] != expected:
            problems.append(f"charges do not match {quote['incoterm']} scope")
    return problems


async def run(ctx: EvalContext) -> SuiteResult:
    """Price the gold items of every enquiry and check the invariants."""
    profile = get_business_profile()
    fx = fixed_rate(profile.fx_stub_inr_to_aed)
    rows = load("enquiries", ctx)
    failures, passed = [], 0
    by_term: dict[str, int] = {}
    for row in rows:
        labels = row["labels"]
        items = [LineItem(description=i["description_en"], quantity=i["quantity"], unit=i["unit"])
                 for i in labels["items"]]
        quote = price_quote(items, profile, fx, labels["incoterm"], labels["buyer_country"])
        by_term[quote["incoterm"]] = by_term.get(quote["incoterm"], 0) + 1
        problems = violations(quote, profile.min_margin_pct)
        if problems:
            failures.append({"id": row["id"], "problems": problems})
        else:
            passed += 1
    n = len(rows) or 1
    return SuiteResult("pricing", len(rows), {"pricing_invariant_pass_rate": passed / n}, {}, failures,
                       notes=[f"Quotes per Incoterm: {dict(sorted(by_term.items()))}"])
