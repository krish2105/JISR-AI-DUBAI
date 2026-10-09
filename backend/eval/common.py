"""
common.py — Shared pieces of the evaluation harness.

Why this file exists:
    Every suite loads datasets the same way, writes results in the same contract, and uses the
    same text normalisation, so numbers from different suites (and different days) are comparable.

Results contract (one JSON file per suite run, never edited by hand):
    suite, git_sha, timestamp, models, llm_profile, dataset_version, split, n, metrics{},
    slices{ name: {metric: value} }, failures[ worst examples ], notes[]
"""

import json
import re
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
DATA = REPO / "data" / "synthetic"
RESULTS = BACKEND / "eval" / "results"


@dataclass
class EvalContext:
    """Options shared by all suites for one run."""

    fast: bool = False                  # fast = test split only, smaller samples (CI on every PR)
    split: str | None = None            # None = all splits
    concurrency: int = 8                # parallel model calls (lower it for free tiers)


@dataclass
class SuiteResult:
    """What a suite returns: headline metrics, per-slice breakdowns and the worst failures."""

    suite: str
    n: int
    metrics: dict[str, float]
    slices: dict[str, dict[str, float]] = field(default_factory=dict)
    failures: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------------------
# Datasets
# ---------------------------------------------------------------------------------------


def dataset_version() -> str:
    """Version string from data/synthetic/MANIFEST.json."""
    return json.loads((DATA / "MANIFEST.json").read_text(encoding="utf-8"))["version"]


def load(name: str, ctx: EvalContext) -> list[dict]:
    """Load a dataset (enquiries | adversarial | docsets), filtered by split for this run."""
    rows = [json.loads(line) for line in (DATA / f"{name}.jsonl").read_text(encoding="utf-8").splitlines() if line]
    split = ctx.split or ("test" if ctx.fast else None)
    return [r for r in rows if split is None or r["split"] == split]


# ---------------------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------------------

ARABIC_DIACRITICS = re.compile(r"[ً-ْـ]")       # tashkeel + tatweel
EN_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}
AR_MONTHS = {"يناير": 1, "فبراير": 2, "مارس": 3, "أبريل": 4, "ابريل": 4, "مايو": 5, "يونيو": 6, "يوليو": 7,
             "أغسطس": 8, "اغسطس": 8, "سبتمبر": 9, "أكتوبر": 10, "اكتوبر": 10, "نوفمبر": 11, "ديسمبر": 12}
STOPWORDS = {"of", "the", "and", "pcs", "pieces", "sets", "boxes", "qty", "من", "قطعة", "طقم", "علبة", "و"}


def tokens(text: str) -> set[str]:
    """Lower-cased word tokens without stopwords or Arabic diacritics (for fuzzy matching)."""
    text = ARABIC_DIACRITICS.sub("", text.lower()).replace("-", " ")
    return {t for t in re.findall(r"[\w؀-ۿ]+", text) if t not in STOPWORDS and not t.isdigit()}


def description_match(gold: dict, predicted: str) -> bool:
    """A predicted item description matches if it contains (most of) the gold English or Arabic words."""
    pred = tokens(predicted)
    if not pred:
        return False
    for key in ("description_en", "description_ar"):
        gold_tokens = tokens(gold[key])
        if gold_tokens and len(gold_tokens & pred) / len(gold_tokens) >= 0.6:
            return True
    return False


def parse_deadline(text: str | None) -> dict | None:
    """Turn a free-text deadline (English or Arabic) into the structured gold format."""
    if not text:
        return None
    t = ARABIC_DIACRITICS.sub("", text.lower())
    if m := re.search(r"within\s+(\d+)\s+days?|خلال\s+(\d+)\s+يوم", t):
        return {"kind": "within_days", "days": int(m.group(1) or m.group(2))}
    if m := re.search(r"end of ([a-z]+)", t):
        month = EN_MONTHS.get(m.group(1)[:3])
        return {"kind": "end_of_month", "month": month} if month else None
    if m := re.search(r"نهاية\s+(\S+)", t):
        month = AR_MONTHS.get(m.group(1))
        return {"kind": "end_of_month", "month": month} if month else None
    if m := re.search(r"(\d{1,2})\s+([a-z]{3,9})", t):
        month = EN_MONTHS.get(m.group(2)[:3])
        return {"kind": "date", "day": int(m.group(1)), "month": month} if month else None
    if m := re.search(r"(\d{1,2})\s+(\S+)", t):
        month = AR_MONTHS.get(m.group(2))
        return {"kind": "date", "day": int(m.group(1)), "month": month} if month else None
    return None


# ---------------------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------------------


def git_sha() -> str:
    """Short commit id, with '-dirty' if there are uncommitted changes."""
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO, capture_output=True,
                             text=True, check=True).stdout.strip()
        # The eval's own outputs do not make the SOURCE dirty, so they are excluded from the check.
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--", ".", ":!backend/eval/results", ":!docs/EVAL_REPORT.md",
             ":!backend/eval/baseline.json"],
            cwd=REPO, capture_output=True, text=True).stdout
        return f"{sha}-dirty" if dirty.strip() else sha
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def models_in_use() -> tuple[str, dict[str, str]]:
    """(profile name, {role: model}) from the router configuration."""
    from app.config import get_settings
    from app.llm.router import load_profiles

    profile = get_settings().llm_profile
    return profile, {role: cfg.model for role, cfg in load_profiles()[profile].items()}


def write_result(result: SuiteResult, ctx: EvalContext) -> Path:
    """Save one suite's results following the contract above; returns the file path."""
    RESULTS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    profile, models = models_in_use()
    payload = {
        "suite": result.suite,
        "git_sha": git_sha(),
        "timestamp": datetime.now(UTC).isoformat(timespec="seconds"),
        "llm_profile": profile,
        "models": models,
        "dataset_version": dataset_version(),
        "split": ctx.split or ("test" if ctx.fast else "all"),
        "fast": ctx.fast,
        "n": result.n,
        "metrics": {k: round(v, 4) for k, v in result.metrics.items()},
        "slices": {k: {m: round(v, 4) for m, v in d.items()} for k, d in result.slices.items()},
        "failures": result.failures[:5],
        "notes": result.notes,
    }
    path = RESULTS / f"{result.suite}_{stamp}.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def latest_results() -> dict[str, dict]:
    """The newest result file of every suite (other files, e.g. calibration_*.json, are not suite results)."""
    latest: dict[str, dict] = {}
    for path in sorted(RESULTS.glob("*_*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if "metrics" in data and "llm_profile" in data:
            latest[data["suite"]] = data
    return latest


def f1(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    """(precision, recall, F1); 1.0 when there is nothing to find and nothing was predicted."""
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    score = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, score
