"""
ingest_tariff.py — Build the tariff TREE from the Dubai Customs Integrated Customs Tariff master (XLSX).

Why this file exists:
    The official master lists ~13,450 tariff lines with old 8-digit and new 12-digit codes, Arabic and English
    descriptions, statistical unit and duty percentage, but no chapter or heading rows. We rebuild the tree:
        chapter (2) -> heading (4) -> subheading (6) -> national line (8) -> 12-digit line
    Chapter titles come from the official CEPA Annex 3B table (same HS chapters); heading and subheading
    descriptions are summarised from their children ("Includes: ...") so they are searchable. Every node
    keeps the source id so answers can cite it.
"""

import re
from collections import defaultdict
from pathlib import Path

from openpyxl import load_workbook

from app.rag.models import TariffNode

SOURCE_ID = "uae_tariff_master"


def _digits(value) -> str:
    """Code as a digit string (Excel may give ints or strings)."""
    return re.sub(r"\D", "", str(value or ""))


def load_tariff(path: Path, chapter_titles: dict[int, str] | None = None) -> list[TariffNode]:
    """Read the XLSX and return all nodes (leaves + rebuilt parents)."""
    wb = load_workbook(path, read_only=True)
    ws = wb.active
    rows = ws.iter_rows(values_only=True)
    header = [str(h).strip() for h in next(rows)]
    col = {name: header.index(name) for name in header}
    leaves: list[TariffNode] = []
    for r in rows:
        if not r or not r[col["NewHSCode"]]:
            continue
        new, old = _digits(r[col["NewHSCode"]]), _digits(r[col["OldHSCode"]])
        if len(new) < 6:
            continue
        leaves.append(TariffNode(
            code=new, level="line", parent=old if len(old) == 8 else new[:6],
            desc_en=str(r[col["LongDescEn"]] or "").strip(), desc_ar=str(r[col["LongDescAr"]] or "").strip(),
            duty_pct=str(r[col["DutyPercentage"]]).strip() if r[col["DutyPercentage"]] is not None else None,
            unit=str(r[col["StatisticalQtyUnit"]] or "") or None, old_code=old or None, source_id=SOURCE_ID,
        ))
    wb.close()

    # Rebuild parents bottom-up with summarised descriptions.
    children: dict[str, list[TariffNode]] = defaultdict(list)
    for leaf in leaves:
        children[leaf.parent].append(leaf)
    nodes: dict[str, TariffNode] = {}
    for code8, kids in children.items():
        if len(code8) == 8:
            nodes[code8] = TariffNode(code=code8, level="national", parent=code8[:6], source_id=SOURCE_ID,
                                      desc_en=kids[0].desc_en, desc_ar=kids[0].desc_ar,
                                      duty_pct=kids[0].duty_pct if len({k.duty_pct for k in kids}) == 1 else None)
    def summarise(texts: list[str], limit: int = 6) -> str:
        """Short "Includes: a; b; c" summary of distinct child descriptions."""
        uniq = list(dict.fromkeys(t.rstrip(". ") for t in texts if t))
        return "; ".join(uniq[:limit]) + (" ..." if len(uniq) > limit else "")

    by6, by4, by2 = defaultdict(list), defaultdict(list), defaultdict(list)
    for leaf in leaves:
        by6[leaf.code[:6]].append(leaf)
        by4[leaf.code[:4]].append(leaf)
        by2[leaf.code[:2]].append(leaf)
    for code6, kids in by6.items():
        nodes[code6] = TariffNode(code=code6, level="subheading", parent=code6[:4], source_id=SOURCE_ID,
                                  desc_en="Includes: " + summarise([k.desc_en for k in kids]),
                                  desc_ar="يشمل: " + summarise([k.desc_ar for k in kids]))
    for code4, kids in by4.items():
        nodes[code4] = TariffNode(code=code4, level="heading", parent=code4[:2], source_id=SOURCE_ID,
                                  desc_en="Includes: " + summarise([k.desc_en for k in kids]),
                                  desc_ar="يشمل: " + summarise([k.desc_ar for k in kids]))
    titles = chapter_titles or {}
    for code2 in by2:
        title = titles.get(int(code2), "")
        nodes[code2] = TariffNode(code=code2, level="chapter", parent=None, source_id=SOURCE_ID,
                                  desc_en=(f"Chapter {int(code2)}: {title}" if title else f"Chapter {int(code2)}"),
                                  desc_ar=f"الفصل {int(code2)}")
    return list(nodes.values()) + leaves
