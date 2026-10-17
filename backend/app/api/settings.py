"""
settings.py — Organisation settings and onboarding (Phase 15): business profile, catalogue, autonomy.

    GET    /settings/profile                 profile + onboarding progress            (runs.read)
    PATCH  /settings/profile                 change sections (validated as a whole)   (settings.business)
    GET    /settings/catalogue               products                                 (runs.read)
    POST   /settings/catalogue               add a product                            (settings.business)
    PUT    /settings/catalogue/{name}        replace a product                        (settings.business)
    DELETE /settings/catalogue/{name}        remove a product                         (settings.business)
    POST   /settings/catalogue/import        CSV, merge or replace                    (settings.business)
    GET    /settings/catalogue/export        CSV download                             (runs.read)
    GET    /settings/autonomy                levels per action (default, current, allowed)   (governance.read)
    PUT    /settings/autonomy                set one action's level (only STRICTER)   (governance.policies.edit)
    POST   /settings/onboarding              record onboarding progress               (settings.business)

Every change is audited with what changed (keys, before/after fingerprints) and who changed it. Bank details,
payment instructions and payment status cannot be touched from here: they are NEVER actions in autonomy.yaml.
"""

import hashlib
import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field, ValidationError

from app.api.deps import require
from app.auth.service import Principal
from app.db.models import OrgProfile, OrgSettings
from app.db.session import session_scope
from app.governance.audit import append_audit
from app.governance.policy_engine import LEVEL_RANK, get_policy_engine
from app.profile import (
    BusinessProfile,
    CatalogueEntry,
    catalogue_from_csv,
    catalogue_to_csv,
    default_profile,
)

router = APIRouter(prefix="/settings", tags=["settings"])
ONBOARDING_STEPS = ["business", "products", "pricing", "logistics", "first_quote"]
EDITABLE_SECTIONS = {"seller_name", "home_currency", "quote_currency", "quote_validity_days", "default_margin_pct",
                     "min_margin_pct", "max_discount_pct", "volume_discounts", "fx_stub_inr_to_aed",
                     "default_unit_cost_inr", "default_kg", "default_cbm", "logistics", "roi"}


def _fingerprint(data: dict) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()[:16]


def _errors(exc: ValidationError) -> str:
    return "; ".join(f"{'.'.join(str(p) for p in e['loc']) or 'profile'}: {e['msg']}" for e in exc.errors()[:5])


async def _load(org_id: str) -> tuple[BusinessProfile, OrgProfile | None]:
    async with session_scope() as db:
        row = await db.get(OrgProfile, org_id)
    profile = BusinessProfile(**row.data) if row else default_profile()
    return profile, row


async def _save(principal: Principal, profile: BusinessProfile, action: str, details: dict) -> dict:
    """Store the validated profile and audit the change."""
    data = profile.model_dump(mode="json")
    async with session_scope() as db:
        row = await db.get(OrgProfile, principal.org_id)
        before = _fingerprint(row.data) if row else _fingerprint(default_profile().model_dump(mode="json"))
        if row is None:
            row = OrgProfile(org_id=principal.org_id, data=data, onboarding_step=len(ONBOARDING_STEPS),
                             onboarding_done=True)             # demo / sandbox: no onboarding needed
            db.add(row)
        row.data, row.updated_by, row.updated_at = data, principal.actor, datetime.now(UTC)
        await append_audit(db, org_id=principal.org_id, actor=principal.actor, action=action,
                           details={**details, "before": before, "after": _fingerprint(data)})
    return await _view(principal.org_id)


async def _view(org_id: str) -> dict:
    profile, row = await _load(org_id)
    return {"profile": profile.model_dump(mode="json"), "source": "organisation" if row else "demo",
            "onboarding": {"steps": ONBOARDING_STEPS, "step": row.onboarding_step if row else len(ONBOARDING_STEPS),
                           "done": row.onboarding_done if row else True}}


@router.get("/profile")
async def get_profile(principal: Principal = Depends(require("runs.read"))) -> dict:
    return await _view(principal.org_id)


@router.patch("/profile")
async def patch_profile(body: dict, principal: Principal = Depends(require("settings.business"))) -> dict:
    """Change one or more sections; the whole profile is re-validated before anything is stored."""
    unknown = set(body) - EDITABLE_SECTIONS
    if unknown:
        raise HTTPException(422, f"Not editable here: {', '.join(sorted(unknown))}. Use the catalogue endpoints for "
                                 "products.")
    profile, _ = await _load(principal.org_id)
    merged = profile.model_dump(mode="json")
    for key, value in body.items():
        merged[key] = {**merged[key], **value} if isinstance(merged.get(key), dict) and isinstance(value, dict) \
            else value
    try:
        updated = BusinessProfile(**merged)
    except ValidationError as exc:
        raise HTTPException(422, _errors(exc)) from exc
    return await _save(principal, updated, "settings.profile_updated", {"sections": sorted(body)})


# --- Catalogue ------------------------------------------------------------------------------------------------------

def _index(profile: BusinessProfile, name: str) -> int:
    for i, entry in enumerate(profile.catalogue):
        if entry.name.strip().lower() == name.strip().lower():
            return i
    raise HTTPException(404, "Product not found.")


async def _save_catalogue(principal: Principal, profile: BusinessProfile, catalogue: list[CatalogueEntry],
                          action: str, details: dict) -> dict:
    try:
        updated = BusinessProfile(**{**profile.model_dump(mode="json"),
                                     "catalogue": [e.model_dump(mode="json") for e in catalogue]})
    except ValidationError as exc:
        raise HTTPException(422, _errors(exc)) from exc
    return await _save(principal, updated, action, {**details, "products": len(catalogue)})


@router.get("/catalogue")
async def catalogue(principal: Principal = Depends(require("runs.read"))) -> list[dict]:
    profile, _ = await _load(principal.org_id)
    return [e.model_dump(mode="json") for e in profile.catalogue]


@router.post("/catalogue", status_code=201)
async def add_product(entry: CatalogueEntry, principal: Principal = Depends(require("settings.business"))) -> dict:
    profile, _ = await _load(principal.org_id)
    return await _save_catalogue(principal, profile, [*profile.catalogue, entry], "settings.product_added",
                                 {"product": entry.name})


@router.put("/catalogue/{name}")
async def replace_product(name: str, entry: CatalogueEntry,
                          principal: Principal = Depends(require("settings.business"))) -> dict:
    profile, _ = await _load(principal.org_id)
    items = list(profile.catalogue)
    items[_index(profile, name)] = entry
    return await _save_catalogue(principal, profile, items, "settings.product_changed",
                                 {"product": entry.name, "was": name})


@router.delete("/catalogue/{name}")
async def remove_product(name: str, principal: Principal = Depends(require("settings.business"))) -> dict:
    profile, _ = await _load(principal.org_id)
    items = list(profile.catalogue)
    removed = items.pop(_index(profile, name))
    return await _save_catalogue(principal, profile, items, "settings.product_removed", {"product": removed.name})


class ImportBody(BaseModel):
    csv: str = Field(max_length=1_000_000)
    mode: str = Field(default="merge", pattern="^(merge|replace)$")


@router.post("/catalogue/import")
async def import_catalogue(body: ImportBody, principal: Principal = Depends(require("settings.business"))) -> dict:
    """Merge (add new names, update existing) or replace the catalogue from CSV. Bad rows are reported, not stored."""
    entries, errors = catalogue_from_csv(body.csv)
    if not entries:
        raise HTTPException(422, "; ".join(errors) or "No products found in the file.")
    profile, _ = await _load(principal.org_id)
    if body.mode == "replace":
        items, added, updated = entries, len(entries), 0
    else:
        by_name = {e.name.strip().lower(): e for e in profile.catalogue}
        added = sum(1 for e in entries if e.name.strip().lower() not in by_name)
        updated = len(entries) - added
        by_name.update({e.name.strip().lower(): e for e in entries})
        items = list(by_name.values())
    view = await _save_catalogue(principal, profile, items, "settings.catalogue_imported",
                                 {"mode": body.mode, "added": added, "updated": updated, "row_errors": len(errors)})
    return {**view, "import": {"added": added, "updated": updated, "errors": errors}}


@router.get("/catalogue/export", response_class=PlainTextResponse)
async def export_catalogue(principal: Principal = Depends(require("runs.read"))) -> PlainTextResponse:
    profile, _ = await _load(principal.org_id)
    return PlainTextResponse(catalogue_to_csv(profile.catalogue), media_type="text/csv",
                             headers={"Content-Disposition": 'attachment; filename="jisr-catalogue.csv"'})


# --- Autonomy (bounded) ---------------------------------------------------------------------------------------------

async def _autonomy_view(org_id: str) -> list[dict]:
    engine = get_policy_engine()
    async with session_scope() as db:
        row = await db.get(OrgSettings, org_id)
    overrides = (row.autonomy or {}) if row else {}
    out = []
    for action, conf in engine.autonomy.items():
        default = engine.level_for(action)
        allowed = [lvl for lvl, rank in sorted(LEVEL_RANK.items(), key=lambda kv: kv[1]) if rank <= LEVEL_RANK[default]]
        out.append({"action_type": action, "default": default, "level": engine.effective_level(action, overrides),
                    "allowed": allowed, "locked": default == "NEVER", "why": conf.get("why", "")})
    return out


@router.get("/autonomy")
async def get_autonomy(principal: Principal = Depends(require("governance.read"))) -> list[dict]:
    return await _autonomy_view(principal.org_id)


class AutonomyBody(BaseModel):
    action_type: str = Field(max_length=60)
    level: str = Field(pattern="^(NEVER|L0|L1|L2|L3)$")


@router.put("/autonomy")
async def set_autonomy(body: AutonomyBody,
                       principal: Principal = Depends(require("governance.policies.edit"))) -> list[dict]:
    """Make an action stricter than the shipped default (or restore the default). Never looser."""
    engine = get_policy_engine()
    if body.action_type not in engine.autonomy:
        raise HTTPException(404, "Unknown action type.")
    default = engine.level_for(body.action_type)
    if LEVEL_RANK[body.level] > LEVEL_RANK[default]:
        raise HTTPException(422, f"'{body.action_type}' cannot be more autonomous than {default} (autonomy.yaml). "
                                 "Settings can only add caution.")
    async with session_scope() as db:
        row = await db.get(OrgSettings, principal.org_id)
        if row is None:
            row = OrgSettings(org_id=principal.org_id)
            db.add(row)
        overrides = dict(row.autonomy or {})
        before = overrides.get(body.action_type, default)
        if body.level == default:
            overrides.pop(body.action_type, None)
        else:
            overrides[body.action_type] = body.level
        row.autonomy = overrides
        await append_audit(db, org_id=principal.org_id, actor=principal.actor, action="settings.autonomy_changed",
                           details={"action_type": body.action_type, "before": before, "after": body.level})
    return await _autonomy_view(principal.org_id)


# --- Onboarding -----------------------------------------------------------------------------------------------------

class OnboardingBody(BaseModel):
    step: int = Field(ge=0, le=len(ONBOARDING_STEPS))
    done: bool = False


@router.post("/onboarding")
async def onboarding(body: OnboardingBody, principal: Principal = Depends(require("settings.business"))) -> dict:
    async with session_scope() as db:
        row = await db.get(OrgProfile, principal.org_id)
        if row is None:
            raise HTTPException(409, "This organisation uses the demo profile; there is nothing to set up.")
        row.onboarding_step = max(row.onboarding_step, body.step)
        if body.done:
            row.onboarding_done = True
            await append_audit(db, org_id=principal.org_id, actor=principal.actor, action="settings.onboarding_done",
                               details={"products": len(row.data.get("catalogue", []))})
    return await _view(principal.org_id)
