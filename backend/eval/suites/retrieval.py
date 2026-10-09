"""
retrieval.py — Suite: retrieval quality (ablation) and grounded-answer quality (v3 §22.2, §22.5).

Retrieval metrics (answerable questions; any gold chunk counts as a hit):
    recall@5, recall@10, MRR, nDCG@10, precision@5 — per pipeline and per language (en / ar / cross-lingual)
Pipelines (ablation):  bm25 -> vector -> rrf (bm25 + vector fused) -> rrf_rerank -> agentic (with corrective loop)
HS classification:     heading accuracy top-1 / top-3 on hand-labelled seller phrases (data/gold/hs_products.jsonl,
                       e.g. "brass diya lamps"), reported for glossary-covered and uncovered goods separately; plus
                       the easier tariff-wording questions (hs_tariffdesc_top1)
Answer metrics (agentic):
    grounded_claim_rate      supported claims / all claims written (claims failing the code check are removed)
    numeric_verbatim_pass    claims containing numbers whose numbers all appear verbatim in a cited passage
    correct_refusal_rate     unanswerable questions answered "needs human check" with no claims
    false_refusal_rate       answerable questions refused

Splits: headline numbers are on the TEST split. `--split dev` runs the dev split only; it is the one used to
calibrate the grading thresholds (eval/calibrate.py) and to look at failures.

Needs the local knowledge base (`make kb`). Without it the suite reports SKIP (CI has no sources or models).
"""

import math
import time
from collections import defaultdict

from eval.common import DATA, REPO, EvalContext, SuiteResult

MODES = ["bm25", "vector", "rrf", "rrf_rerank"]


def _read(path) -> list[dict]:
    import json

    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _split(ctx: EvalContext) -> str:
    return ctx.split or "test"


def _load_questions(ctx: EvalContext) -> list[dict]:
    return [q for q in _read(DATA / "retrieval_eval.jsonl") if q.get("split", "test") == _split(ctx)]


def _load_products(ctx: EvalContext) -> list[dict]:
    return [q for q in _read(REPO / "data" / "gold" / "hs_products.jsonl") if q["split"] == _split(ctx)]


def _scores(ranked: list[str], gold: set[str]) -> dict[str, float]:
    """Rank metrics for one question."""
    hits = [1 if cid in gold else 0 for cid in ranked[:10]]
    first = next((i for i, h in enumerate(hits) if h), None)
    dcg = sum(h / math.log2(i + 2) for i, h in enumerate(hits))
    ideal = sum(1 / math.log2(i + 2) for i in range(min(len(gold), 10)))
    return {"recall@5": float(any(hits[:5])), "recall@10": float(any(hits)),
            "mrr": 1 / (first + 1) if first is not None else 0.0, "ndcg@10": dcg / ideal if ideal else 0.0,
            "precision@5": sum(hits[:5]) / 5}


def _mean(rows: list[dict[str, float]]) -> dict[str, float]:
    return {k: sum(r[k] for r in rows) / len(rows) for k in rows[0]} if rows else {}


async def run(ctx: EvalContext) -> SuiteResult:
    """Run the ablation and the agentic answers."""
    from app.rag.index import index_exists

    questions = _load_questions(ctx)
    if not index_exists() or not questions:
        return SuiteResult("retrieval", 0, {}, notes=["SKIPPED: knowledge base not built here (run `make kb`)."])

    from app.rag.agentic import answer_question_sync
    from app.rag.retriever import classify_hs, get_retriever

    retriever = get_retriever()
    answerable = [q for q in questions if q["answerable"]]
    modes = ["rrf_rerank"] if ctx.fast else MODES
    if not retriever.has_vectors:
        modes = ["bm25"]
    per_mode: dict[str, list[dict]] = defaultdict(list)
    per_slice: dict[str, list[dict]] = defaultdict(list)
    timing: dict[str, float] = {}
    for mode in modes:
        t0 = time.perf_counter()
        for q in answerable:
            ranked = [h.chunk_id for h in retriever.search(q["question"], k=10, mode=mode)]
            s = _scores(ranked, set(q["gold"]))
            per_mode[mode].append(s)
            per_slice[f"mode={mode}/lang={q['language']}"].append(s)
        timing[mode] = (time.perf_counter() - t0) / max(len(answerable), 1)

    # Agentic: plan + route + corrective loop + grounded claims.
    t0 = time.perf_counter()
    claims_total = claims_kept = num_claims = num_ok = 0
    refusals_ok = refusals_bad = 0
    failures = []
    for q in questions:
        ans = answer_question_sync(q["question"], retriever)
        written = len(ans.claims) + len(ans.removed_claims)
        claims_total += written
        claims_kept += len(ans.claims)
        for c in ans.claims + ans.removed_claims:
            if any(ch.isdigit() for ch in c.text):
                num_claims += 1
                num_ok += c.status == "supported"
        refused = ans.needs_human_check and not ans.claims
        if q["answerable"]:
            s = _scores(ans.retrieved, set(q["gold"]))
            per_mode["agentic"].append(s)
            per_slice[f"mode=agentic/lang={q['language']}"].append(s)
            refusals_bad += refused
            if not s["recall@10"]:
                failures.append({"id": q["id"], "type": q["type"], "language": q["language"],
                                 "question": q["question"][:120], "got": ans.retrieved[:3]})
        else:
            refusals_ok += refused
            if not refused:
                failures.append({"id": q["id"], "type": "unanswerable", "question": q["question"][:120],
                                 "claims": [c.text[:80] for c in ans.claims[:1]]})
    timing["agentic"] = (time.perf_counter() - t0) / max(len(questions), 1)

    # HS heading accuracy: seller phrases (the duty agent's real input) and tariff-wording questions.
    from app.rag.trade_terms import tariff_terms

    hs_rows: dict[str, list[dict]] = defaultdict(list)
    for q in _load_products(ctx):
        cands = classify_hs(retriever, q["description"])
        got = [c.heading for c in cands[:3]]
        r = {"top1": float(bool(got) and got[0] in q["headings"]), "top3": float(any(h in q["headings"] for h in got))}
        covered = "covered" if tariff_terms(q["description"]) else "uncovered"
        for key in ("all", f"lang={q['language']}", f"glossary={covered}"):
            hs_rows[key].append(r)
        if not r["top1"]:
            failures.append({"id": q["id"], "type": "hs_product", "question": q["description"],
                             "expected": q["headings"], "got": got})
    top1 = top3 = n_hs = 0
    for q in (q for q in answerable if q["type"] == "tariff_desc"):
        cands = classify_hs(retriever, q["question"])
        gold_headings = {g[3:7] for g in q["gold"]}
        n_hs += 1
        top1 += bool(cands) and cands[0].heading in gold_headings
        top3 += any(c.heading in gold_headings for c in cands[:3])

    best = "rrf_rerank" if "rrf_rerank" in per_mode else modes[-1]
    unanswerable = [q for q in questions if not q["answerable"]]
    metrics = {f"{k}": v for k, v in _mean(per_mode[best]).items()}
    metrics |= {f"agentic_{k}": v for k, v in _mean(per_mode["agentic"]).items()}
    metrics |= {
        "grounded_claim_rate": claims_kept / claims_total if claims_total else 1.0,
        "numeric_verbatim_pass": num_ok / num_claims if num_claims else 1.0,
        "correct_refusal_rate": refusals_ok / len(unanswerable) if unanswerable else 1.0,
        "false_refusal_rate": refusals_bad / len(answerable) if answerable else 0.0,
        "hs_product_top1": _mean(hs_rows["all"]).get("top1", 0.0),
        "hs_product_top3": _mean(hs_rows["all"]).get("top3", 0.0),
        "hs_tariffdesc_top1": top1 / n_hs if n_hs else 0.0,
        "hs_tariffdesc_top3": top3 / n_hs if n_hs else 0.0,
    }
    slices = {f"mode={m}": _mean(rows) for m, rows in per_mode.items()}
    slices |= {f"hs_product/{k}": {**_mean(v), "n": len(v)} for k, v in sorted(hs_rows.items())}
    slices |= {k: _mean(v) for k, v in sorted(per_slice.items())}
    notes = [f"Split: {_split(ctx)}. Headline retrieval numbers use pipeline '{best}'. Seconds per question: "
             + ", ".join(f"{k} {v:.2f}" for k, v in timing.items()),
             "Gold passages come from the structure of the official sources (eval/synth/retrieval.py), "
             "not from a model."]
    failures.sort(key=lambda f: f["type"] != "hs_product")           # HS misses first: they cost real money
    return SuiteResult("retrieval", len(questions), metrics, slices, failures, notes)
