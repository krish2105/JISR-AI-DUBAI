"""
agentic.py — Agentic RAG: plan -> route -> retrieve -> grade -> correct -> claims -> grounding check (v3 §22.1-22.2).

Why this file exists:
    "Retrieve once, then answer" invents facts when retrieval misses. Here the agent decides HOW to retrieve,
    checks what it found, retries differently when it found nothing good, and only states claims it can prove:

      plan     detect intents (HS classification, origin rule, duty rate, procedure) and split sub-questions
      route    each sub-question goes to the right tool: exact code lookup, tariff tree, Annex 3B rules,
               or document search
      grade    the cross-encoder score says relevant / partial / irrelevant
      correct  if nothing relevant: rewrite the query (domain synonyms, Arabic -> English trade terms), then widen
               (keyword-only, all document kinds); every attempt is logged so judges can watch it self-correct
      answer   atomic CLAIMS, each citing passage ids
      ground   CODE (not a model) checks every claim: it must cite retrieved passages, and every number in it must
               appear verbatim in a cited passage. Failing claims are removed; if none survive -> "needs human check"
      budget   hard limits on searches and steps; when exhausted, return what is supported + `incomplete`

Offline (fake profile) the claim writer is EXTRACTIVE: claims are built from structured fields or copied
sentences, so they are grounded by construction. With a real model (dev/prod) the model writes the claims and
the same grounding check applies.
"""

import asyncio
import re
from typing import Literal

from pydantic import BaseModel, Field

from app.rag.ingest_psr import rule_for
from app.rag.retriever import Retriever, classify_hs, get_retriever

Intent = Literal["hs", "psr", "duty", "procedure"]
# Grade thresholds. With the reranker they are CALIBRATED on the dev half of the retrieval set (eval/calibrate.py);
# without it (no vectors) word coverage is used with fixed, conservative values.
RERANK_RELEVANT, RERANK_PARTIAL = 0.24, 0.12           # eval/results/calibration_20261009-1615.json (DECISIONS K11)
# Tariff lines are short, so the reranker scores them on another scale (a correct "brass diya lamps" line: 0.16).
# Gate only clearly irrelevant matches: below 38 of 39 correct dev classifications; the dev split has only two
# non-goods questions, too few to calibrate (DECISIONS K13).
HS_MIN_RELEVANCE = 0.01
COVERAGE_RELEVANT, COVERAGE_PARTIAL = 0.6, 0.4

# Small bilingual trade lexicon used by the corrective rewrite (Arabic -> English and synonyms).
LEXICON = {
    "شهادة المنشأ": "certificate of origin", "شهادات المنشأ": "certificates of origin", "قواعد المنشأ": "rules of origin",
    "قاعدة المنشأ": "rule of origin", "الرسوم الجمركية": "customs duty", "رسوم": "duty", "الفاتورة": "invoice",
    "قائمة التعبئة": "packing list", "التصريح الجمركي": "customs declaration", "المصدر": "exporter",
    "التحقق": "verification", "الشحن": "shipment", "النقل المباشر": "direct consignment", "الإعفاء": "exemption",
    "ضريبة القيمة المضافة": "VAT", "الاستيراد": "import", "التصدير": "export", "المستندات": "documents",
    "coo": "certificate of origin", "psr": "product specific rule", "rvc": "value addition", "vat": "value added tax",
    "transshipment": "transport direct consignment third party", "eCoO": "electronic certificate of origin",
}
QUESTION_FILLER = re.compile(
    r"^(what|which|how|is|are|does|do|can|please|tell me|explain)\b|\b(the|is|are|for|of|a|an|under|in|cepa|uae|india)\b|[?؟]|"
    r"(ما هي|ما هو|هل|كيف|ماذا|ما)", re.I)


class Budget(BaseModel):
    """Hard limits per question."""

    max_searches: int = 6
    max_steps: int = 14


class Attempt(BaseModel):
    """One retrieval try (shown in the trace)."""

    sub_question: str
    query: str
    action: str                                     # initial | rewrite | widen | exact | classify
    best: float
    top: list[str] = Field(default_factory=list)


class Claim(BaseModel):
    """One atomic statement with its evidence."""

    text: str
    citations: list[str]
    status: Literal["supported", "unsupported", "contradicted"] = "supported"
    reason: str = ""


class Answer(BaseModel):
    """The agent's final, grounded answer."""

    question: str
    intents: list[Intent]
    claims: list[Claim] = Field(default_factory=list)
    removed_claims: list[Claim] = Field(default_factory=list)
    retrieved: list[str] = Field(default_factory=list)       # ranked chunk ids actually seen (for evaluation)
    attempts: list[Attempt] = Field(default_factory=list)
    needs_human_check: bool = False
    incomplete: bool = False
    note: str = ""


# ---------------------------------------------------------------------------------------
# Planning
# ---------------------------------------------------------------------------------------

INTENT_PATTERNS: dict[Intent, re.Pattern] = {
    "psr": re.compile(r"rule of origin|rules of origin|origin rule|product[- ]specific|\bpsr\b|qualif|"
                      r"قاعدة المنشأ|قواعد المنشأ|شروط المنشأ", re.I),
    "duty": re.compile(r"\bduty\b|duties|tariff rate|customs rate|import tax|رسوم|الرسوم|نسبة", re.I),
    "hs": re.compile(r"\bhs\b|classif|tariff code|which code|commodity code|تصنيف|البند|رمز", re.I),
}


PROCEDURE_HINT = re.compile(r"certificate of origin|proof of origin|origin declaration|verif|document|transport|"
                            r"consignment|invoice|cumulation|de minimis|شهادة المنشأ|إعلان المنشأ|المستندات|التحقق|النقل",
                            re.I)


def plan(question: str) -> list[Intent]:
    """Intents in the question (procedure when none of the structured ones match, or procedure words dominate)."""
    if PROCEDURE_HINT.search(question) and not re.search(r"\d{4}", question):
        return ["procedure"]
    intents = [i for i, rx in INTENT_PATTERNS.items() if rx.search(question)]
    if not intents and _is_product_phrase(question):
        return ["hs"]                              # "Fresh or chilled carrots" is a tariff lookup, not a procedure
    return intents or ["procedure"]


QUESTION_FORM = re.compile(r"[?؟]|^\s*(what|which|how|when|where|who|why|is|are|does|do|can|should|must|"
                           r"ما|ماذا|كيف|متى|أين|من|لماذا|هل|كم)\b", re.I)


def _is_product_phrase(text: str) -> bool:
    """A short statement with no question form names goods (the duty agent's and the tariff's wording)."""
    return not QUESTION_FORM.search(text) and len(text.split()) <= 12


def product_phrase(question: str) -> str:
    """The product words in a question ('What is the rule of origin for brass lamps?' -> 'brass lamps')."""
    q = re.sub(r"rules? of origin|origin rule|product[- ]specific rule|duty rate|customs duty|import duty|"
               r"hs code|tariff code|classification|qualif\w*|preferen\w*|قاعدة المنشأ|قواعد المنشأ|الرسوم الجمركية|"
               r"نسبة الرسوم|رسوم|تصنيف|البند الجمركي|(في )?اتفاقية الشراكة( الاقتصادية الشاملة)?|"
               r"(?<![\u0621-\u064a])[لب]?منتجات(?![\u0621-\u064a])", " ", question, flags=re.I)
    q = QUESTION_FILLER.sub(" ", q)
    return re.sub(r"\s+", " ", q).strip(" ,.:;") or question


QUESTION_WORDS = re.compile(r"^\s*(what|which|how|is|are|does|do|can|when|who|please|tell me|explain)\b|[?؟]|"
                            r"(ما هي|ما هو|هل|كيف|ماذا|متى|ما)\s", re.I)


def rewrite(query: str) -> str:
    """Corrective rewrite: Arabic trade terms -> English, abbreviations expanded, question words removed."""
    out = query
    for src, dst in sorted(LEXICON.items(), key=lambda kv: -len(kv[0])):
        out = re.sub(rf"(?<![A-Za-z0-9\u0621-\u064a]){re.escape(src)}(?![A-Za-z0-9\u0621-\u064a])", f" {dst} ", out, flags=re.I)
    return re.sub(r"\s+", " ", QUESTION_WORDS.sub(" ", out)).strip(" ,.:;")


def coverage(query: str, text: str) -> float:
    """Share of the question's content words found in a passage (grading when no reranker is available)."""
    from app.rag.analyzers import analyze

    q = set(analyze(QUESTION_WORDS.sub(" ", query)))
    return len(q & set(analyze(text))) / len(q) if q else 0.0


# ---------------------------------------------------------------------------------------
# Grounding (code, not a model)
# ---------------------------------------------------------------------------------------

NUMBER_RE = re.compile(r"(?<![\d.])\d+(?:[.,]\d+)*(?![\d])")


def _numbers(text: str) -> set[str]:
    """Whole numbers in a text, normalised ('1,200' -> '1200', '40 %' -> '40'); '94' never matches '9'."""
    from app.security.normalize import ARABIC_INDIC_DIGITS

    return {n.replace(",", "") for n in NUMBER_RE.findall(text.translate(ARABIC_INDIC_DIGITS))}


def ground(claims: list[Claim], retriever: Retriever, allowed: set[str]) -> tuple[list[Claim], list[Claim]]:
    """Keep claims that cite retrieved passages and whose numbers appear verbatim in a cited passage."""
    kept, removed = [], []
    for claim in claims:
        cited = [c for c in claim.citations if c in allowed and c in retriever.kb.chunks]
        if not cited:
            removed.append(claim.model_copy(update={"status": "unsupported", "reason": "no retrieved citation"}))
            continue
        evidence: set[str] = set()
        for c in cited:
            ch = retriever.kb.chunks[c]
            evidence |= _numbers(f"{ch.text} {ch.text_ar} {ch.code or ''} {ch.meta.get('rule_text', '')} "
                                 f"{ch.meta.get('duty_pct', '')}")
        missing = sorted(n for n in _numbers(claim.text) if n not in evidence)
        if missing:
            removed.append(claim.model_copy(update={"status": "unsupported",
                                                    "reason": f"numbers not in cited text: {missing}"}))
            continue
        kept.append(claim.model_copy(update={"citations": cited}))
    return kept, removed


# ---------------------------------------------------------------------------------------
# Tools per intent (extractive claim writers)
# ---------------------------------------------------------------------------------------


def _codes_in(question: str, retriever: Retriever) -> list[str]:
    """Codes written in the question: tariff nodes when they exist, else the digits as written (for rules)."""
    from app.rag.retriever import CODE_RE

    out = []
    for raw in CODE_RE.findall(question):
        digits = re.sub(r"\D", "", raw)
        out.append(retriever.tariff_node_for(digits) or digits)
    return out


def _best_sentences(text: str, query: str, n: int = 2) -> str:
    """The n sentences of a passage that share most words with the query (extractive, verbatim)."""
    q = set(re.findall(r"[a-zء-ي]{3,}", query.lower()))
    sentences = [s.strip() for s in re.split(r"(?<=[.;:])\s+(?=[A-Z(\d])", text) if len(s.strip()) > 20]
    ranked = sorted(sentences, key=lambda s: -len(q & set(re.findall(r"[a-zء-ي]{3,}", s.lower()))))
    return " ".join(ranked[:n])[:600]


def classify_tool(question: str, retriever: Retriever, answer: Answer, budget_left: list[int]) -> str | None:
    """HS code for the question: exact code if written, else top heading from the tariff tree."""
    codes = _codes_in(question, retriever)
    if codes:
        code = max(codes, key=len)
        answer.attempts.append(Attempt(sub_question="hs", query=question, action="exact", best=1.0, top=[f"hs:{code}"]))
        answer.retrieved.append(f"hs:{code}")
        return code
    if budget_left[0] <= 0:
        answer.incomplete = True
        return None
    budget_left[0] -= 1
    product = product_phrase(question)
    cands = classify_hs(retriever, product)
    answer.attempts.append(Attempt(sub_question="hs", query=product, action="classify",
                                   best=cands[0].best_score if cands else 0.0,
                                   top=[c.best_line for c in cands]))
    if not cands:
        return None
    for c in cands:
        answer.retrieved += [f"hs:{c.heading}"] + c.chunk_ids
    # Absolute relevance gate (same calibrated reranker threshold as document grading): "tourist visa fees" must
    # not become "Travelers cheques". Relative confidence alone cannot say "none of these fit".
    if cands[0].mode == "rrf_rerank" and cands[0].best_score < HS_MIN_RELEVANCE:
        answer.needs_human_check = True
        answer.note = "No tariff line clearly matches the goods described."
        return None
    if cands[0].confidence < 0.45:
        answer.needs_human_check = True
        answer.note = "HS classification is uncertain; top candidates listed."
    for c in cands:
        # The heading number is grounded in the heading's own passage, the description in the line's.
        answer.claims.append(Claim(text=f"Candidate HS heading {c.heading}: {c.best_line_desc}",
                                   citations=[f"hs:{c.heading}", f"hs:{c.best_line}"]))
    return cands[0].best_line


def psr_tool(code: str, retriever: Retriever, answer: Answer) -> None:
    """CEPA Annex 3B rule for a code, with the FOB / Ex-Works basis from Rule 1."""
    rule = rule_for(code, retriever.kb.rules)
    if not rule:
        answer.needs_human_check = True
        return
    answer.attempts.append(Attempt(sub_question="psr", query=code, action="exact", best=1.0, top=[rule.rule_id]))
    _psr_claims(rule, answer)


def psr_search_tool(question: str, retriever: Retriever, answer: Answer, budget_left: list[int]) -> bool:
    """Rule questions about a whole product group ("rule of origin for coffee, tea and spices"): search the
    Annex 3B rules themselves (their descriptions are chapter titles), graded by the calibrated threshold."""
    from app.rag.trade_terms import expand

    if budget_left[0] <= 0 or not retriever.has_vectors:
        return False
    budget_left[0] -= 1
    query = expand(rewrite(product_phrase(question)))
    hits = retriever.search(query, k=3, mode="rrf_rerank", kinds={"psr"}, use_exact=False)
    best = hits[0].stages.get("rerank", 0.0) if hits else 0.0
    answer.attempts.append(Attempt(sub_question="psr", query=query, action="rule_search", best=round(best, 3),
                                   top=[h.chunk_id for h in hits]))
    if not hits or best < RERANK_RELEVANT:
        return False
    rule = next(r for r in retriever.kb.rules if r.rule_id == hits[0].chunk_id)
    answer.needs_human_check, answer.note = False, None          # the tariff-line gate no longer applies
    _psr_claims(rule, answer)
    return True


def _psr_claims(rule, answer: Answer) -> None:
    """Claims for one Annex 3B rule (facts only; document, page label and date travel in the citation)."""
    answer.retrieved += [rule.rule_id, "psr_rule1"]
    answer.claims.append(Claim(text=f"CEPA product specific rule for {rule.scope_text} ({rule.description}): "
                                    f"{rule.rule_text}.", citations=[rule.rule_id]))
    if rule.components.get("va_pct"):
        answer.claims.append(Claim(text="Value addition percentages are on an FOB basis; on an Ex Works basis the "
                                        "value addition is 5 percentage points lower.", citations=["psr_rule1"]))
    if rule.is_ex:
        answer.needs_human_check = True
        answer.note = f"'Ex' rule: {rule.scope_text} applies only to part of the heading; check the product fits."


def duty_tool(code: str, retriever: Retriever, answer: Answer) -> None:
    """Published UAE duty for a tariff code (most specific node with a duty)."""
    node = None
    for length in (12, 8, 6, 4):
        candidate = retriever.kb.tariff.get(code[:length])
        if candidate and candidate.duty_pct not in (None, "", "None"):
            node = candidate
            break
    if node is None:                                   # heading-level code: use its first line for the rate
        lines = [n for c, n in retriever.kb.tariff.items() if c.startswith(code) and n.duty_pct]
        node = lines[0] if lines and len({n.duty_pct for n in lines}) == 1 else None
    if node is None:
        answer.needs_human_check = True
        answer.note = "Duty rate differs across lines under this code; a more specific code is needed."
        return
    cid = f"hs:{node.code}"
    answer.retrieved.append(cid)
    answer.claims.append(Claim(text=f"UAE customs duty for HS {node.code} ({node.desc_en}) is {node.duty_pct}% "
                                    "(MFN rate in the Dubai Customs tariff master, before any CEPA preference).",
                               citations=[cid]))


def procedure_tool(question: str, retriever: Retriever, answer: Answer, budget_left: list[int]) -> None:
    """Document search with grading and the corrective loop."""
    query, action = question, "initial"
    tried: set[str] = set()
    while budget_left[0] > 0:
        budget_left[0] -= 1
        kinds = {"text", "psr"} if action != "widen" else None
        if retriever.has_vectors:
            hits = (retriever.search(query, k=6, mode="rrf_rerank", kinds=kinds) if action != "widen" else
                    retriever.rerank(question, retriever.bm25_search(query, 30, kinds), top=6))
        else:
            hits = retriever.search(query, k=6, mode="bm25", kinds=kinds)
        # Grade: the reranker's probability when available, else word coverage (explainable, scale-free).
        for h in hits:
            passage = retriever._passage_text(retriever.kb.chunks[h.chunk_id])
            h.stages["grade"] = h.stages.get("rerank", coverage(query, passage))
        hits.sort(key=lambda h: -h.stages["grade"])
        best = max((h.stages["grade"] for h in hits), default=0.0)
        relevant, partial = ((RERANK_RELEVANT, RERANK_PARTIAL) if any("rerank" in h.stages for h in hits)
                             else (COVERAGE_RELEVANT, COVERAGE_PARTIAL))
        answer.attempts.append(Attempt(sub_question="procedure", query=query, action=action, best=round(best, 3),
                                       top=[h.chunk_id for h in hits[:5]]))
        answer.retrieved += [h.chunk_id for h in hits]
        if hits and best >= relevant:
            for h in hits[:2]:
                c = retriever.kb.chunks[h.chunk_id]
                if h.stages["grade"] >= partial:
                    answer.claims.append(Claim(text=_best_sentences(c.text, query), citations=[h.chunk_id]))
            return
        tried.add(query)
        if action == "initial":
            query, action = rewrite(question), "rewrite"
            if query in tried:
                action = "widen"
        elif action == "rewrite":
            action = "widen"
        else:
            break
    answer.needs_human_check = True
    answer.note = "No sufficiently relevant official passage found."


# ---------------------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------------------


def answer_question_sync(question: str, retriever: Retriever | None = None, budget: Budget | None = None) -> Answer:
    """Plan, retrieve, correct, write claims and ground them (synchronous, CPU-bound)."""
    retriever = retriever or get_retriever()
    budget = budget or Budget()
    intents = plan(question)
    answer = Answer(question=question, intents=intents)
    left = [budget.max_searches]
    if "procedure" in intents:
        procedure_tool(question, retriever, answer, left)
    else:
        # Rule questions without a written code ask about a product group: the rule table is searched first.
        if intents == ["psr"] and not _codes_in(question, retriever) and psr_search_tool(question, retriever,
                                                                                          answer, left):
            pass
        else:
            code = classify_tool(question, retriever, answer, left)
            if code:
                if "psr" in intents:
                    psr_tool(code, retriever, answer)
                if "duty" in intents:
                    duty_tool(code, retriever, answer)
            elif not answer.claims:
                answer.needs_human_check = True
    kept, removed = ground(answer.claims, retriever, set(answer.retrieved))
    answer.claims, answer.removed_claims = kept, removed
    answer.retrieved = list(dict.fromkeys(answer.retrieved))
    if not kept:
        answer.needs_human_check = True
        answer.note = answer.note or "I don't know: no claim could be grounded in an official source."
    return answer


async def answer_question(question: str, budget: Budget | None = None) -> Answer:
    """Async wrapper: retrieval is CPU-bound, so it runs in a worker thread."""
    return await asyncio.to_thread(answer_question_sync, question, None, budget)
