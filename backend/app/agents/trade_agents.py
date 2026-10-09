"""
trade_agents.py — The CEPA Duty agent and the Docs agent (Phase 5), built on the cited knowledge base.

Why this file exists:
    These two agents turn retrieval into decisions a trade officer can check:

    Duty agent (per quote line)
        HS top-3 candidates with confidence (tariff tree) -> published UAE MFN duty (cited tariff line)
        -> CEPA Annex 3B product-specific rule (cited, page label) + the FOB/Ex-Works basis (Rule 1)
        -> the origin EVIDENCE the exporter must hold (derived from the rule's components)
        -> "up to AED X" duty that would be saved IF the CEPA preferential rate is 0%. The line-level preferential
           rate is "needs human check" because the UAE tariff schedule (Annex 2B) is not in the knowledge base.
        Every claim goes through the same code grounding check as agentic RAG (numbers verbatim in cited text).
    Docs agent
        HS candidates per line (from the duty analysis) + the document pack, each requirement cited to the
        Dubai Customs services guide, the DGFT CEPA certificate-of-origin notice, CEPA Articles 3.12-3.20 and ICEGATE.

    If the knowledge base is not built (CI, fresh checkout) both agents say so and flag "needs human check".
"""

import asyncio
import re
from decimal import Decimal

from app.profile import get_business_profile
from app.rag.agentic import HS_MIN_RELEVANCE, Claim, ground
from app.rag.citations import find_article, first_chunk_of, resolve
from app.rag.index import index_exists
from app.rag.ingest_psr import rule_for
from app.rag.retriever import classify_hs, get_retriever


def _evidence_for(components: dict) -> list[str]:
    """Plain-language origin evidence implied by a rule's components."""
    needs = []
    if components.get("wo"):
        needs.append("Proof the product is wholly obtained or produced in India (Article 3.3).")
    if components.get("cc"):
        needs.append("Bill of materials showing every non-originating material is from a different HS chapter.")
    if components.get("cth"):
        needs.append("Bill of materials showing every non-originating material is classified in a different "
                     "4-digit heading than the product.")
    if components.get("ctsh"):
        needs.append("Bill of materials showing every non-originating material is classified in a different "
                     "6-digit subheading than the product.")
    if components.get("va_pct"):
        va = components["va_pct"]
        needs.append(f"Cost sheet showing value addition of at least {va}% of the FOB value "
                     f"(or {va - 5}% of the Ex-Works price).")
    if components.get("melt"):
        needs.append("Proof of the melting/casting process in India, as the rule requires.")
    return needs


def analyse_duty_sync(rfq, quote: dict) -> dict:
    """CPU-bound duty analysis for all quote lines (runs in a worker thread)."""
    retriever = get_retriever()
    kb = retriever.kb
    profile = get_business_profile()
    lines_out, retrieved = [], set()
    total_mfn = Decimal(0)
    goods_total = Decimal(str(quote.get("goods_total_aed") or quote.get("total_aed") or 0)) or Decimal(1)
    cif_charges = sum(Decimal(str(c["total_aed"])) for c in quote.get("charges", [])
                      if c["code"] in ("inland", "export", "freight", "insurance"))
    art_transport, art_proof = find_article(kb, "3.12"), find_article(kb, "3.13")
    dgft = first_chunk_of(kb, "dgft_trade_notice_05_2022_23_india_uae_cepa_ecoo")
    for item, line in zip(rfq.items, quote["lines"], strict=False):
        entry = profile.match(item.description)
        hint = entry.hs_hint if entry and entry.hs_hint else None
        cands = classify_hs(retriever, item.description, prior_heading=hint)
        if not cands:
            lines_out.append({"description": item.description, "status": "no_candidate", "needs_human_check": True})
            continue
        top = cands[0]
        for c in cands:
            retrieved.update(c.chunk_ids)
        rule = rule_for(top.best_line, kb.rules)
        claims = [Claim(text=f"Most likely HS heading {top.heading}, tariff line {top.best_line}: {top.best_line_desc}",
                        citations=[f"hs:{top.heading}", f"hs:{top.best_line}"])]
        if top.duty_pct not in (None, "", "None"):
            claims.append(Claim(text=f"Published UAE customs duty for HS {top.best_line} is {top.duty_pct}% "
                                     "(before any CEPA preference).", citations=[f"hs:{top.best_line}"]))
        if rule:
            retrieved.update({rule.rule_id, "psr_rule1"})
            claims.append(Claim(text=f"CEPA product specific rule ({rule.scope_text}): {rule.rule_text}.",
                                citations=[rule.rule_id]))
            if rule.components.get("va_pct"):
                claims.append(Claim(text="Value addition is measured on an FOB basis; it is 5 percentage points "
                                         "lower on an Ex Works basis.", citations=["psr_rule1"]))
        kept, removed = ground(claims, retriever, retrieved | {f"hs:{top.heading}", f"hs:{top.best_line}"})
        weak_match = top.mode == "rrf_rerank" and top.best_score < HS_MIN_RELEVANCE    # no tariff line clearly fits
        # Indicative MFN duty on this line's CIF value (goods + its value share of pre-arrival charges).
        line_aed = Decimal(str(line["total_aed"]))
        cif = line_aed + cif_charges * line_aed / goods_total
        duty_pct = Decimal(top.duty_pct) if (top.duty_pct or "").replace(".", "", 1).isdigit() else None
        mfn = (cif * duty_pct / 100).quantize(Decimal("0.01")) if duty_pct is not None else None
        if mfn is not None:
            total_mfn += mfn
        lines_out.append({
            "description": item.description,
            "hs_candidates": [c.model_dump() for c in cands],
            "hs_confidence": top.confidence,
            "catalogue_hint": hint,
            "hint_agrees": (top.heading == hint) if hint else None,
            "rule": {"rule_id": rule.rule_id, "scope": rule.scope_text, "text": rule.rule_text,
                     "page_label": rule.page_label, "is_ex": rule.is_ex} if rule else None,
            "evidence_needed": _evidence_for(rule.components) if rule else [],
            "mfn_duty_pct": top.duty_pct,
            "cif_value_aed": float(cif.quantize(Decimal("0.01"))),
            "mfn_duty_aed": float(mfn) if mfn is not None else None,
            "claims": [c.model_dump() for c in kept],
            "removed_claims": [c.model_dump() for c in removed],
            "weak_match": weak_match,
            "needs_human_check": top.confidence < 0.45 or (rule.is_ex if rule else True) or weak_match
                                 or (hint is not None and top.heading != hint),
        })
    procedure_ids = [cid for cid in (art_transport, art_proof, dgft) if cid]
    citations = {cid: resolve(kb, cid) for cid in sorted(retrieved | set(procedure_ids)) if cid in kb.chunks}
    return {
        "status": "analysed",
        "lines": lines_out,
        "total_mfn_duty_aed": float(total_mfn),
        "max_potential_saving_aed": float(total_mfn),
        "preferential_rate": "needs human check: the UAE CEPA tariff schedule (Annex 2B) is not in the knowledge base",
        "common_requirements": [
            {"text": "Goods must be transported directly from India to the UAE (direct consignment).",
             "citation": art_transport},
            {"text": "A certificate of origin (or origin declaration) is the proof of origin.", "citation": art_proof},
            {"text": "Preferential certificates of origin for the UAE are issued on the DGFT CoO e-platform.",
             "citation": dgft},
        ],
        "citations": citations,
        "needs_human_check": True,
        "note": "Indicative only: verify with a customs broker. Savings shown are the MFN duty that a 0% CEPA "
                "rate would remove; confirm the line's preferential rate in Annex 2B.",
    }


async def analyse_duty(rfq, quote: dict) -> dict:
    """Async wrapper; reports clearly when the knowledge base is unavailable."""
    if not index_exists():
        return {"status": "kb_unavailable", "needs_human_check": True, "lines": [], "max_potential_saving_aed": None,
                "note": "Knowledge base not built on this server (`make kb`): no cited CEPA analysis possible."}
    try:
        return await asyncio.to_thread(analyse_duty_sync, rfq, quote)
    except Exception as exc:          # never let the knowledge base take the whole run down
        return {"status": "kb_error", "needs_human_check": True, "lines": [], "max_potential_saving_aed": None,
                "note": f"CEPA analysis failed ({type(exc).__name__}); needs human check."}


def _anchored_chunk(kb, sources: set[str], anchors: list[str]) -> str | None:
    """The first chunk of the given sources containing every anchor phrase (whitespace-insensitive)."""
    if not anchors:
        return None
    norm = [re.sub(r"\s+", " ", a) for a in anchors]
    for cid, c in kb.chunks.items():
        if c.source_id in sources and all(a in re.sub(r"\s+", " ", c.text) for a in norm):
            return cid
    return None


def build_doc_pack(duty: dict) -> dict:
    """Document pack with cited requirements and HS candidates per line."""
    if duty.get("status") != "analysed" or not index_exists():
        return {"status": "kb_unavailable", "documents": [], "hs": [], "needs_human_check": True}
    retriever = get_retriever()
    kb = retriever.kb
    mode = "rrf_rerank" if retriever.has_vectors else "bm25"
    # (search query, allowed sources, verbatim anchors). Anchors pin the exact official passage when the source's
    # layout splits a requirement from its heading (Dubai Customs guide: "Submit Customs Declaration" service).
    queries = {
        "Commercial invoice and packing list (import declaration)":
            ("documents required for customs declaration commercial invoice packing list",
             {"dubai_customs_services_guide_2025_v09"},
             ["Import: AED15.00 - AED100.00", "Required Documents - Invoice - Packing list - Certificate of Origin"]),
        "Certificate of origin (CEPA, DGFT e-platform)":
            ("preferential certificate of origin India UAE CEPA e-platform",
             {"dgft_trade_notice_05_2022_23_india_uae_cepa_ecoo"}, []),
        "Shipping bill (Indian export declaration, ICEGATE)":
            ("shipping bill export declaration filing", {"icegate_user_manual_web_forms_shipping_bill",
                                                          "dgft_how_to_export_practical_guide_2023_24"}, []),
    }
    documents = []
    for name, (query, sources, anchors) in queries.items():
        # The requirement passages do not depend on the buyer, so they are looked up once per index build.
        key = ("doc_pack", query, mode)
        if key not in retriever.hs_cache:
            retriever.hs_cache[key] = _anchored_chunk(kb, sources, anchors) or next(
                (h.chunk_id for h in retriever.search(query, k=1, mode=mode, kinds={"text"}, sources=sources,
                                                      candidates=20)), None)
        chunk_id = retriever.hs_cache[key]
        documents.append({"document": name, "citation": resolve(kb, chunk_id) if chunk_id else None,
                          "status": "required"})
    hs = [{"description": ln["description"],
           "candidates": [{"heading": c["heading"], "line": c["best_line"], "confidence": c["confidence"]}
                          for c in ln.get("hs_candidates", [])],
           "verified": False} for ln in duty["lines"]]
    return {"status": "prepared", "documents": documents, "hs": hs, "needs_human_check": True,
            "note": "HS codes are ranked candidates from the tariff; a human confirms before documents are issued."}
