"""
ingest_psr.py — Parse CEPA Annex 3B (Product Specific Rules) from the Final Agreement PDF into structured rules.

Why this file exists:
    "Does this product qualify for CEPA preference?" depends on the exact product-specific rule (PSR) for its
    HS code: WO (wholly obtained), CC / CTH / CTSH (change of chapter / heading / subheading), VA x% (value
    addition, FOB basis; 5 points lower on an Ex-Works basis per Rule 1), SO (specific operations), or
    alternatives. We parse the table into rules a calculator can apply and an answer can cite (page label).

PDF text quirks handled:
    descriptions wrap over several lines; the rule can appear in the MIDDLE of a wrapped description;
    scopes can be chapters ("Chapter 94", "Ex Chapter 87"), codes ("1302", "080132"), lists
    ("2201, 2202, Ex2206, 2209", possibly over two lines) or ranges ("2007-2009").
"""

import re
from pathlib import Path

from pypdf import PdfReader

from app.rag.models import OriginRule

SOURCE_ID = "cepa_final"

SCOPE_START = re.compile(r"^\s*(?:(Ex\s*)?Chapter\s+(\d{1,2})\b|((?:Ex\s*)?\d{4}(?:\d{2})?(?:\s*-\s*\d{4,6})?)(?=[\s,]))")
CODE_ONLY_LINE = re.compile(r"^\s*(?:(?:Ex\s*)?\d{4}(?:\d{2})?(?:\s*-\s*\d{4,6})?\s*,?\s*)+$")
RULE_RE = re.compile(
    r"\(?\s*Melt[^)]*\)\s*or\s*\(\s*CTS?H\s*\+\s*VA\s*\d+\s*%\s*\)"            # (Melt, cast and rolled) or (CTSH + VA 40%)
    r"|Melt\s+and\s+pour"
    r"|\b(?:WO|CC|CTH|CTSH|SO)\b(?:\s*\+\s*VA\s*\d+\s*%)?(?:\s*(?:or|/)\s*(?:WO|CC|CTH|CTSH|SO)\b(?:\s*\+\s*VA\s*\d+\s*%)?)*",
    re.I)


def canonical_rule(raw: str) -> str:
    """'CTSH +VA40 %' -> 'CTSH + VA 40%'."""
    r = re.sub(r"\s+", " ", raw.strip())
    r = re.sub(r"\s*\+\s*", " + ", r)
    r = re.sub(r"VA\s*(\d+)\s*%", r"VA \1%", r, flags=re.I)
    return r


def components(rule: str) -> dict:
    """Machine-usable parts of a rule string."""
    up = rule.upper()
    va = re.findall(r"VA\s*(\d+)\s*%", up)
    return {
        "wo": bool(re.search(r"\bWO\b", up)), "cc": bool(re.search(r"\bCC\b", up)),
        "cth": bool(re.search(r"\bCTH\b", up)), "ctsh": bool(re.search(r"\bCTSH\b", up)),
        "so": bool(re.search(r"\bSO\b", up)), "melt": "MELT" in up,
        "va_pct": int(va[0]) if va else None, "has_alternatives": " OR " in up,
    }


def _expand_codes(scope: str) -> tuple[list[str], bool]:
    """'2201, 2202, Ex2206' -> ['2201','2202','2206'] (+ is_ex); '2007-2009' -> ['2007','2008','2009']."""
    is_ex = bool(re.search(r"\bEx", scope, re.I))
    codes: list[str] = []
    for part in re.findall(r"\d{4,6}(?:\s*-\s*\d{4,6})?", scope):
        if "-" in part:
            a, b = (int(x) for x in re.split(r"\s*-\s*", part))
            codes += [str(c).zfill(len(part.split("-")[0].strip())) for c in range(a, b + 1)] if b - a < 50 else [str(a)]
        else:
            codes.append(part)
    return codes, is_ex


def parse_annex_3b(pdf_path: Path) -> tuple[list[OriginRule], str, dict[int, str]]:
    """Return (rules, Rule-1 definitions text, chapter titles) from the Final Agreement PDF."""
    reader = PdfReader(str(pdf_path))
    pages: list[tuple[int, str, str]] = []
    for number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        label = re.search(r"Annex 3B-\d+", text)
        if label and "Product Specific" in text or (label and pages):
            pages.append((number, label.group(0) if label else "", text))
        elif pages:
            break
    definitions = ""
    entries: list[dict] = []
    current: dict | None = None
    for number, label, text in pages:
        lines = text.splitlines()
        if not definitions and "Rule 1" in text:
            start = text.find("Rule 1")
            end = text.find("TABLE 1")
            definitions = re.sub(r"\s+", " ", text[start:end]).strip()
            lines = text[end:].splitlines()[1:] if end > 0 else lines
        for line in lines:
            if re.match(r"^\s*(Annex 3B-\d+|HS Code Description|Rule \(PSR\)|TABLE 1)", line) or not line.strip():
                continue
            if current and CODE_ONLY_LINE.match(line) and not current["body"]:
                current["scope"] += " " + line.strip()          # scope list continued on the next line
                continue
            m = SCOPE_START.match(line)
            if m:
                if current:
                    entries.append(current)
                scope = m.group(0).strip()
                rest = line[m.end():]
                # absorb trailing list items on the same line: "2201, 2202, " ...
                extra = re.match(r"^((?:\s*,\s*(?:Ex\s*)?\d{4}(?:\d{2})?)+\s*,?)", rest)
                if extra:
                    scope += extra.group(1)
                    rest = rest[extra.end():]
                if re.fullmatch(r"\s*,?\s*(Ex)?\s*", rest, re.I):  # "Ex 2207, Ex" + next line "2208"
                    scope += rest
                    rest = ""
                current = {"scope": scope.strip(" ,"), "body": rest.strip(), "page": number, "label": label}
            elif current:
                current["body"] = (current["body"] + " " + line.strip()).strip()
    if current:
        entries.append(current)

    rules: list[OriginRule] = []
    titles: dict[int, str] = {}
    for e in entries:
        body = e["body"]
        found = RULE_RE.findall(body)
        rule_text = canonical_rule(max(found, key=len)) if found else ""
        description = re.sub(r"\s+", " ", RULE_RE.sub(" ", body)).strip(" .;-") if found else body
        description = re.sub(r"\(\s*(UAE|India)[^)]*\)", "", description).strip()   # stray negotiator notes
        scope = re.sub(r"\s+", " ", e["scope"])
        chap = re.match(r"(Ex\s*)?Chapter\s+(\d{1,2})", scope, re.I)
        if chap:
            chapters, codes, is_ex = [int(chap.group(2))], [], bool(chap.group(1))
            titles.setdefault(int(chap.group(2)), description)
            rule_id = f"psr_ch{int(chap.group(2)):02d}"
        else:
            codes, is_ex = _expand_codes(scope)
            chapters = sorted({int(c[:2]) for c in codes})
            rule_id = "psr_" + re.sub(r"[^0-9]+", "-", scope).strip("-")
        if not rule_text:
            continue
        rules.append(OriginRule(rule_id=rule_id, scope_text=scope, chapters=chapters, codes=codes, is_ex=is_ex,
                                description=description, rule_text=rule_text, components=components(rule_text),
                                page=e["page"], page_label=e["label"], source_id=SOURCE_ID))
    return rules, definitions, titles


def rule_for(code: str, rules: list[OriginRule]) -> OriginRule | None:
    """Most specific rule for an HS code: 6-digit code > 4-digit code (incl. ranges/lists) > chapter."""
    digits = re.sub(r"\D", "", code)
    for length in (6, 4):
        for rule in rules:
            if any(c == digits[:length] for c in rule.codes if len(c) == length):
                return rule
    chapter = int(digits[:2]) if len(digits) >= 2 else -1
    return next((r for r in rules if not r.codes and chapter in r.chapters), None)
