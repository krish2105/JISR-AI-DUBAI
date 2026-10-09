"""
calibrate.py — Choose the agentic grading threshold on the DEV split only (never test).

Why this file exists:
    The corrective loop answers when the best passage's reranker probability reaches RERANK_RELEVANT, and
    otherwise rewrites, widens, and finally says "needs human check". The INT8 cross-encoder's probabilities are
    small and not on a 0.5 scale, so the threshold must be measured, not guessed.

    For every dev question that the planner routes to document search, this runs all three attempts with grading
    switched off and records each attempt's best probability and whether it found a gold passage. It then picks
    the threshold with the best balanced accuracy:
        answerable questions answered with a gold passage   (good answer)
        unanswerable questions refused                      (correct refusal)
    The best score is usually a plateau of thresholds; the chosen value is the plateau's geometric midpoint
    (robust with a small dev set: an edge value sits next to a drop). Output:
    eval/results/calibration_<timestamp>.json; the chosen value is copied into app/rag/agentic.py with a
    DECISIONS.md line.

Usage:  uv run python -m eval.calibrate
"""

import json
from datetime import UTC, datetime

from eval.common import DATA, RESULTS, git_sha


def _attempt_grades(question: str, retriever) -> list[tuple[float, list[str]]]:
    """(best probability, top chunk ids) for the initial, rewrite and widen attempts."""
    from app.rag import agentic

    answer = agentic.Answer(question=question, intents=["procedure"])
    saved = agentic.RERANK_RELEVANT
    agentic.RERANK_RELEVANT = 2.0                                     # never satisfied: run every attempt
    try:
        agentic.procedure_tool(question, retriever, answer, [3])
    finally:
        agentic.RERANK_RELEVANT = saved
    return [(a.best, a.top) for a in answer.attempts]


def main() -> None:
    """Measure on dev, choose a threshold, write the calibration result."""
    from app.rag.agentic import plan
    from app.rag.index import index_exists
    from app.rag.retriever import get_retriever

    if not index_exists():
        raise SystemExit("Knowledge base not built (make kb).")
    retriever = get_retriever()
    rows = [json.loads(line) for line in (DATA / "retrieval_eval.jsonl").read_text(encoding="utf-8").splitlines()]
    dev = [r for r in rows if r["split"] == "dev" and plan(r["question"]) == ["procedure"]]
    measured = []
    for r in dev:
        attempts = _attempt_grades(r["question"], retriever)
        found = [{"best": b, "gold_found": bool(set(top) & set(r["gold"]))} for b, top in attempts]
        measured.append({"id": r["id"], "answerable": r["answerable"], "gold": r["gold"], "attempts": found})

    def outcome(t: float, m: dict) -> bool:
        first = next((a for a in m["attempts"] if a["best"] >= t), None)    # the attempt that would answer
        return (first is not None and first["gold_found"]) if m["answerable"] else first is None

    candidates = sorted({a["best"] for m in measured for a in m["attempts"]} | {0.005, 0.01, 0.02, 0.05, 0.1})
    pos = [m for m in measured if m["answerable"]]
    neg = [m for m in measured if not m["answerable"]]
    table = []
    for t in candidates:
        good = sum(outcome(t, m) for m in pos) / len(pos) if pos else 0.0
        refuse = sum(outcome(t, m) for m in neg) / len(neg) if neg else 0.0
        table.append({"threshold": round(t, 4), "good_answer_rate": good, "correct_refusal_rate": refuse,
                      "balanced": (good + refuse) / 2})
    top = max(round(row["balanced"], 6) for row in table)
    plateau = [row["threshold"] for row in table if round(row["balanced"], 6) == top and row["threshold"] > 0]
    mid = round((min(plateau) * max(plateau)) ** 0.5, 2)
    best = {**max((row for row in table if row["threshold"] <= mid), key=lambda row: row["threshold"]),
            "threshold": mid, "plateau": [min(plateau), max(plateau)]}
    result = {"suite": "calibration", "git_sha": git_sha(), "split": "dev",
              "timestamp": datetime.now(UTC).isoformat(timespec="seconds"), "n": len(measured),
              "n_answerable": len(pos), "n_unanswerable": len(neg), "chosen": best,
              "table": [row for row in table if row["threshold"] <= 0.5], "measured": measured}
    RESULTS.mkdir(parents=True, exist_ok=True)
    out = RESULTS / f"calibration_{datetime.now(UTC):%Y%m%d-%H%M}.json"
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"dev questions routed to document search: {len(measured)} ({len(pos)} answerable, {len(neg)} not)")
    print(f"chosen RERANK_RELEVANT = {best['threshold']}  good answers {best['good_answer_rate']:.2f}  "
          f"correct refusals {best['correct_refusal_rate']:.2f}  -> {out.name}")


if __name__ == "__main__":
    main()
