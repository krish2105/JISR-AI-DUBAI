"""
retrieval.py — Build the retrieval evaluation set from the OFFICIAL data itself (v3 §22.5).

Why this file exists:
    Retrieval quality must be measured separately from answer quality, with gold passages that were NOT chosen by
    the model under test. Every gold label here comes from the structure of the official sources:

      duty_exact      "What is the UAE duty for HS <code>?"             gold: that tariff line
      tariff_desc     a shortened official description (EN or AR)       gold: any line of the same 6-digit subheading
      psr_chapter     "What is the CEPA rule for <chapter title>?"      gold: that chapter's Annex 3B rule
      psr_chapter_ar  the same question in Arabic (cross-lingual: the rules are English-only)
      procedure       CEPA Chapter 3 questions (EN, and Arabic = cross-lingual), gold: chunks of the named ARTICLE
      unanswerable    outside the knowledge base: the right behaviour is "I don't know"

    Questions are template- or hand-written by the developer from the official text (not by the model being
    evaluated). Founder / trade-advisor review of a sample is still recommended (see data/synthetic/README.md).
Requires data/kb_index (run `make kb`). Output: data/synthetic/retrieval_eval.jsonl
"""

import hashlib
import json
import random
import re

from app.rag.index import INDEX_DIR

AR_CHAPTERS = {94: "الأثاث والمصابيح وأجهزة الإنارة", 44: "الخشب والمصنوعات الخشبية", 62: "الملابس غير المحبوكة",
               63: "المصنوعات النسيجية الجاهزة", 71: "اللؤلؤ والأحجار الكريمة والمجوهرات", 95: "اللعب والألعاب",
               9: "البن والشاي والتوابل", 76: "الألمنيوم ومصنوعاته", 74: "النحاس ومصنوعاته", 69: "منتجات الخزف",
               42: "المصنوعات الجلدية والحقائب", 57: "السجاد", 33: "العطور ومستحضرات التجميل", 61: "الملابس المحبوكة"}

# (article, English question, Arabic question)
PROCEDURES = [
    ("3.3", "Which products count as wholly obtained or produced?", "ما هي المنتجات التي تعتبر منتجة بالكامل؟"),
    ("3.4", "What is the de minimis rule for non-originating materials?", "ما هي قاعدة الحد الأدنى للمواد غير المنشئة؟"),
    ("3.5", "Which minimal or insufficient operations do not confer origin?", "ما هي العمليات البسيطة التي لا تمنح صفة المنشأ؟"),
    ("3.7", "How does bilateral cumulation work between India and the UAE?", "كيف يعمل التراكم الثنائي بين الهند والإمارات؟"),
    ("3.8", "How are packages, packing materials and containers treated for origin?", "كيف تعامل مواد التعبئة والحاويات في تحديد المنشأ؟"),
    ("3.9", "Are accessories, spare parts and tools considered originating?", "هل تعتبر الملحقات وقطع الغيار والأدوات منشئة؟"),
    ("3.12", "What are the transport and direct consignment conditions?", "ما هي شروط النقل والشحن المباشر؟"),
    ("3.13", "What documents serve as proof of origin?", "ما هي المستندات التي تثبت المنشأ؟"),
    ("3.15", "Is third-party invoicing allowed for preferential treatment?", "هل يسمح بفوترة طرف ثالث للمعاملة التفضيلية؟"),
    ("3.18", "How long must documents be preserved by the exporter?", "ما هي مدة الاحتفاظ بالمستندات من قبل المصدر؟"),
    ("3.20", "How must the certificate of origin be presented to customs?", "كيف تقدم شهادة المنشأ إلى الجمارك؟"),
    ("3.21", "How can the importing Party verify a certificate of origin?", "كيف يمكن للطرف المستورد التحقق من شهادة المنشأ؟"),
    ("3.25", "When can preferential treatment be denied?", "متى يمكن رفض المعاملة التفضيلية؟"),
    ("3.35", "What is an origin declaration by an approved exporter?", "ما هو إعلان المنشأ من المصدر المعتمد؟"),
    ("3.10", "How are indirect materials treated when determining origin?", "كيف تعامل المواد غير المباشرة عند تحديد المنشأ؟"),
]

UNANSWERABLE = [
    ("en", "What is the EU anti-dumping duty on steel from China?"),
    ("en", "What is the corporate income tax rate in Saudi Arabia?"),
    ("en", "What is the CEPA product specific rule for chapter 77?"),
    ("en", "Who won the cricket world cup in 2011?"),
    ("en", "What is the visa fee for a UAE tourist visa?"),
    ("en", "What is the US tariff on Indian textiles?"),
    ("en", "How many employees does Dubai Customs have?"),
    ("en", "What is the interest rate on a UAE mortgage?"),
    ("en", "What is the shipping time from Mumbai to New York?"),
    ("en", "Which bank offers the best export credit in India?"),
    ("ar", "ما هي رسوم التأشيرة السياحية في دبي؟"),
    ("ar", "ما هو سعر الفائدة على القروض العقارية؟"),
    ("ar", "من فاز بكأس العالم لكرة القدم 2018؟"),
    ("ar", "ما هي ضريبة الدخل على الشركات في السعودية؟"),
    ("ar", "ما هي الرسوم الأمريكية على المنسوجات الهندية؟"),
    ("ar", "كم عدد موظفي جمارك دبي؟"),
    ("ar", "ما هي مدة الشحن من مومباي إلى نيويورك؟"),
    ("ar", "ما هو أفضل بنك لتمويل الصادرات في الهند؟"),
    ("ar", "ما هي رسوم مكافحة الإغراق الأوروبية على الصلب الصيني؟"),
    ("ar", "ما هو سعر صرف الين الياباني اليوم؟"),
]


def _short(text: str, n: int) -> str:
    """First n content words of an official description (drop codes and punctuation)."""
    words = [w for w in re.findall(r"[A-Za-zء-ي][\wء-ي-]*", text) if len(w) > 2]
    return " ".join(words[:n])


def generate_retrieval(seed: int = 20261009) -> list[dict]:
    """About 150 questions with gold chunk ids, language and type."""
    rng = random.Random(seed)
    tariff = [json.loads(line) for line in (INDEX_DIR / "tariff.jsonl").read_text(encoding="utf-8").splitlines()]
    rules = json.loads((INDEX_DIR / "psr.json").read_text(encoding="utf-8"))["rules"]
    chunks = [json.loads(line) for line in (INDEX_DIR / "chunks.jsonl").read_text(encoding="utf-8").splitlines()]
    lines = [n for n in tariff if n["level"] == "line" and n["desc_en"] and n["desc_ar"]
             and not re.match(r"(?i)^(other|others)\b", n["desc_en"]) and n["duty_pct"] not in (None, "", "None")]
    by_sub: dict[str, list[str]] = {}
    for n in tariff:
        if n["level"] == "line":
            by_sub.setdefault(n["code"][:6], []).append(f"hs:{n['code']}")
    rows: list[dict] = []

    def add(qid, language, qtype, question, gold, answerable=True):
        rows.append({"id": qid, "language": language, "type": qtype, "question": question, "gold": gold,
                     "answerable": answerable, "split": "test"})

    for i, n in enumerate(rng.sample(lines, 25)):
        if i < 10:
            add(f"rq_dx_en_{i}", "en", "duty_exact", f"What is the UAE customs duty rate for HS {n['code']}?",
                [f"hs:{n['code']}"])
        else:
            add(f"rq_dx_ar_{i}", "ar", "duty_exact", f"ما هي نسبة الرسوم الجمركية على البند {n['code']}؟",
                [f"hs:{n['code']}"])
    for i, n in enumerate(rng.sample(lines, 50)):
        gold = by_sub[n["code"][:6]]
        if i < 20:
            add(f"rq_td_en_{i}", "en", "tariff_desc", _short(n["desc_en"], 6), gold)
        else:
            add(f"rq_td_ar_{i}", "ar", "tariff_desc", _short(n["desc_ar"], 6), gold)
    chapter_rules = [r for r in rules if not r["codes"]]
    for i, r in enumerate(rng.sample(chapter_rules, 15)):
        add(f"rq_psr_en_{i}", "en", "psr_chapter",
            f"What is the CEPA product specific rule for {_short(r['description'], 7)}?", [r["rule_id"]])
    for ch, name in AR_CHAPTERS.items():
        rid = next((r["rule_id"] for r in chapter_rules if ch in r["chapters"]), None)
        if rid:
            add(f"rq_psr_ar_{ch}", "cross", "psr_chapter", f"ما هي قاعدة المنشأ في اتفاقية الشراكة لمنتجات {name}؟", [rid])
    for art, en_q, ar_q in PROCEDURES:
        gold = [c["chunk_id"] for c in chunks if c["source_id"] == "cepa_final"
                and c.get("title", "").startswith(f"ARTICLE {art} ")]
        if gold:
            add(f"rq_proc_en_{art}", "en", "procedure", en_q, gold)
            add(f"rq_proc_ar_{art}", "cross", "procedure", ar_q, gold)
    for i, (lang, q) in enumerate(UNANSWERABLE):
        add(f"rq_none_{lang}_{i}", lang, "unanswerable", q, [], answerable=False)
    return _assign_splits(rows)


def _assign_splits(rows: list[dict]) -> list[dict]:
    """Stable 40/60 dev/test split inside each question type (sorted by a hash of the id).

    Dev is used to calibrate the grading thresholds and to look at failures; test is only reported.
    The English and Arabic versions of one procedure question share an article, so they share a split.
    """
    def key(r: dict) -> str:
        return re.sub(r"_(en|ar)_", "_", r["id"]) if r["type"] == "procedure" else r["id"]

    by_type: dict[str, list[str]] = {}
    for r in rows:
        group = by_type.setdefault(r["type"], [])
        if key(r) not in group:
            group.append(key(r))
    dev: set[str] = set()
    for keys in by_type.values():
        keys.sort(key=lambda k: hashlib.sha1(k.encode()).hexdigest())
        dev |= set(keys[: round(0.4 * len(keys))])
    for r in rows:
        r["split"] = "dev" if key(r) in dev else "test"
    return rows
