"""
retriever.py — Find the right official passages: exact codes, keywords, meaning, fusion, reranking, hierarchy.

Why this file exists:
    One retrieval step is never good enough for customs questions. This module offers composable stages so the
    agentic layer can choose, and so the evaluation can measure what each stage adds (ablation, v3 §22.2):

      exact      HS codes / "Chapter 94" written in the question are looked up directly (no guessing)
      bm25       keyword search with English + Arabic analysers (analyzers.py)
      vector     meaning search with multilingual-e5-large (Arabic and English share one space)
      rrf        Reciprocal Rank Fusion of bm25 + vector (score = sum 1 / (60 + rank))
      rerank     cross-encoder bge-reranker-v2-m3 re-scores the top candidates jointly with the question

    Tariff hits come with their context: parent levels and the chapter's CEPA origin rule (v3 §22.3).
    `classify_hs` ranks HS headings for a product description and reports top-3 with a confidence.
"""

import math
import re
from collections import defaultdict
from functools import lru_cache
from typing import Literal

import numpy as np
from pydantic import BaseModel, Field
from rank_bm25 import BM25Okapi

from app.rag.analyzers import analyze
from app.rag.index import EMBED_MODEL, MODEL_CACHE, RERANK_MODEL, KnowledgeBase, get_kb
from app.rag.ingest_psr import rule_for
from app.rag.models import Chunk

Mode = Literal["bm25", "vector", "rrf", "rrf_rerank"]
RRF_K = 60
CODE_RE = re.compile(r"(?<!\d)(\d{4}(?:[.\s]?\d{2}){0,4})(?!\d)")
CHAPTER_RE = re.compile(r"\bchapter\s+(\d{1,2})\b|الفصل\s+(\d{1,2})", re.I)


class Hit(BaseModel):
    """One retrieved passage with the scores that put it there."""

    chunk_id: str
    score: float
    stages: dict[str, float] = Field(default_factory=dict)


class Retriever:
    """All retrieval stages over one loaded knowledge base."""

    def __init__(self, kb: KnowledgeBase) -> None:
        self.kb = kb
        self.ids = list(kb.chunks)
        self.bm25 = BM25Okapi([analyze(f"{c.title} {c.text} {c.text_ar}") for c in kb.chunks.values()])
        self.vec_index = {cid: i for i, cid in enumerate(kb.vector_ids)}
        self._embedder = None
        self._reranker = None
        self.hs_cache: dict[tuple, object] = {}          # deterministic results reused across runs (same goods recur)

    # ---------------- model loading (lazy: only if a stage needs it) ----------------

    @property
    def embedder(self):
        if self._embedder is None:
            from fastembed import TextEmbedding

            self._embedder = TextEmbedding(EMBED_MODEL, cache_dir=MODEL_CACHE)
        return self._embedder

    @property
    def reranker(self):
        if self._reranker is None:
            from fastembed.rerank.cross_encoder import TextCrossEncoder

            self._reranker = TextCrossEncoder(RERANK_MODEL, cache_dir=MODEL_CACHE)
        return self._reranker

    @property
    def has_vectors(self) -> bool:
        return self.kb.vectors is not None and len(self.kb.vector_ids) > 0

    # ---------------- stages ----------------

    def _allowed(self, cid: str, kinds: set[str] | None, levels: set[str] | None,
                 sources: set[str] | None = None) -> bool:
        c = self.kb.chunks[cid]
        return ((kinds is None or c.kind in kinds) and (levels is None or c.kind != "tariff" or c.level in levels)
                and (sources is None or c.source_id in sources))

    def exact(self, query: str) -> list[str]:
        """Chunk ids for HS codes or chapters written in the query (most specific first)."""
        found: list[str] = []
        for raw in CODE_RE.findall(query):
            digits = re.sub(r"\D", "", raw)
            node = self.tariff_node_for(digits)
            if node:
                found.append(f"hs:{node}")
            rule = rule_for(digits, self.kb.rules) if len(digits) >= 4 else None
            if rule:
                found.append(rule.rule_id)
        for m in CHAPTER_RE.finditer(query):
            ch = int(m.group(1) or m.group(2))
            found += [f"hs:{ch:02d}"] if f"{ch:02d}" in self.kb.tariff else []
            found += [r.rule_id for r in self.kb.rules if not r.codes and ch in r.chapters]
        return [cid for cid in dict.fromkeys(found) if cid in self.kb.chunks]

    def tariff_node_for(self, digits: str) -> str | None:
        """Most specific tariff node for a written code ('9405.19' -> the subheading, or its first line)."""
        for length in (12, 10, 8, 6):
            code = digits[:length]
            if len(code) == length and code in self.kb.tariff:
                return code
        if len(digits) >= 6:                                   # e.g. 6 digits when only 12-digit lines exist
            lines = sorted(c for c in self.kb.tariff if c.startswith(digits[:6]) and len(c) > 6)
            if lines:
                return lines[0]
        return digits[:4] if digits[:4] in self.kb.tariff else None

    def bm25_search(self, query: str, k: int = 50, kinds: set[str] | None = None,
                    levels: set[str] | None = None, sources: set[str] | None = None) -> list[Hit]:
        """Keyword search (English + Arabic analysers)."""
        scores = self.bm25.get_scores(analyze(query))
        order = np.argsort(-scores)
        hits = []
        for i in order:
            if scores[i] <= 0 or len(hits) >= k:
                break
            cid = self.ids[i]
            if self._allowed(cid, kinds, levels, sources):
                hits.append(Hit(chunk_id=cid, score=float(scores[i]), stages={"bm25": float(scores[i])}))
        return hits

    def vector_search(self, query: str, k: int = 50, kinds: set[str] | None = None,
                      levels: set[str] | None = None, sources: set[str] | None = None) -> list[Hit]:
        """Meaning search with the multilingual embedding model ('query: ' prefix as e5 expects)."""
        if not self.has_vectors:
            return []
        q = np.array(next(iter(self.embedder.embed([f"query: {query}"]))), dtype=np.float32)
        q /= np.linalg.norm(q) + 1e-12
        sims = self.kb.vectors @ q
        hits = []
        for i in np.argsort(-sims):
            if len(hits) >= k:
                break
            cid = self.kb.vector_ids[i]
            if self._allowed(cid, kinds, levels, sources):
                hits.append(Hit(chunk_id=cid, score=float(sims[i]), stages={"vector": float(sims[i])}))
        return hits

    @staticmethod
    def rrf(*ranked: list[Hit]) -> list[Hit]:
        """Reciprocal Rank Fusion: robust to the very different score scales of BM25 and cosine."""
        fused: dict[str, Hit] = {}
        for hits in ranked:
            for rank, h in enumerate(hits, start=1):
                hit = fused.setdefault(h.chunk_id, Hit(chunk_id=h.chunk_id, score=0.0))
                hit.score += 1.0 / (RRF_K + rank)
                hit.stages.update(h.stages)
        return sorted(fused.values(), key=lambda h: -h.score)

    def rerank(self, query: str, hits: list[Hit], top: int = 8) -> list[Hit]:
        """Cross-encoder re-scoring of the candidates (probability-like score via a sigmoid)."""
        if not hits:
            return []
        texts = [self._passage_text(self.kb.chunks[h.chunk_id]) for h in hits]
        scores = list(self.reranker.rerank(query, texts))
        rescored = []
        for h, s in zip(hits, scores, strict=True):
            p = 1.0 / (1.0 + math.exp(-float(s)))
            rescored.append(Hit(chunk_id=h.chunk_id, score=p, stages={**h.stages, "rerank": p}))
        return sorted(rescored, key=lambda h: -h.score)[:top]

    @staticmethod
    def _passage_text(c: Chunk) -> str:
        return f"{c.title}. {c.text} {c.text_ar}".strip(" .")[:1500]

    # ---------------- composition ----------------

    def search(self, query: str, k: int = 8, mode: Mode = "rrf_rerank", kinds: set[str] | None = None,
               levels: set[str] | None = None, candidates: int = 50, use_exact: bool = True,
               sources: set[str] | None = None) -> list[Hit]:
        """One search with the chosen pipeline; exact-code hits always lead when present.

        `sources` limits the search to some documents BEFORE reranking (reranking is the expensive stage).
        """
        exact = [Hit(chunk_id=cid, score=1.0, stages={"exact": 1.0}) for cid in (self.exact(query) if use_exact else [])
                 if self._allowed(cid, kinds, levels, sources)]
        if mode == "bm25":
            ranked = self.bm25_search(query, candidates, kinds, levels, sources)
        elif mode == "vector":
            ranked = (self.vector_search(query, candidates, kinds, levels, sources)
                      or self.bm25_search(query, candidates, kinds, levels, sources))
        else:
            ranked = self.rrf(self.bm25_search(query, candidates, kinds, levels, sources),
                              self.vector_search(query, candidates, kinds, levels, sources))
            if mode == "rrf_rerank":
                ranked = self.rerank(query, ranked[:30], top=max(k, 10))
        seen = {h.chunk_id for h in exact}
        return (exact + [h for h in ranked if h.chunk_id not in seen])[:k]

    def context_for(self, chunk_id: str) -> list[str]:
        """Parent tariff levels and the applicable CEPA rule for a tariff hit (v3: always attach parents)."""
        c = self.kb.chunks[chunk_id]
        if c.kind != "tariff":
            return []
        out, parent = [], c.parent
        while parent:
            if f"hs:{parent}" in self.kb.chunks:
                out.append(f"hs:{parent}")
            node = self.kb.tariff.get(parent)
            parent = node.parent if node else None
        rule = rule_for(c.code or "", self.kb.rules)
        if rule:
            out.append(rule.rule_id)
        return out


class HSCandidate(BaseModel):
    """One HS classification candidate."""

    heading: str
    heading_desc: str
    best_line: str
    best_line_desc: str
    duty_pct: str | None
    score: float
    confidence: float                          # share among the top candidates (relative)
    best_score: float = 0.0                    # the best line's own score (reranker probability in rrf_rerank)
    mode: str = "bm25"
    chunk_ids: list[str]


def classify_hs(retriever: Retriever, description: str, top: int = 3, mode: Mode | None = None,
                prior_heading: str | None = None) -> list[HSCandidate]:
    """Rank 4-digit headings for a product description: retrieve tariff lines, aggregate by heading.

    mode defaults to rrf_rerank when vectors exist (the cross-encoder separates 'lamp' from 'bulb').
    prior_heading (e.g. the seller catalogue's HS hint) adds that heading's best-matching lines to the
    candidates; it is a labelled prior, never a verdict: the tariff text still has to match.
    """
    from app.rag.trade_terms import expand

    mode = mode or ("rrf_rerank" if retriever.has_vectors else "bm25")
    key = (description.strip().lower(), top, mode, prior_heading)
    if key in retriever.hs_cache:                    # deterministic, so a cached answer is the same answer
        return [c.model_copy(deep=True) for c in retriever.hs_cache[key]]
    query = expand(description)                      # seller words + the tariff's own vocabulary
    hits = retriever.search(query, k=40, mode=mode, kinds={"tariff"}, levels={"line", "national"},
                            use_exact=True)
    if prior_heading:
        prior_hits = [h for h in retriever.search(f"{description} {prior_heading}", k=200, mode="bm25",
                                                  kinds={"tariff"}, levels={"line"}, use_exact=False)
                      if (retriever.kb.chunks[h.chunk_id].code or "").startswith(prior_heading)][:5]
        if mode == "rrf_rerank" and prior_hits:
            prior_hits = retriever.rerank(query, prior_hits, top=5)
        known = {h.chunk_id for h in hits}
        hits += [h for h in prior_hits if h.chunk_id not in known]
    by_heading: dict[str, list[Hit]] = defaultdict(list)
    for h in hits:
        code = retriever.kb.chunks[h.chunk_id].code or ""
        by_heading[code[:4]].append(h)
    scored = []
    for heading, hs in by_heading.items():
        # best line counts most; extra supporting lines add a little (avoids one stray match winning)
        s = hs[0].score + 0.25 * sum(h.score for h in hs[1:4])
        scored.append((s, heading, hs))
    scored.sort(key=lambda x: -x[0])
    total = sum(s for s, _, _ in scored[: max(top, 3)]) or 1.0
    out = []
    for s, heading, hs in scored[:top]:
        best = retriever.kb.chunks[hs[0].chunk_id]
        node = retriever.kb.tariff.get(heading)
        out.append(HSCandidate(heading=heading, heading_desc=node.desc_en if node else "", best_line=best.code or "",
                               best_line_desc=best.text, duty_pct=best.meta.get("duty_pct"), score=round(s, 4),
                               confidence=round(s / total, 3), best_score=round(hs[0].score, 4), mode=mode,
                               chunk_ids=[h.chunk_id for h in hs[:3]]))
    if len(retriever.hs_cache) < 5000:
        retriever.hs_cache[key] = [c.model_copy(deep=True) for c in out]
    return out


@lru_cache
def get_retriever() -> Retriever:
    """Shared retriever (BM25 built once per process, models loaded on first use)."""
    return Retriever(get_kb())
