"""
demo.py — Demo helpers for the no-login /demo page.

    GET /demo/samples    the built-in sample enquiries (English, Arabic, hostile)
"""

from fastapi import APIRouter

from app.demo.samples import SAMPLES

router = APIRouter(prefix="/demo", tags=["demo"])


@router.get("/samples")
def samples() -> list[dict]:
    """List the demo samples (full text included so the page can preview them)."""
    return [s.model_dump() for s in SAMPLES]
