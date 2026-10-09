"""
test_kb_real.py — Checks against the FULL local knowledge base (built by `make kb` from the official sources).

These tests skip automatically where the index is not built (CI, fresh clones): the sources and models are
local-only. They pin facts of the official texts so a parser change can never silently corrupt them.
"""

import pytest

from app.rag.index import INDEX_DIR

pytestmark = pytest.mark.skipif(not (INDEX_DIR / "meta.json").exists(),
                                reason="knowledge base not built here (run `make kb`)")


@pytest.fixture(scope="module")
def kb(monkeypatch_module=None):
    import os

    os.environ["KB_ENABLED"] = "true"
    from app.config import get_settings
    from app.rag.index import get_kb

    get_settings.cache_clear()
    get_kb.cache_clear()
    yield get_kb()
    os.environ["KB_ENABLED"] = "false"
    get_settings.cache_clear()


def test_annex_3b_covers_every_chapter_except_reserved_77(kb):
    chapters = {c for r in kb.rules if not r.codes for c in r.chapters}
    assert set(range(1, 98)) - chapters == {77}


@pytest.mark.parametrize("code, rule", [("940519", "CTH + VA 40%"), ("710239", "CTSH + VA 6%"),
                                        ("870321", "CTH + VA 45%"), ("442090", "CTSH + VA 40%"),
                                        ("621420", "CTH + VA 40%"), ("080132", "CTSH")])
def test_treaty_rules_are_parsed_exactly(kb, code, rule):
    from app.rag.ingest_psr import rule_for

    assert rule_for(code, kb.rules).rule_text == rule


def test_tariff_tree_is_complete_and_bilingual(kb):
    lines = [n for n in kb.tariff.values() if n.level == "line"]
    assert len(lines) > 13000 and all(n.desc_ar for n in lines[:200])
    assert kb.tariff["940519000000"].duty_pct == "5" and kb.tariff["9405"].level == "heading"


def test_pre_final_draft_is_never_indexed(kb):
    assert not any("PreFinal" in s.local_file for s in kb.sources.values())
    assert not any("UAE wants" in c.text or "UAE suggests" in c.text for c in kb.chunks.values())


def test_doc_pack_anchor_finds_the_customs_declaration_requirements(kb):
    from app.agents.trade_agents import _anchored_chunk

    cid = _anchored_chunk(kb, {"dubai_customs_services_guide_2025_v09"},
                          ["Import: AED15.00 - AED100.00",
                           "Required Documents - Invoice - Packing list - Certificate of Origin"])
    assert cid is not None and kb.chunks[cid].page == 17


def test_cepa_annex_pages_are_not_labelled_as_article_18_5(kb):
    annex = [c for c in kb.chunks.values() if c.source_id == "cepa_final" and c.title.startswith("ANNEX 8A")]
    assert annex and all(c.meta.get("page_label", "").startswith("Annex 8A") for c in annex if c.meta.get("page_label"))
    assert not [c for c in kb.chunks.values() if c.title.startswith("ARTICLE 18.5") and (c.page or 0) > 216]
