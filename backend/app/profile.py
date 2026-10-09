"""
profile.py — Load the seller's business profile (products, costs, margin, currencies).

Why this file exists:
    Agents read pricing inputs from a configurable profile rather than from code, so the
    same system serves the pilot business, the demo company, or any future customer.
"""

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel

DEFAULT_PROFILE_PATH = Path(__file__).parent / "demo" / "business_profile.yaml"


class CatalogueEntry(BaseModel):
    """A product family recognised by keywords, with its unit cost."""

    keywords: list[str]
    unit_cost_inr: float
    hs_hint: str | None = None   # a HINT only; HS codes are decided with cited sources (Phase 5)


class BusinessProfile(BaseModel):
    """The seller's commercial settings."""

    seller_name: str
    home_currency: str = "INR"
    quote_currency: str = "AED"
    default_margin_pct: float
    quote_validity_days: int = 15
    fx_stub_inr_to_aed: float
    catalogue: list[CatalogueEntry]
    default_unit_cost_inr: float

    def match(self, description: str) -> CatalogueEntry | None:
        """Return the first catalogue entry whose keyword appears in the description."""
        text = description.lower()
        for entry in self.catalogue:
            if any(k.lower() in text for k in entry.keywords):
                return entry
        return None


@lru_cache
def get_business_profile(path: Path = DEFAULT_PROFILE_PATH) -> BusinessProfile:
    """Load and cache the profile."""
    return BusinessProfile(**yaml.safe_load(path.read_text(encoding="utf-8")))
