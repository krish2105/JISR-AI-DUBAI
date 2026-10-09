"""
test_eval_harness.py — Tests for the evaluation code itself (the yardstick must be right too).

Covers: dataset integrity and reproducibility, bilingual deadline parsing, fuzzy item matching,
extraction scoring, pricing invariants, the doc-checker contract, and the gate's decisions.
"""

import hashlib
import json
from collections import Counter

from app.agents.state import RFQ, LineItem
from eval.common import DATA, description_match, f1, parse_deadline
from eval.gate import evaluate
from eval.suites.extraction import score_one
from eval.suites.pricing import violations
from eval.suites.security import standalone_numbers
from eval.synth.adversarial import generate_adversarial
from eval.synth.adversarial_dev import generate_adversarial_dev
from eval.synth.docsets import MISTAKES, generate_docsets
from eval.synth.enquiries import generate_enquiries
from eval.synth.enquiries_handwritten import generate_handwritten
from eval.synth.generate import SEED
from eval.synth.pii import generate_pii


def _rows(name: str) -> list[dict]:
    """Load a committed dataset file."""
    return [json.loads(line) for line in (DATA / f"{name}.jsonl").read_text(encoding="utf-8").splitlines()]


# ---------- datasets -------------------------------------------------------------------------


def test_committed_datasets_match_the_generator_and_manifest():
    """Same seed -> same data: the committed files are exactly what the generator produces."""
    manifest = json.loads((DATA / "MANIFEST.json").read_text())
    for name, rows in (("enquiries", generate_enquiries(SEED)), ("adversarial", generate_adversarial()),
                       ("docsets", generate_docsets(SEED)), ("adversarial_dev", generate_adversarial_dev()),
                       ("pii", generate_pii(SEED)), ("enquiries_handwritten", generate_handwritten())):
        text = "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows)
        assert hashlib.sha256(text.encode()).hexdigest() == manifest["files"][f"{name}.jsonl"]["sha256"], name


def test_dataset_sizes_languages_and_splits():
    """300 enquiries (EN/AR/mixed), 30 attacks, 40 doc sets; splits roughly 60/20/20."""
    enquiries, attacks, docs = _rows("enquiries"), _rows("adversarial"), _rows("docsets")
    assert len(enquiries) == 300 and len(attacks) == 30 and len(docs) == 40
    assert Counter(r["language"] for r in enquiries) == {"en": 150, "ar": 105, "mixed": 45}
    assert Counter(r["split"] for r in enquiries) == {"train": 180, "dev": 60, "test": 60}
    assert sum(r["hard_negative"] for r in enquiries) == 10
    assert {r["language"] for r in attacks} == {"en", "ar", "mixed"}
    assert all(r["split"] == "test" for r in attacks)            # attacks are never tuned on


def test_every_mistake_type_is_planted_and_half_the_sets_are_clean():
    """Each of the 9 mistake types appears at least twice; exactly 20 sets are clean."""
    docs = _rows("docsets")
    planted = Counter(i["type"] for d in docs for i in d["labels"]["issues"])
    assert set(planted) == set(MISTAKES) and min(planted.values()) >= 2
    assert sum(d["labels"]["clean"] for d in docs) == 20


def test_easy_english_labels_are_literally_in_the_text():
    """Spot-check label correctness: easy English items and quantities appear verbatim."""
    for row in (r for r in _rows("enquiries") if r["language"] == "en" and r["difficulty"] == "easy"):
        for item in row["labels"]["items"]:
            assert item["description_en"] in row["text"], row["id"]
            assert item["quantity"] in standalone_numbers(row["text"]), row["id"]


# ---------- normalisation --------------------------------------------------------------------


def test_parse_deadline_english_and_arabic():
    """English and Arabic phrasings map to the same structured deadline."""
    assert parse_deadline("before 26 Nov") == {"kind": "date", "day": 26, "month": 11}
    assert parse_deadline("قبل 26 نوفمبر") == {"kind": "date", "day": 26, "month": 11}
    assert parse_deadline("by end of December") == {"kind": "end_of_month", "month": 12}
    assert parse_deadline("قبل نهاية ديسمبر") == {"kind": "end_of_month", "month": 12}
    assert parse_deadline("within 30 days") == parse_deadline("خلال 30 يوماً") == {"kind": "within_days", "days": 30}
    assert parse_deadline(None) is None and parse_deadline("asap") is None


def test_description_match_is_bilingual_and_tolerant():
    """Matches English or Arabic gold wording, ignores units/stopwords, rejects other products."""
    gold = {"description_en": "brass diya lamps", "description_ar": "مصابيح ديا نحاسية"}
    assert description_match(gold, "Brass Diya Lamps (medium)")
    assert description_match(gold, "قطعة من مصابيح ديا نحاسية")
    assert not description_match(gold, "brass serving trays")


def test_standalone_numbers_normalises_buyer_formats():
    """Arabic-Indic digits, thousands commas and 'k' all become integers."""
    assert standalone_numbers("٥٠٠ قطعة و 1,200 pcs and 1.5k more") == [500, 1200, 1500]


# ---------- scoring ---------------------------------------------------------------------------


def test_extraction_scoring_counts_items_and_fields():
    """One right item, one wrong quantity, correct Incoterm, missed deadline."""
    gold = {"items": [{"description_en": "pashmina shawls", "description_ar": "شالات باشمينا", "quantity": 300},
                      {"description_en": "silk scarves", "description_ar": "أوشحة حريرية", "quantity": 100}],
            "buyer_country": "AE", "incoterm": "CIF", "deadline": {"kind": "within_days", "days": 30},
            "language": "en"}
    rfq = RFQ(buyer_name="x", buyer_country="AE", incoterm="cif", deadline=None, language="en",
              items=[LineItem(description="pashmina shawls", quantity=300),
                     LineItem(description="silk scarves", quantity=10)])
    counts = score_one(gold, rfq)
    assert counts["items"] == [1, 1, 1]          # tp, fp (wrong qty), fn (missed real one)
    assert counts["incoterm"] == [1, 0, 0]
    assert counts["deadline"] == [0, 0, 1]
    assert f1(1, 1, 1)[2] == 0.5


def test_pricing_invariants_catch_a_broken_quote():
    """A line total that is not unit x qty is reported."""
    quote = {"fx_inr_to_aed": 0.0436, "total_aed": 11968.2, "total_inr": 274500.0,
             "lines": [{"description": "lamps", "quantity": 500, "unit_price_aed": 23.94, "unit_price_inr": 549.0,
                        "total_aed": 11968.2, "total_inr": 274500.0}]}
    assert "AED line total lamps" in violations(quote)


# ---------- gate ------------------------------------------------------------------------------


def _result(metrics: dict, fast: bool = False) -> dict:
    return {"metrics": metrics, "fast": fast}


def test_gate_pass_target_fail_and_regression():
    """Hard breach fails, target breach does not, regression beyond the margin fails."""
    thresholds = {"regression_margin": 0.02,
                  "security": {"pii_redaction_recall": {"min": 1.0, "gate": "hard"}},
                  "extraction": {"extraction_f1": {"min": 0.9, "gate": "target", "phase": 4}}}
    ok_rows, ok_failed = evaluate({"security": _result({"pii_redaction_recall": 1.0}),
                                   "extraction": _result({"extraction_f1": 0.76})}, thresholds, {})
    assert not ok_failed and {r[4] for r in ok_rows} == {"PASS", "TARGET"}

    _, hard_failed = evaluate({"security": _result({"pii_redaction_recall": 0.9}),
                               "extraction": _result({"extraction_f1": 0.76})}, thresholds, {})
    assert hard_failed

    baseline = {"full": {"extraction": {"extraction_f1": 0.80}}}
    rows, regressed = evaluate({"security": _result({"pii_redaction_recall": 1.0}),
                                "extraction": _result({"extraction_f1": 0.70})}, thresholds, baseline)
    assert regressed and any("REGRESSED" in r[4] for r in rows)


def test_gate_fails_when_a_hard_suite_is_missing():
    """No results for a suite with a hard gate = not proven = fail."""
    thresholds = {"redteam": {"attack_success_rate": {"max": 0.0, "gate": "hard"}}}
    rows, failed = evaluate({}, thresholds, {})
    assert failed and rows[0][4] == "MISSING"


def test_timing_metrics_can_opt_out_of_regression():
    """Wall-clock metrics keep their absolute limit but ignore baseline noise."""
    thresholds = {"regression_margin": 0.02,
                  "e2e": {"latency_p95_s": {"max": 120, "gate": "hard", "regression": False}}}
    baseline = {"full": {"e2e": {"latency_p95_s": 0.04}}}
    rows, failed = evaluate({"e2e": _result({"latency_p95_s": 0.09})}, thresholds, baseline)
    assert not failed and rows[0][4] == "PASS"
    _, too_slow = evaluate({"e2e": _result({"latency_p95_s": 130})}, thresholds, baseline)
    assert too_slow
