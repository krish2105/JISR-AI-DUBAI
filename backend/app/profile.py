"""
profile.py — Load the seller's business profile (catalogue, costs, pricing policy, logistics).

Why this file exists:
    Agents read pricing inputs from a configurable profile rather than from code, so the same system serves
    the pilot business, the demo company or any future customer. All numbers in the demo profile are
    estimates; the pilot replaces them with real costs and forwarder quotes.
"""

import re
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

DEFAULT_PROFILE_PATH = Path(__file__).parent / "demo" / "business_profile.yaml"


class CatalogueEntry(BaseModel):
    """A product family recognised by keywords, with cost and packed weight/volume per unit."""

    name: str
    keywords: list[str]                        # product nouns (decisive for matching)
    materials: list[str] = Field(default_factory=list)
    unit_cost_inr: float
    kg: float
    cbm: float
    hs_hint: str | None = None                 # a HINT only; HS codes are decided with cited sources (Phase 5)


class VolumeTier(BaseModel):
    """Discount applied to a line whose quantity reaches min_qty."""

    min_qty: float
    pct: float


class Logistics(BaseModel):
    """Shipment cost inputs (demo estimates)."""

    origin_port: str
    inland_freight_inr_per_kg: float
    export_clearance_inr: float
    ocean_freight_aed_per_cbm: dict[str, float]
    min_cbm: float
    insurance_pct: float
    destination_delivery_aed: float
    destination_clearance_aed: float
    import_duty_pct: float
    import_duty_source: str


class RoiAssumptions(BaseModel):
    """Inputs for the time-saved estimate. ASSUMPTIONS until the pilot measures the real baseline."""

    manual_minutes_per_quote: float = 45       # owner's estimate: reading, pricing, duty lookup, typing the reply
    review_minutes_per_quote: float = 5        # checking Jisr's draft before approving
    source: str = "founder estimate (replace with the pilot baseline interview)"


class BusinessProfile(BaseModel):
    """The seller's commercial settings and owner pricing policy."""

    seller_name: str
    home_currency: str = "INR"
    quote_currency: str = "AED"
    quote_validity_days: int = 15
    default_margin_pct: float
    min_margin_pct: float
    max_discount_pct: float
    volume_discounts: list[VolumeTier] = Field(default_factory=list)
    fx_stub_inr_to_aed: float
    catalogue: list[CatalogueEntry]
    default_unit_cost_inr: float
    default_kg: float
    default_cbm: float
    logistics: Logistics
    roi: RoiAssumptions = Field(default_factory=RoiAssumptions)

    def match(self, description: str) -> CatalogueEntry | None:
        """Best catalogue entry for a description: most product-noun hits, then material hits; None if no noun."""
        text = description.lower()

        def hits(words: list[str]) -> int:
            return sum(1 for w in words if re.search(rf"(?<![\w؀-ۿ]){re.escape(w.lower())}", text))

        scored = [(hits(e.keywords), hits(e.materials), e) for e in self.catalogue]
        scored = [s for s in scored if s[0] > 0]
        if not scored:
            return None
        return max(scored, key=lambda s: (s[0], s[1]))[2]

    def volume_discount(self, quantity: float) -> float:
        """Discount % for a line quantity (highest tier reached)."""
        reached = [t.pct for t in self.volume_discounts if quantity >= t.min_qty]
        return max(reached) if reached else 0.0


@lru_cache
def get_business_profile(path: Path = DEFAULT_PROFILE_PATH) -> BusinessProfile:
    """Load and cache the profile."""
    return BusinessProfile(**yaml.safe_load(path.read_text(encoding="utf-8")))
