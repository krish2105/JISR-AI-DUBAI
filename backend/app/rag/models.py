"""
models.py — The knowledge base's building blocks: sources, tariff nodes, origin rules, text chunks.

Why this file exists:
    Every fact Jisr states must point back to an official document, a page or tariff line, and the document's
    date. These models carry that provenance from ingestion to the final cited answer.

    Tariff and rules of origin are TREES, not prose (v3 §22.3): a tariff line knows its parent subheading,
    heading and chapter; a product-specific rule knows the codes it covers. Prose documents (agreement articles,
    guides) are chunks on structural boundaries with page numbers.
"""

from typing import Literal

from pydantic import BaseModel, Field


class Source(BaseModel):
    """An official document from data/kb_sources/sources.csv."""

    source_id: str                         # stable id, e.g. "cepa_final"
    title: str
    issuing_body: str
    url: str
    document_date: str
    local_file: str
    sha256: str | None = None


class TariffNode(BaseModel):
    """One node of the UAE/GCC tariff tree (chapter 2 / heading 4 / subheading 6 / national 8 / line 12 digits)."""

    code: str                              # digits only, e.g. "94051900" or "940519000000"
    level: Literal["chapter", "heading", "subheading", "national", "line"]
    parent: str | None = None
    desc_en: str
    desc_ar: str = ""
    duty_pct: str | None = None            # as published ("5", "0", "Exempt", ...); None for non-leaf nodes
    unit: str | None = None
    old_code: str | None = None            # 8-digit code before the 2025 12-digit transition
    source_id: str


class OriginRule(BaseModel):
    """One product-specific rule (PSR) row of CEPA Annex 3B."""

    rule_id: str                           # e.g. "psr_ch94", "psr_7102", "psr_2007-2009"
    scope_text: str                        # as written: "Chapter 94", "Ex Chapter 87", "2201, 2202, Ex2206, 2209"
    chapters: list[int]                    # chapters the row belongs to
    codes: list[str] = Field(default_factory=list)   # explicit heading/subheading codes (digits), ranges expanded
    is_ex: bool = False                    # "Ex" = applies to part of the scope only
    description: str
    rule_text: str                         # canonical, e.g. "CTH + VA 40%"
    components: dict = Field(default_factory=dict)  # {"wo":bool,"cc":bool,"cth":bool,"ctsh":bool,"va_pct":40,...}
    page: int                              # PDF page number
    page_label: str                        # printed page label, e.g. "Annex 3B-9"
    source_id: str


class Chunk(BaseModel):
    """A retrievable passage: a tariff line, an origin rule or a span of a document."""

    chunk_id: str
    kind: Literal["tariff", "psr", "text"]
    source_id: str
    text: str                              # what is indexed and shown (original language)
    text_ar: str = ""                      # Arabic twin when the source is bilingual (tariff)
    title: str = ""                        # article / section heading
    page: int | None = None
    page_label: str | None = None
    code: str | None = None                # tariff code or rule id
    level: str | None = None
    parent: str | None = None
    meta: dict = Field(default_factory=dict)
