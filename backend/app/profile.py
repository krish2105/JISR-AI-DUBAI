"""
profile.py — Load the seller's business profile (catalogue, costs, pricing policy, logistics).

Why this file exists:
    Agents read pricing inputs from a configurable profile rather than from code, so the same system serves
    the pilot business, the demo company or any future customer. All numbers in the demo profile are
    estimates; the pilot replaces them with real costs and forwarder quotes.
"""

import csv
import io
import re
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

DEFAULT_PROFILE_PATH = Path(__file__).parent / "demo" / "business_profile.yaml"


class CatalogueEntry(BaseModel):
    """A product family recognised by keywords, with cost and packed weight/volume per unit."""

    name: str = Field(min_length=1, max_length=120)
    keywords: list[str] = Field(min_length=1)  # product nouns (decisive for matching)
    materials: list[str] = Field(default_factory=list)
    unit_cost_inr: float = Field(gt=0)
    kg: float = Field(gt=0)
    cbm: float = Field(gt=0)
    hs_hint: str | None = None                 # a HINT only; HS codes are decided with cited sources (Phase 5)

    @field_validator("keywords", "materials")
    @classmethod
    def _clean_words(cls, words: list[str]) -> list[str]:
        cleaned = [w.strip() for w in words if w and w.strip()]
        return list(dict.fromkeys(cleaned))[:30]

    @field_validator("hs_hint")
    @classmethod
    def _hs_digits(cls, value: str | None) -> str | None:
        if value in (None, ""):
            return None
        digits = re.sub(r"\D", "", value)
        if not 4 <= len(digits) <= 10:
            raise ValueError("HS hint must have 4 to 10 digits")
        return digits


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

    seller_name: str = Field(min_length=1, max_length=160)
    home_currency: str = "INR"
    quote_currency: str = "AED"
    quote_validity_days: int = Field(default=15, ge=1, le=120)
    default_margin_pct: float = Field(ge=0, le=300)
    min_margin_pct: float = Field(ge=0, le=300)
    max_discount_pct: float = Field(ge=0, le=90)
    volume_discounts: list[VolumeTier] = Field(default_factory=list)
    fx_stub_inr_to_aed: float
    catalogue: list[CatalogueEntry]
    default_unit_cost_inr: float
    default_kg: float
    default_cbm: float
    logistics: Logistics
    roi: RoiAssumptions = Field(default_factory=RoiAssumptions)

    @model_validator(mode="after")
    def _consistent(self) -> "BusinessProfile":
        if self.min_margin_pct > self.default_margin_pct:
            raise ValueError("The minimum margin cannot be above the default margin.")
        names = [e.name.strip().lower() for e in self.catalogue]
        if len(names) != len(set(names)):
            raise ValueError("Each catalogue product needs a unique name.")
        return self

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
def default_profile(path: Path = DEFAULT_PROFILE_PATH) -> BusinessProfile:
    """The synthetic demo profile (demo organisation, sandboxes, tests). Cached."""
    return BusinessProfile(**yaml.safe_load(path.read_text(encoding="utf-8")))


# The profile of the organisation whose work is running now (set per run, per collections check, per API call).
_ACTIVE: ContextVar[BusinessProfile | None] = ContextVar("active_business_profile", default=None)


def get_business_profile() -> BusinessProfile:
    """The active organisation's profile (Phase 15), or the demo profile when none is active."""
    return _ACTIVE.get() or default_profile()


get_business_profile.cache_clear = default_profile.cache_clear      # type: ignore[attr-defined]  (tests)


@contextmanager
def using_profile(profile: BusinessProfile):
    """Make `profile` the active one inside the block (agents call get_business_profile() unchanged)."""
    token = _ACTIVE.set(profile)
    try:
        yield profile
    finally:
        _ACTIVE.reset(token)


def blank_profile(seller_name: str) -> BusinessProfile:
    """A new organisation's starting point: its name, the demo's pricing defaults and logistics ESTIMATES (to be
    replaced in onboarding) and an empty catalogue (every line is then priced at the default cost and flagged)."""
    demo = default_profile()
    return demo.model_copy(update={"seller_name": seller_name, "catalogue": []}, deep=True)


async def load_org_profile(org_id: str) -> BusinessProfile:
    """The organisation's saved profile, or the demo profile if it has none (demo, sandboxes)."""
    from app.db.models import OrgProfile
    from app.db.session import session_scope

    async with session_scope() as db:
        row = await db.get(OrgProfile, org_id)
    return BusinessProfile(**row.data) if row is not None else default_profile()


CSV_FIELDS = ["name", "keywords", "materials", "unit_cost_inr", "kg", "cbm", "hs_hint"]


def catalogue_to_csv(entries: list[CatalogueEntry]) -> str:
    """Catalogue as CSV (keywords and materials joined with '|')."""
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=CSV_FIELDS)
    writer.writeheader()
    for e in entries:
        writer.writerow({**e.model_dump(), "keywords": "|".join(e.keywords), "materials": "|".join(e.materials),
                         "hs_hint": e.hs_hint or ""})
    return out.getvalue()


def catalogue_from_csv(text: str, max_rows: int = 2000) -> tuple[list[CatalogueEntry], list[str]]:
    """Parse a catalogue CSV. Returns (valid entries, row errors). Keywords default to the product name."""
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    missing = {"name", "unit_cost_inr", "kg", "cbm"} - set(reader.fieldnames or [])
    if missing:
        return [], [f"Missing columns: {', '.join(sorted(missing))}. Expected: {', '.join(CSV_FIELDS)}."]
    entries, errors = [], []
    for i, row in enumerate(reader, start=2):
        if i - 1 > max_rows:
            errors.append(f"Only the first {max_rows} rows were read.")
            break
        split = lambda v: [w for w in re.split(r"[|;]", v or "") if w.strip()]  # noqa: E731
        try:
            name = (row.get("name") or "").strip()
            entries.append(CatalogueEntry(
                name=name, keywords=split(row.get("keywords")) or [name.lower()], materials=split(row.get("materials")),
                unit_cost_inr=float(row.get("unit_cost_inr") or 0), kg=float(row.get("kg") or 0),
                cbm=float(row.get("cbm") or 0), hs_hint=(row.get("hs_hint") or None)))
        except (ValueError, TypeError) as exc:
            errors.append(f"Row {i}: {str(exc).splitlines()[0]}")
    return entries, errors
