"""
kb.py — Knowledge-base API for the HS-tariff tree explorer (2D list and 3D tree).

    GET /kb/chapters                 the 97 tariff chapters with their CEPA origin rule
    GET /kb/tree?chapter=94          one chapter: headings -> subheadings -> tariff lines (EN + AR, duty, origin rule)
    GET /kb/locate?q=brass+diya+lamps  where a product sits: top-3 headings and the path chapter > heading > line,
                                     with the cited tariff text and Annex 3B rule (what the duty agent does)

Every node carries its official source (Dubai Customs tariff master; CEPA Final Agreement Annex 3B with page label).
"""

import asyncio

from fastapi import APIRouter, HTTPException

from app.rag.index import index_exists
from app.rag.ingest_psr import rule_for

router = APIRouter(prefix="/kb", tags=["knowledge base"])


def _kb():
    if not index_exists():
        raise HTTPException(503, "Knowledge base not built on this server (make kb)")
    from app.rag.retriever import get_retriever

    return get_retriever()


def _rule(code: str, kb) -> dict | None:
    r = rule_for(code, kb.rules)
    return {"rule_id": r.rule_id, "text": r.rule_text, "scope": r.scope_text, "page_label": r.page_label,
            "is_ex": r.is_ex} if r else None


@router.get("/chapters")
async def chapters() -> list[dict]:
    """All chapters with their title and CEPA origin rule."""
    kb = _kb().kb
    out = []
    for code, node in sorted(kb.tariff.items()):
        if node.level == "chapter":
            rule = next((r for r in kb.rules if not r.codes and int(code) in r.chapters), None)
            out.append({"code": code, "title": node.desc_en, "title_ar": node.desc_ar,
                        "rule": rule.rule_text if rule else None})
    return out


@router.get("/tree")
async def tree(chapter: str, max_lines: int = 6) -> dict:
    """One chapter as a tree (lines capped per subheading so the 3D view stays readable)."""
    kb = _kb().kb
    chapter = chapter.zfill(2)[:2]
    root = kb.tariff.get(chapter)
    if root is None:
        raise HTTPException(404, "Unknown chapter")
    children: dict[str, list] = {}
    for node in kb.tariff.values():
        if node.parent:
            children.setdefault(node.parent, []).append(node)

    def build(node, depth: int) -> dict:
        kids = sorted(children.get(node.code, []), key=lambda n: n.code)
        if node.level in ("subheading", "national"):
            kids = kids[:max_lines]
        return {"code": node.code, "level": node.level, "desc_en": node.desc_en[:160], "desc_ar": node.desc_ar[:160],
                "duty_pct": node.duty_pct, "rule": _rule(node.code, kb) if node.level == "heading" else None,
                "children": [build(k, depth + 1) for k in kids] if depth < 4 else [],
                "more": max(0, len(children.get(node.code, [])) - len(kids))}

    return {**build(root, 0), "source": {"tariff": "Dubai Customs Integrated Customs Tariff (12-digit master)",
                                         "rules": "India-UAE CEPA Final Agreement, Annex 3B (UAE MoET, 2022-03-28)"}}


@router.get("/locate")
async def locate(q: str) -> dict:
    """Where goods sit in the tariff: the path the duty agent takes, with confidence and the cited texts."""
    from app.rag.retriever import classify_hs

    retriever = _kb()
    cands = await asyncio.to_thread(classify_hs, retriever, q[:300])
    kb = retriever.kb

    def path(line: str) -> list[str]:
        out, code = [], line
        while code:
            out.append(code)
            node = kb.tariff.get(code)
            code = node.parent if node else None
        return list(reversed(out))

    return {"query": q, "candidates": [{"heading": c.heading, "line": c.best_line, "desc": c.best_line_desc,
                                        "confidence": c.confidence, "duty_pct": c.duty_pct, "path": path(c.best_line),
                                        "rule": _rule(c.best_line, kb)} for c in cands],
            "needs_human_check": True}
