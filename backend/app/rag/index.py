"""
index.py — Build and load the knowledge-base index (chunks, tariff tree, origin rules, vectors).

Why this file exists:
    `make kb` runs once after the official sources are downloaded. It ingests everything, embeds the passages
    with the multilingual model, and writes plain files to data/kb_index/ (git-ignored, rebuilt from sources):
        chunks.jsonl        every retrievable passage (tariff, psr, text) with provenance
        tariff.jsonl        all tariff tree nodes (for exact-code lookup and parents)
        psr.json            parsed CEPA Annex 3B rules + the Rule 1 definitions
        vectors.npy         normalised embeddings for the embedded chunks (float32)
        vector_ids.json     chunk ids in the same order as vectors.npy
        meta.json           model, build time, counts and the SHA-256 of every source used
    At runtime `get_kb()` loads it once (BM25 is rebuilt in memory in a few seconds).

The vector store is a numpy matrix behind a small interface; Phase 10 can move it to pgvector unchanged.
"""

import hashlib
import json
import os
import time
from datetime import UTC, datetime
from functools import lru_cache

import numpy as np
from pydantic import BaseModel

from app.rag.ingest_docs import KB_DIR, load_document_chunks, load_sources
from app.rag.ingest_psr import parse_annex_3b
from app.rag.ingest_tariff import load_tariff
from app.rag.models import Chunk, OriginRule, Source, TariffNode

INDEX_DIR = KB_DIR.parent / "kb_index"
EMBED_MODEL = "intfloat/multilingual-e5-large"
RERANK_MODEL = "BAAI/bge-reranker-v2-m3-int8"
MODEL_CACHE = os.path.expanduser(os.environ.get("FASTEMBED_CACHE", "~/.cache/fastembed"))
EMBED_LEVELS = {"line", "heading", "chapter"}                # tariff levels that get a vector


def tariff_chunk(node: TariffNode) -> Chunk:
    """A tariff node as a retrievable chunk (English text + Arabic twin)."""
    duty = f" | duty {node.duty_pct}%" if node.duty_pct not in (None, "", "None") else ""
    return Chunk(chunk_id=f"hs:{node.code}", kind="tariff", source_id=node.source_id,
                 text=f"HS {node.code} {node.desc_en}{duty}", text_ar=node.desc_ar, code=node.code,
                 level=node.level, parent=node.parent,
                 meta={"duty_pct": node.duty_pct, "unit": node.unit, "old_code": node.old_code})


def psr_chunk(rule: OriginRule) -> Chunk:
    """An Annex 3B rule as a retrievable chunk."""
    text = (f"CEPA Annex 3B product specific rule for {rule.scope_text}: {rule.description}. "
            f"Rule: {rule.rule_text}.")
    return Chunk(chunk_id=rule.rule_id, kind="psr", source_id=rule.source_id, text=text, code=rule.rule_id,
                 page=rule.page, page_label=rule.page_label, meta={"rule_text": rule.rule_text,
                                                                   "chapters": rule.chapters, "codes": rule.codes,
                                                                   "is_ex": rule.is_ex})


def embed_text(c: Chunk) -> str:
    """The exact text a chunk is embedded with (e5 'passage: ' prefix; titles are not embedded)."""
    return f"passage: {c.text} {c.text_ar}".strip()


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _previous_vectors() -> dict[str, np.ndarray]:
    """Vectors of the previous build keyed by the hash of their embedding text (the embedding cache).

    Re-ingesting usually changes ids or titles but not passage text (e.g. a fixed section label), so a rebuild
    only embeds new or changed text. Same model only: the cache is ignored if meta.json names another model.
    """
    try:
        meta = json.loads((INDEX_DIR / "meta.json").read_text(encoding="utf-8"))
        if meta.get("embed_model") != EMBED_MODEL:
            return {}
        ids = json.loads((INDEX_DIR / "vector_ids.json").read_text(encoding="utf-8"))
        vectors = np.load(INDEX_DIR / "vectors.npy")
        texts = {}
        with (INDEX_DIR / "chunks.jsonl").open(encoding="utf-8") as fh:
            for line in fh:
                c = Chunk.model_validate_json(line)
                texts[c.chunk_id] = embed_text(c)
    except (OSError, ValueError):
        return {}
    return {_text_hash(texts[cid]): vectors[i] for i, cid in enumerate(ids) if cid in texts}


def build(embed: bool = True, log=print) -> dict:
    """Ingest all sources and write data/kb_index/. Returns the meta dictionary."""
    started = time.time()
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    cache = _previous_vectors() if embed else {}               # read before the old files are overwritten
    (INDEX_DIR / "meta.json").unlink(missing_ok=True)          # meta.json is the completion marker
    sources = load_sources()
    cepa = KB_DIR / "downloads" / "India_UAE_CEPA_Final_Agreement_MoET.pdf"
    rules, definitions, titles = parse_annex_3b(cepa)
    log(f"Annex 3B: {len(rules)} rules")
    nodes = load_tariff(KB_DIR / "downloads" / "GCC_Integrated_Customs_Tariff_Master_12_digit.xlsx", titles)
    log(f"Tariff: {len(nodes)} nodes")
    docs = load_document_chunks(sources)
    log(f"Documents: {len(docs)} chunks from {len(sources)} sources")

    definitions_chunk = Chunk(chunk_id="psr_rule1", kind="text", source_id="cepa_final", text=definitions,
                              title="Annex 3B Rule 1 Definitions", page=rules[0].page if rules else None,
                              page_label="Annex 3B-1")
    chunks = [tariff_chunk(n) for n in nodes] + [psr_chunk(r) for r in rules] + [definitions_chunk] + docs
    with (INDEX_DIR / "chunks.jsonl").open("w", encoding="utf-8") as fh:
        for c in chunks:
            fh.write(c.model_dump_json() + "\n")
    with (INDEX_DIR / "tariff.jsonl").open("w", encoding="utf-8") as fh:
        for n in nodes:
            fh.write(n.model_dump_json() + "\n")
    (INDEX_DIR / "psr.json").write_text(json.dumps({"definitions": definitions,
                                                    "rules": [r.model_dump() for r in rules]},
                                                   ensure_ascii=False), encoding="utf-8")
    (INDEX_DIR / "sources.json").write_text(json.dumps([s.model_dump() for s in sources], ensure_ascii=False),
                                            encoding="utf-8")

    to_embed = [c for c in chunks if c.kind != "tariff" or c.level in EMBED_LEVELS]
    if embed:
        from fastembed import TextEmbedding

        texts = [embed_text(c) for c in to_embed]
        hashes = [_text_hash(t) for t in texts]
        missing = [i for i, h in enumerate(hashes) if h not in cache]
        log(f"Embedding {len(missing)} new passages with {EMBED_MODEL} ({len(texts) - len(missing)} reused from cache; "
            f"~{len(missing) / 9 / 60:.0f} min on CPU)...")
        if missing:
            model = TextEmbedding(EMBED_MODEL, cache_dir=MODEL_CACHE)
            fresh = np.array(list(model.embed([texts[i] for i in missing], batch_size=32)), dtype=np.float32)
            fresh /= np.linalg.norm(fresh, axis=1, keepdims=True) + 1e-12
            for i, v in zip(missing, fresh, strict=True):
                cache[hashes[i]] = v
        vectors = np.stack([cache[h] for h in hashes]).astype(np.float32)
        np.save(INDEX_DIR / "vectors.npy", vectors)
        (INDEX_DIR / "vector_ids.json").write_text(json.dumps([c.chunk_id for c in to_embed]), encoding="utf-8")
    meta = {"built_at": datetime.now(UTC).isoformat(timespec="seconds"), "embed_model": EMBED_MODEL if embed else None,
            "counts": {"chunks": len(chunks), "tariff_nodes": len(nodes), "psr_rules": len(rules),
                       "doc_chunks": len(docs), "vectors": len(to_embed) if embed else 0},
            "sources": {s.source_id: {"sha256": s.sha256, "document_date": s.document_date} for s in sources},
            "seconds": round(time.time() - started, 1)}
    (INDEX_DIR / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    log(f"Index written to {INDEX_DIR} in {meta['seconds']} s")
    return meta


class KnowledgeBase(BaseModel):
    """Everything loaded from data/kb_index/, ready for retrieval."""

    model_config = {"arbitrary_types_allowed": True}

    chunks: dict[str, Chunk]
    tariff: dict[str, TariffNode]
    rules: list[OriginRule]
    definitions: str
    sources: dict[str, Source]
    vectors: np.ndarray | None = None
    vector_ids: list[str] = []
    meta: dict = {}


def index_exists() -> bool:
    """True when a COMPLETE index is available and the knowledge base is enabled.

    meta.json is written last by build(), so it marks a finished build (a half-built index is ignored).
    KB_ENABLED=false (unit tests) makes agents behave as if no knowledge base were present.
    """
    from app.config import get_settings

    return get_settings().kb_enabled and (INDEX_DIR / "meta.json").exists()


@lru_cache
def get_kb() -> KnowledgeBase:
    """Load the built index once per process."""
    if not index_exists():
        raise FileNotFoundError("Knowledge base index not found: run `make kb` after downloading the sources.")
    chunks = {c.chunk_id: c for c in (Chunk.model_validate_json(line) for line in
                                      (INDEX_DIR / "chunks.jsonl").read_text(encoding="utf-8").splitlines())}
    tariff = {n.code: n for n in (TariffNode.model_validate_json(line) for line in
                                  (INDEX_DIR / "tariff.jsonl").read_text(encoding="utf-8").splitlines())}
    psr = json.loads((INDEX_DIR / "psr.json").read_text(encoding="utf-8"))
    sources = {s["source_id"]: Source(**s) for s in json.loads((INDEX_DIR / "sources.json").read_text("utf-8"))}
    vectors, ids = None, []
    if (INDEX_DIR / "vectors.npy").exists():
        vectors = np.load(INDEX_DIR / "vectors.npy")
        ids = json.loads((INDEX_DIR / "vector_ids.json").read_text(encoding="utf-8"))
    return KnowledgeBase(chunks=chunks, tariff=tariff, rules=[OriginRule(**r) for r in psr["rules"]],
                         definitions=psr["definitions"], sources=sources, vectors=vectors, vector_ids=ids,
                         meta=json.loads((INDEX_DIR / "meta.json").read_text(encoding="utf-8")))


if __name__ == "__main__":
    build(embed=os.environ.get("KB_EMBED", "1") != "0")
