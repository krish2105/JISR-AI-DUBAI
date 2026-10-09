"""
test_rag.py — Phase 5: parsers, analysers, retrieval stages, agentic RAG, grounding, duty evidence.

Hermetic: a tiny in-memory knowledge base (real Annex 3B wording and real tariff lines, copied as fixtures)
so these tests run anywhere, including CI, without the 2.6 GB models or the downloaded sources.
Tests against the full local index live in test_kb_real.py and skip when `make kb` has not been run.
"""

import pytest

from app.agents.trade_agents import _evidence_for
from app.rag.agentic import Budget, Claim, answer_question_sync, ground, plan, product_phrase, rewrite
from app.rag.analyzers import analyze, query_language
from app.rag.index import KnowledgeBase, psr_chunk, tariff_chunk
from app.rag.ingest_psr import _expand_codes, canonical_rule, components, rule_for
from app.rag.models import Chunk, OriginRule, Source, TariffNode
from app.rag.retriever import Retriever, classify_hs

T = "uae_tariff_master"


def _node(code, level, en, ar="", duty=None, parent=None):
    return TariffNode(code=code, level=level, parent=parent, desc_en=en, desc_ar=ar, duty_pct=duty, source_id=T)


def _rule(rid, scope, chapters, codes, desc, text, label, is_ex=False):
    return OriginRule(rule_id=rid, scope_text=scope, chapters=chapters, codes=codes, is_ex=is_ex, description=desc,
                      rule_text=text, components=components(text), page=58, page_label=label, source_id="cepa_final")


@pytest.fixture(scope="module")
def retriever() -> Retriever:
    nodes = [
        _node("94", "chapter", "Chapter 94: Furniture; lamps and lighting fittings"),
        _node("9405", "heading", "Includes: Lamps and lighting fittings", parent="94"),
        _node("940519000000", "line", "Other chandeliers and other electric ceiling or wall lighting fittings",
              "غيرها من ثريات وأجهزة إنارة كهربائية", "5", parent="9405"),
        _node("940550000000", "line", "Non-electrical lamps and lighting fittings", "مصابيح غير كهربائية", "5",
              parent="9405"),
        _node("62", "chapter", "Chapter 62: Articles of apparel, not knitted"),
        _node("621420100000", "line", "Shawls of wool or fine animal hair, not knitted or crocheted",
              "شالات من صوف أو من وبر ناعم", "5", parent="6214"),
        _node("71", "chapter", "Chapter 71: Pearls, precious stones"),
        _node("710239000000", "line", "Other diamonds, non-industrial", "ماس غير صناعي", "0", parent="7102"),
    ]
    rules = [
        _rule("psr_ch94", "Chapter 94", [94], [], "Furniture; bedding; lamps and lighting fittings", "CTH + VA 40%",
              "Annex 3B-9"),
        _rule("psr_ch62", "Chapter 62", [62], [], "Articles of apparel and clothing accessories, not knitted",
              "CTH + VA 40%", "Annex 3B-6"),
        _rule("psr_7102", "7102", [71], ["7102"], "Diamonds", "CTSH + VA 6%", "Annex 3B-7"),
        _rule("psr_2207-2208", "Ex 2207, Ex 2208", [22], ["2207", "2208"], "Undenatured ethyl alcohol for medical use",
              "CTH + VA 40%", "Annex 3B-3", is_ex=True),
    ]
    docs = [
        Chunk(chunk_id="cepa_final:3.12:0", kind="text", source_id="cepa_final", title="ARTICLE 3.12 Transport", page=36,
              text="Preferential treatment shall be accorded to originating products that are transported directly "
                   "from the exporting Party to the importing Party. Products transiting through third parties keep "
                   "their status if they remain under customs control."),
        Chunk(chunk_id="cepa_final:3.4:0", kind="text", source_id="cepa_final", title="ARTICLE 3.4 De Minimis", page=31,
              text="A product that does not satisfy a change in tariff classification requirement shall be considered "
                   "originating if the value of non-originating materials does not exceed 10 per cent of the FOB value."),
        Chunk(chunk_id="psr_rule1", kind="text", source_id="cepa_final", title="Annex 3B Rule 1 Definitions",
              text="VA means value addition. The percentages are on an FOB basis. In the case that Ex Works price is "
                   "the basis, the value addition shall be 5 percentage points lower."),
    ]
    chunks = {c.chunk_id: c for c in [tariff_chunk(n) for n in nodes] + [psr_chunk(r) for r in rules] + docs}
    kb = KnowledgeBase(chunks=chunks, tariff={n.code: n for n in nodes}, rules=rules, definitions="",
                       sources={"cepa_final": Source(source_id="cepa_final", title="CEPA", issuing_body="UAE MoET",
                                                     url="https://example", document_date="2022-03-28", local_file="x")})
    return Retriever(kb)


# ---------- parsing helpers ---------------------------------------------------------------------


def test_rule_helpers():
    assert canonical_rule("CTSH +VA40 %") == "CTSH + VA 40%"
    assert components("CTH + VA 45%") | {} == {"wo": False, "cc": False, "cth": True, "ctsh": False, "so": False,
                                                "melt": False, "va_pct": 45, "has_alternatives": False}
    assert _expand_codes("2007-2009") == (["2007", "2008", "2009"], False)
    assert _expand_codes("Ex 2207, Ex 2208") == (["2207", "2208"], True)


def test_rule_for_prefers_the_most_specific_scope(retriever):
    rules = retriever.kb.rules
    assert rule_for("710239", rules).rule_id == "psr_7102"          # heading row beats the chapter
    assert rule_for("940519000000", rules).rule_id == "psr_ch94"
    assert rule_for("010101", rules) is None


def test_analyzers_handle_both_scripts():
    assert analyze("والمصابيح النحاسية") == analyze("مصابيح نحاسية") == ["مصابيح", "نحاس"]
    assert analyze("Lamps and Lighting") == ["lamp", "light"]
    assert query_language("ما هي قاعدة المنشأ") == "ar" and query_language("rule of origin") == "en"


# ---------- retrieval ---------------------------------------------------------------------------


def test_exact_code_lookup_includes_the_rule(retriever):
    assert retriever.exact("What is the duty for HS 9405.19?")[:2] == ["hs:940519000000", "psr_ch94"]


def test_bm25_finds_arabic_and_english(retriever):
    assert retriever.search("شالات صوف", k=1, mode="bm25")[0].chunk_id == "hs:621420100000"
    assert retriever.search("non electrical lamps", k=1, mode="bm25")[0].chunk_id == "hs:940550000000"


def test_rrf_without_vectors_degrades_to_keywords(retriever):
    assert not retriever.has_vectors
    hits = retriever.search("diamonds", k=3, mode="rrf", use_exact=False)
    assert hits and hits[0].chunk_id in ("hs:710239000000", "psr_7102")


def test_context_attaches_parents_and_rule(retriever):
    assert retriever.context_for("hs:940519000000") == ["hs:9405", "hs:94", "psr_ch94"]


def test_classify_hs_ranks_headings(retriever):
    cands = classify_hs(retriever, "wool shawls", mode="bm25")
    assert cands[0].heading == "6214" and 0 < cands[0].confidence <= 1


# ---------- agentic RAG ---------------------------------------------------------------------------


def test_planner_and_rewrites():
    assert plan("What is the rule of origin for brass lamps?") == ["psr"]
    assert plan("ما هي نسبة الرسوم على البند 9405") == ["duty", "hs"]
    assert plan("How long must documents be kept?") == ["procedure"]
    assert product_phrase("What is the rule of origin for brass lamps?") == "brass lamps"
    assert "certificate of origin" in rewrite("كيف تقدم شهادة المنشأ؟")


def test_psr_answer_is_cited_and_grounded(retriever):
    ans = answer_question_sync("What is the CEPA rule of origin for HS 9405.19?", retriever)
    assert any("CTH + VA 40%" in c.text and c.citations == ["psr_ch94"] for c in ans.claims)
    assert any("5 percentage points lower" in c.text for c in ans.claims)
    assert not ans.removed_claims and not ans.needs_human_check


def test_duty_answer_uses_the_published_rate(retriever):
    ans = answer_question_sync("What is the duty rate for HS 710239?", retriever)
    assert any(" is 0%" in c.text and c.citations == ["hs:710239000000"] for c in ans.claims)


def test_ex_rules_are_flagged_for_a_human(retriever):
    ans = answer_question_sync("What is the rule of origin for HS 2207?", retriever)
    assert ans.needs_human_check and "Ex" in ans.note


def test_procedure_answer_quotes_the_article(retriever):
    ans = answer_question_sync("What does the de minimis rule allow?", retriever)
    assert ans.claims and ans.claims[0].citations == ["cepa_final:3.4:0"]
    assert "10 per cent" in ans.claims[0].text                         # verbatim from the article


def test_grounding_removes_invented_numbers_and_uncited_claims(retriever):
    claims = [Claim(text="De minimis allows 15 per cent of FOB value.", citations=["cepa_final:3.4:0"]),
              Claim(text="Transport must be direct.", citations=["not-retrieved"]),
              Claim(text="De minimis allows 10 per cent of the FOB value.", citations=["cepa_final:3.4:0"])]
    kept, removed = ground(claims, retriever, {"cepa_final:3.4:0"})
    assert [c.text for c in kept] == ["De minimis allows 10 per cent of the FOB value."]
    assert {r.reason.split(":")[0] for r in removed} == {"numbers not in cited text", "no retrieved citation"}


def test_unanswerable_question_is_refused(retriever):
    ans = answer_question_sync("What is the corporate tax rate in Saudi Arabia?", retriever)
    assert ans.needs_human_check and not ans.claims
    assert [a.action for a in ans.attempts][:2] == ["initial", "rewrite"]      # it tried to self-correct first


def test_budget_is_enforced(retriever):
    ans = answer_question_sync("What is the corporate tax rate in Saudi Arabia?", retriever, Budget(max_searches=1))
    assert len(ans.attempts) == 1 and ans.needs_human_check


def test_evidence_follows_the_rule_components():
    needs = _evidence_for(components("CTH + VA 40%"))
    assert any("4-digit heading" in n for n in needs) and any("40% of the FOB" in n and "35%" in n for n in needs)


def test_glossary_bridges_seller_words_to_tariff_wording():
    from app.rag.trade_terms import expand, tariff_terms

    assert "non-electrical luminaires and lighting fittings" in tariff_terms("brass diya lamps")
    assert "table linen" in tariff_terms("cotton table runners")
    assert tariff_terms("حبوب الهيل الأخضر") == ["cardamoms spices"]        # Arabic article "ال" is allowed
    assert tariff_terms("hall") == [] and tariff_terms("مشال") == []          # no matches inside other words
    assert expand("granite slabs") == "granite slabs"                          # unknown goods are left alone


def test_planner_routes_products_certificates_and_rules():
    assert plan("Fresh or chilled carrots") == ["hs"]
    assert plan("كيف تقدم شهادة المنشأ إلى الجمارك؟") == ["procedure"]       # certificate of origin = procedure
    assert "psr" in plan("What is the rule of origin for HS 9405?")
    assert plan("Who won the cricket world cup in 2011?") == ["procedure"]


def test_agreement_chunker_labels_annex_pages(tmp_path, monkeypatch):
    from app.rag import ingest_docs

    pages = ["ARTICLE 18.5\nEntry into Force\nThis Agreement shall enter into force.\n" + "x " * 50,
             "Annex 8C-1\nANNEX 8C\nTelecommunication Services\nScope of the annex text here.\n" + "y " * 50]

    class FakePage:
        def __init__(self, text):
            self.text = text

        def extract_text(self):
            return self.text

    class FakeReader:
        def __init__(self, _path):
            self.pages = [FakePage(p) for p in pages]

    monkeypatch.setattr(ingest_docs, "PdfReader", FakeReader)
    src = Source(source_id="cepa_final", title="CEPA", issuing_body="MoET", document_date="2022-03-28", url="",
                 local_file="x.pdf")
    chunks = ingest_docs.chunk_agreement(tmp_path / "x.pdf", src)
    titles = {c.title: c for c in chunks}
    assert "ARTICLE 18.5 Entry into Force" in titles
    annex = titles["ANNEX 8C Telecommunication Services"]
    assert annex.chunk_id.startswith("cepa_final:annex8C:") and annex.meta["page_label"] == "Annex 8C-1"
    assert "Annex 8C-1" not in annex.text                                       # running label removed from text


def test_heading_claim_is_grounded_in_the_heading_passage(retriever):
    # "9405" is not a whole number inside line "940550000000"; the claim must also cite hs:9405 to survive.
    ans = answer_question_sync("non-electrical lamps", retriever)
    assert ans.intents == ["hs"]
    texts = [c.text for c in ans.claims]
    assert any(t.startswith("Candidate HS heading 9405") for t in texts), (texts, ans.removed_claims)
    assert all("hs:9405" in c.citations for c in ans.claims if c.text.startswith("Candidate HS heading 9405"))
