"""
citations.py — Turn a chunk id into a human-checkable citation (document, issuer, date, page, link).

Why this file exists:
    v3 rule 7: every compliance output carries its source and document date. Agents store resolved citations
    in the run state, so the dashboard, the audit trail and the replay all show exactly where a fact came from.
"""

from app.rag.index import KnowledgeBase


def resolve(kb: KnowledgeBase, chunk_id: str) -> dict:
    """Citation record for one chunk id (never raises: unknown ids are reported as such)."""
    chunk = kb.chunks.get(chunk_id)
    if chunk is None:
        return {"chunk_id": chunk_id, "title": "unknown source", "missing": True}
    source = kb.sources.get(chunk.source_id)
    return {
        "chunk_id": chunk_id,
        "kind": chunk.kind,
        "document": source.title if source else chunk.source_id,
        "issuer": source.issuing_body if source else "",
        "document_date": source.document_date if source else "",
        "url": source.url if source else "",
        "section": chunk.title or (f"HS {chunk.code}" if chunk.kind == "tariff" else chunk.code or ""),
        "page": chunk.page,
        "page_label": chunk.page_label,
        "excerpt": (chunk.text[:220] + ("…" if len(chunk.text) > 220 else "")),
        "excerpt_ar": chunk.text_ar[:160] if chunk.text_ar else "",
    }


def find_article(kb: KnowledgeBase, article: str) -> str | None:
    """First chunk id of a CEPA article, e.g. '3.12'."""
    prefix = f"ARTICLE {article} "
    return next((c.chunk_id for c in kb.chunks.values() if c.source_id == "cepa_final"
                 and (c.title or "").startswith(prefix)), None)


def first_chunk_of(kb: KnowledgeBase, source_id: str) -> str | None:
    """First chunk of a source (e.g. the DGFT CEPA certificate-of-origin trade notice)."""
    return next((c.chunk_id for c in kb.chunks.values() if c.source_id == source_id), None)
