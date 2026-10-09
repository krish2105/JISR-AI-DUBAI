"""
ingest_docs.py — Turn the official documents into citable chunks with page numbers and document dates.

Why this file exists:
    Answers about procedures ("which certificate of origin?", "what documents does Dubai Customs need?") come
    from prose documents. We split them on STRUCTURAL boundaries, never mid-sentence by a fixed character
    count, so each chunk is a meaningful unit a human can check:
        the CEPA agreement      by ARTICLE (title kept), long articles split into parts with the title repeated
        other PDFs              by page, then by paragraph groups (~1,200 characters)
        HTML pages / snapshots  boilerplate stripped, then paragraph groups
    The table of contents and the Abu Dhabi Customs pre-final copy are excluded (the latter must never be cited).
"""

import csv
import html
import re
from pathlib import Path

from pypdf import PdfReader

from app.rag.models import Chunk, Source

KB_DIR = Path(__file__).resolve().parents[3] / "data" / "kb_sources"
EXCLUDED = {"downloads/India_UAE_CEPA_AbuDhabiCustoms_PreFinal_Copy.pdf"}   # pre-final draft: never cite
TARGET_CHARS = 1200


def source_id_for(local_file: str) -> str:
    """Stable id from a file name, e.g. 'downloads/India_UAE_CEPA_Final_Agreement_MoET.pdf' -> 'cepa_final'."""
    special = {"India_UAE_CEPA_Final_Agreement_MoET": "cepa_final",
               "GCC_Integrated_Customs_Tariff_Master_12_digit": "uae_tariff_master"}
    stem = Path(local_file).stem
    return special.get(stem, re.sub(r"[^a-z0-9]+", "_", stem.lower()).strip("_")[:60])


def load_sources() -> list[Source]:
    """Sources from the manifest that exist locally (with their SHA-256 from the download report)."""
    status = {}
    status_file = KB_DIR / "download_status.csv"
    if status_file.exists():
        status = {r["local_filename"]: r for r in csv.DictReader(status_file.open(encoding="utf-8"))}
    out = []
    for row in csv.DictReader((KB_DIR / "sources.csv").open(encoding="utf-8-sig")):
        local = row["local_filename"]
        if local in EXCLUDED or not (KB_DIR / local).exists():
            continue
        out.append(Source(source_id=source_id_for(local), title=row["title"], issuing_body=row["issuing_body"],
                          url=row["url"], document_date=row["document_date"], local_file=local,
                          sha256=status.get(local, {}).get("sha256") or None))
    return out


def _paragraph_groups(text: str) -> list[str]:
    """Group paragraphs into ~TARGET_CHARS pieces without cutting sentences."""
    paras = [p.strip() for p in re.split(r"\n\s*\n|(?<=[.:;])\n(?=[A-Z0-9(•\-])", text) if p.strip()]
    groups, buf = [], ""
    for p in paras:
        p = re.sub(r"\s+", " ", p)
        if buf and len(buf) + len(p) > TARGET_CHARS:
            groups.append(buf)
            buf = p
        else:
            buf = f"{buf} {p}".strip()
    if buf:
        groups.append(buf)
    # split any very long group at sentence boundaries
    out = []
    for g in groups:
        while len(g) > 2 * TARGET_CHARS:
            cut = g.rfind(". ", 0, TARGET_CHARS + 300)
            cut = cut + 1 if cut > 200 else TARGET_CHARS
            out.append(g[:cut].strip())
            g = g[cut:].strip()
        out.append(g)
    return out


def _is_toc(text: str) -> bool:
    """Table-of-contents pages are full of dot leaders."""
    return len(re.findall(r"\.{6,}", text)) >= 5


def chunk_agreement(path: Path, source: Source) -> list[Chunk]:
    """CEPA agreement split by ARTICLE and ANNEX headings with page numbers.

    Annex 3B (the PSR table) is parsed by ingest_psr instead. Annexes also sit inside chapters (3A-3E follow
    Chapter 3), so an ANNEX heading ends the current article exactly like the next ARTICLE heading does;
    otherwise annex pages would be labelled with the last article before them.
    """
    reader = PdfReader(str(path))
    spans: list[tuple[int, str, str | None]] = []        # (page, text, running label) without TOC and Annex 3B pages
    for number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if _is_toc(text) or re.search(r"Annex 3B-\d+", text):
            continue
        label = re.search(r"(?m)^\s*(Annex\s+\d+[A-Z]-\d+|\d+-\d+)\s*$", text)
        text = re.sub(r"(?m)^\s*(Annex\s+\d+[A-Z]-\d+|\d+-\d+)\s*$", "", text)   # drop running page labels
        spans.append((number, text, label.group(1) if label else None))
    chunks: list[Chunk] = []
    current_title, current_key, buf = "Preamble", "pre", ""
    current_page, current_label = (spans[0][0] if spans else 1), None
    heading_re = re.compile(r"\n\s*(ARTICLE\s+(\d+\.\d+)|ANNEX\s+(\d+[A-Z]))\s*\n\s*([^\n]{3,90})\n")

    def flush() -> None:
        for i, piece in enumerate(_paragraph_groups(buf)):
            chunks.append(Chunk(chunk_id=f"{source.source_id}:{current_key}:{i}", kind="text",
                                source_id=source.source_id, text=piece, title=current_title, page=current_page,
                                meta={"part": i, **({"page_label": current_label} if current_label else {})}))

    for number, text, label in spans:
        pos = 0
        for m in heading_re.finditer("\n" + text):
            buf += text[pos:max(0, m.start() - 1)]
            if buf.strip():
                flush()
            article, annex = m.group(2), m.group(3)
            current_key = article if article else f"annex{annex}"
            current_title = f"{'ARTICLE ' + article if article else 'ANNEX ' + annex} {m.group(4).strip()}"
            current_page, current_label, buf = number, label, ""
            pos = m.end() - 1
        buf += text[pos:]
    if buf.strip():
        flush()
    return chunks


def chunk_pdf(path: Path, source: Source) -> list[Chunk]:
    """Page-aware paragraph groups for guides and notices."""
    reader = PdfReader(str(path))
    chunks = []
    for number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if len(text.strip()) < 80 or _is_toc(text):
            continue
        for i, piece in enumerate(_paragraph_groups(text)):
            chunks.append(Chunk(chunk_id=f"{source.source_id}:p{number}:{i}", kind="text", source_id=source.source_id,
                                text=piece, title=source.title, page=number))
    return chunks


def html_to_text(raw: str) -> str:
    """Visible text of an HTML page: scripts, styles, navigation and footers removed."""
    raw = re.sub(r"(?is)<(script|style|noscript|svg|nav|footer|header)\b.*?</\1>", " ", raw)
    raw = re.sub(r"(?i)<br\s*/?>|</(p|div|li|h\d|tr)>", "\n", raw)
    text = html.unescape(re.sub(r"<[^>]+>", " ", raw))
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in text.splitlines()]
    return "\n\n".join(ln for ln in lines if len(ln) > 40)          # drop menu fragments


def chunk_text_file(path: Path, source: Source) -> list[Chunk]:
    """HTML snapshots and text snapshots."""
    raw = path.read_text(encoding="utf-8", errors="replace")
    text = html_to_text(raw) if path.suffix.lower() in (".html", ".htm") else raw.split("---", 1)[-1]
    return [Chunk(chunk_id=f"{source.source_id}:t{i}", kind="text", source_id=source.source_id, text=piece,
                  title=source.title) for i, piece in enumerate(_paragraph_groups(text))]


def load_document_chunks(sources: list[Source]) -> list[Chunk]:
    """Chunks for every prose source (the tariff XLSX is handled by ingest_tariff)."""
    chunks: list[Chunk] = []
    for src in sources:
        path = KB_DIR / src.local_file
        if path.suffix.lower() == ".xlsx":
            continue
        if src.source_id == "cepa_final":
            chunks += chunk_agreement(path, src)
        elif path.suffix.lower() == ".pdf":
            chunks += chunk_pdf(path, src)
        else:
            chunks += chunk_text_file(path, src)
    return chunks
