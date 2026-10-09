"""
doc_checker.py — Tool: cross-check an export document set for consistency (STUB until Phase 6).

Contract (frozen now so the evaluation can measure it from day one):
    check_document_set(documents) -> list of {"type": <mistake type>, "field": <path>, "severity": ..., "fix": ...}
Mistake types are those in eval/synth/docsets.py (hs_mismatch, qty_mismatch, ...).

Phase 2 returns no findings, so `make eval` honestly reports recall 0.0 for the checker.
Phase 6 implements the real deterministic checks.
"""

IS_STUB = True


def check_document_set(documents: dict) -> list[dict]:
    """Return consistency findings for one document set (stub: none yet)."""
    return []
