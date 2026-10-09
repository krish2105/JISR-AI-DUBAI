"""
test_quote_v2.py — Phase 4: deterministic parser, grounded hybrid extraction, FX provenance, full pricing,
pricing policy rules.

Parser cases are written for this file (not taken from the held-out sets).
"""

import httpx
import pytest

from app.agents.state import RFQ, LineItem, PendingAction
from app.config import get_settings
from app.governance.policy_engine import PolicyContext, PolicyEngine
from app.llm.fake_scripts import DEMO_SCRIPTS
from app.llm.router import FakeBackend, get_router
from app.profile import VolumeTier, get_business_profile
from app.tools import fx as fx_module
from app.tools.fx import fixed_rate, get_inr_to_aed
from app.tools.pricing import SCOPE, price_quote
from app.tools.rfq import extract_rfq, reconcile
from app.tools.rfq_rules import detect_language, find_deadline, find_items, numbers_in, parse_rfq
from eval.suites.pricing import violations

PROFILE = get_business_profile()
FX = fixed_rate(PROFILE.fx_stub_inr_to_aed)


# ---------- deterministic parser --------------------------------------------------------------


@pytest.mark.parametrize("text, expected", [
    ("Need 750 pcs copper bottles and 1,500 jute bags", [(750, "copper bottles"), (1500, "jute bags")]),
    ("pls quote 2.5k brass trays + qty 300 silk scarves", [(2500, "brass trays"), (300, "silk scarves")]),
    ("Linen napkins – 600 sets\nCeramic bowls – 240 pcs", [(600, "Linen napkins"), (240, "Ceramic bowls")]),
    ("we want three hundred marble coasters", [(300, "marble coasters")]),
    ("نحتاج ٣٥٠ قطعة من شالات صوف و 90 طقم أكواب", [(350, "شالات صوف"), (90, "أكواب")]),
])
def test_parser_items(text, expected):
    """Quantities in many formats, separators, dash-after style, number words and Arabic-Indic digits."""
    got = [(int(i.quantity), i.description) for i in find_items(text)]
    assert got == expected


def test_descriptions_are_clean_for_buyers():
    """Descriptions shown in quotes have no dangling brackets, units or trailing context."""
    items = find_items("We need 500 pcs brass diya lamps (medium size) and 200 pcs table runners for our Dubai shop.")
    assert [i.description for i in items] == ["brass diya lamps", "table runners"]


def test_parser_ignores_non_quantity_numbers():
    """Dates, durations, sizes, percentages and reference numbers are not items."""
    items = find_items("RFQ 2026/118: 400 cushion covers 18x18, 30% advance, deliver within 20 days, by 9 Dec")
    assert [(int(i.quantity), i.description) for i in items] == [(400, "cushion covers")]


def test_parser_fields():
    """Incoterm (any case), destination after a C/D term, deadline, language, buyer."""
    rfq = parse_rfq("hi, need 200 lamps cif dammam by 12 Jan pls\n— Gulf Lights Trading")
    assert (rfq.incoterm, rfq.buyer_country, rfq.deadline, rfq.language, rfq.buyer_name) == (
        "CIF", "SA", "12 January", "en", "Gulf Lights Trading")
    assert parse_rfq("200 lamps FOB Mundra").buyer_country == "unknown"          # Indian origin is not a destination
    assert find_deadline("التسليم قبل نهاية ديسمبر") == "end of December"
    assert detect_language("السلام عليكم, we need lamps for our shop please شكراً") == "mixed"


# ---------- grounded hybrid extraction -----------------------------------------------------------


def test_reconcile_drops_hallucinated_quantities_and_unwritten_incoterms():
    """Model output not supported by the text is corrected and reported."""
    text = "Need 400 brass lanterns, delivery to Dubai."
    llm = RFQ(buyer_name="X", buyer_country="AE", incoterm="CIF", language="en",
              items=[LineItem(description="brass lanterns", quantity=400),
                     LineItem(description="lantern stands", quantity=150)])      # 150 is not in the text
    final, corrections, dropped = reconcile(llm, parse_rfq(text), text)
    assert [i.quantity for i in final.items] == [400]
    assert dropped == [{"description": "lantern stands", "quantity": 150}]
    assert final.incoterm is None and any("CIF not written" in c for c in corrections)
    assert 400.0 in numbers_in(text)


async def test_extract_rfq_falls_back_to_rules_when_the_model_fails():
    """A broken model answer never blocks the quote: rules take over and the fallback is reported."""
    get_router.cache_clear()
    get_router().backends["fake"] = FakeBackend(dict(DEMO_SCRIPTS) | {"rfq_extract": {"nonsense": True}})
    rfq, reply, report = await extract_rfq("We need 120 pcs silk scarves CFR Doha")
    assert reply is None and report.source.startswith("rules") and report.error
    assert [i.quantity for i in rfq.items] == [120] and rfq.buyer_country == "QA"


# ---------- FX provenance ---------------------------------------------------------------------


async def test_fixed_fx_is_labelled():
    """The default provider is the configured demo rate, clearly labelled."""
    rate = await get_inr_to_aed(0.0379)
    assert rate.rate == 0.0379 and rate.source.startswith("Fixed demo rate") and not rate.stale


async def test_live_fx_uses_ecb_and_peg_then_falls_back_stale(monkeypatch):
    """Live: AED = 3.6725 / USDINR with date and source; on API failure, last good rate marked stale."""
    monkeypatch.setenv("FX_PROVIDER", "live")
    get_settings.cache_clear()
    fx_module._memory_cache.clear()

    class FakeClient:
        def __init__(self, *a, fail=False, **k):
            self.fail = fail

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url):
            if FakeClient.fail_next:
                raise httpx.ConnectError("down")
            return httpx.Response(200, json={"date": "2026-10-08", "rates": {"INR": 96.78}},
                                  request=httpx.Request("GET", url))

    FakeClient.fail_next = False
    monkeypatch.setattr(fx_module.httpx, "AsyncClient", FakeClient)
    live = await get_inr_to_aed(0.0379)
    assert live.rate == round(3.6725 / 96.78, 6) and live.rate_date == "2026-10-08"
    assert "ECB" in live.source and "3.6725" in live.source and not live.stale

    fx_module._memory_cache.clear()
    FakeClient.fail_next = True
    stale = await get_inr_to_aed(0.0379)
    assert stale.stale and stale.rate == live.rate


# ---------- pricing ---------------------------------------------------------------------------


@pytest.mark.parametrize("term", list(SCOPE))
def test_each_incoterm_has_exactly_its_charges_and_adds_up(term):
    """Every Incoterm: the right cost lines, and every total adds up to the cent."""
    quote = price_quote([LineItem(description="brass diya lamps", quantity=500)], PROFILE, FX, term, "AE")
    assert [c["code"] for c in quote["charges"]] == SCOPE[term]
    assert violations(quote, PROFILE.min_margin_pct) == []


def test_missing_incoterm_defaults_to_fob_and_is_flagged():
    quote = price_quote([LineItem(description="silk scarves", quantity=100)], PROFILE, FX, None, "AE")
    assert quote["incoterm"] == "FOB" and quote["incoterm_assumed"] and "incoterm_not_stated" in quote["pricing_flags"]


def test_volume_discount_and_margin_floor():
    """Tiers apply by quantity; the owner's floor is never crossed automatically."""
    big = price_quote([LineItem(description="pashmina shawls", quantity=3000)], PROFILE, FX, "EXW", "AE")
    assert big["lines"][0]["discount_pct"] == 5.0 and big["lines"][0]["effective_margin_pct"] >= PROFILE.min_margin_pct
    harsh = PROFILE.model_copy(update={"volume_discounts": [VolumeTier(min_qty=1, pct=15)], "max_discount_pct": 20})
    held = price_quote([LineItem(description="pashmina shawls", quantity=10)], harsh, FX, "EXW", "AE")
    assert "held_at_margin_floor" in held["pricing_flags"]
    assert held["lines"][0]["effective_margin_pct"] == pytest.approx(PROFILE.min_margin_pct, abs=0.01)


def test_unknown_item_is_priced_at_assumed_cost_and_flagged():
    quote = price_quote([LineItem(description="hand-knotted carpets", quantity=20)], PROFILE, FX, "CIF", "QA")
    assert "unpriced_item" in quote["pricing_flags"] and quote["lines"][0]["catalogue_match"] is False


# ---------- pricing policy rules (trigger and non-trigger) ------------------------------------

ENGINE = PolicyEngine.load()


def _send(flags: list[str]) -> PendingAction:
    return PendingAction(action_type="send_message", title="send", requested_by="test",
                         payload={"pricing_flags": flags})


@pytest.mark.parametrize("rule, flag, risk", [("P-MARGIN-001", "held_at_margin_floor", "high"),
                                              ("P-MARGIN-001", "target_below_floor", "high"),
                                              ("P-DISC-001", "discount_above_cap", "high"),
                                              ("P-PRICE-001", "unpriced_item", "medium"),
                                              ("P-PRICE-001", "fx_stale", "medium")])
def test_pricing_rules_trigger(rule, flag, risk):
    decision = ENGINE.evaluate(_send([flag]), PolicyContext())
    assert rule in decision.rule_ids and decision.risk == risk and decision.effect == "require_approval"


def test_pricing_rules_do_not_trigger_on_clean_quotes():
    decision = ENGINE.evaluate(_send([]), PolicyContext())
    assert decision.rule_ids == ["P-OUT-001"] and decision.risk == "medium"
