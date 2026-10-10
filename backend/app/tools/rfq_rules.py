"""
rfq_rules.py — Deterministic, bilingual RFQ parser (no model involved).

Why this file exists:
    Two jobs in the product:
      1. OFFLINE EXTRACTION: when no model is available (offline demo, outages) Jisr can still read an enquiry.
      2. GROUNDING: when a model extracts the RFQ, these signals check it. A quantity the model reports that does
         not appear in the message, or an Incoterm that is not written, is a likely hallucination (see rfq.py).

What it understands (English, Arabic, code-switched):
    quantities  500 · 1,200 · 1.2k · 2k · ٥٠٠ · "eight hundred" · "qty 120" · "500 x" · "– 400 pcs" · table rows
    units       pcs, pieces, nos, units, sets, boxes, dozen; قطعة، طقم، علبة، دزينة
    Incoterms   EXW FCA FAS FOB CFR (C&F, CNF) CIF CPT CIP DAP DPU DDP, any case
    places      UAE / GCC cities, ports and countries in English and Arabic -> ISO country; Indian origin ports ignored
    deadlines   "before 26 Nov", "by 5 Jan", "Required by: 10 Dec", "end of February", "within 30 days",
                "قبل 20 ديسمبر", "قبل نهاية يناير", "خلال 15 يوماً"
    language    en / ar / mixed by counting meaningful words in each script

Development discipline: built on the TRAIN split of data/synthetic/enquiries.jsonl only. Dev, test and the
30 hand-written enquiries are measured by `make eval`, never used to tune these rules.
"""

import re

from app.agents.state import RFQ, LineItem
from app.security.normalize import normalize_arabic

ARABIC_INDIC = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

INCOTERM_RE = re.compile(r"(?<![a-z])(exw|fca|fas|fob|cfr|cnf|c&f|cif|cpt|cip|dap|dpu|ddp)(?![a-z])", re.I)
INCOTERM_ALIASES = {"CNF": "CFR", "C&F": "CFR"}
C_AND_D_TERMS = {"CFR", "CIF", "CPT", "CIP", "DAP", "DPU", "DDP"}

# (variants, ISO country) — variants are matched on lower-cased, Arabic-normalised text.
GAZETTEER: list[tuple[tuple[str, ...], str]] = [
    (("dubai", "jebel ali", "al quoz", "deira", "abu dhabi", "khalifa port", "sharjah", "ajman", "ras al khaimah",
      "fujairah", "umm al quwain", "united arab emirates", "uae", "دبي", "جبل علي", "ابوظبي", "أبوظبي", "الشارقه",
      "الشارقة", "عجمان", "راس الخيمه", "رأس الخيمة", "الفجيره", "الفجيرة", "الامارات", "الإمارات"), "AE"),
    (("riyadh", "jeddah", "dammam", "saudi", "ksa", "الرياض", "جده", "جدة", "الدمام", "السعوديه", "السعودية"), "SA"),
    (("doha", "qatar", "hamad port", "الدوحه", "الدوحة", "قطر"), "QA"),
    (("muscat", "oman", "salalah", "sohar", "مسقط", "صلاله", "صلالة"), "OM"),
    (("kuwait", "الكويت"), "KW"),
    (("manama", "bahrain", "المنامه", "المنامة", "البحرين"), "BH"),
]
ORIGIN_PLACES = ("mundra", "nhava sheva", "jaipur", "jaipur icd", "موندرا", "جايبور")

UNITS = {
    "pcs": "pcs", "pc": "pcs", "pieces": "pcs", "piece": "pcs", "nos": "pcs", "units": "pcs", "unit": "pcs",
    "sets": "sets", "set": "sets", "boxes": "boxes", "box": "boxes", "dozen": "dozen", "doz": "dozen",
    "قطعه": "pcs", "قطعة": "pcs", "قطع": "pcs", "طقم": "sets", "اطقم": "sets", "أطقم": "sets", "علبه": "boxes",
    "علبة": "boxes", "علب": "boxes", "دزينه": "dozen", "دزينة": "dozen",
}
UNIT_RE = "|".join(sorted((re.escape(u) for u in UNITS), key=len, reverse=True))

EN_MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
MONTH_LONG = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
              "November", "December"]
AR_MONTHS = {"يناير": 1, "فبراير": 2, "مارس": 3, "ابريل": 4, "أبريل": 4, "مايو": 5, "يونيو": 6, "يوليو": 7,
             "اغسطس": 8, "أغسطس": 8, "سبتمبر": 9, "اكتوبر": 10, "أكتوبر": 10, "نوفمبر": 11, "ديسمبر": 12}
EN_MONTH_RE = r"(jan(uary)?|feb(ruary)?|mar(ch)?|apr(il)?|may|june?|july?|aug(ust)?|sep(t(ember)?)?|oct(ober)?|nov(ember)?|dec(ember)?)"
AR_MONTH_RE = "(" + "|".join(sorted(map(re.escape, AR_MONTHS), key=len, reverse=True)) + ")"

NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
                "ten": 10, "twelve": 12, "fifteen": 15, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
                "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
NUMBER_WORD_RE = re.compile(
    r"\b((?:one|two|three|four|five|six|seven|eight|nine|ten|twelve|fifteen|twenty|thirty|forty|fifty)"
    r"(?:\s+(?:hundred|thousand|fifty))+)\b", re.I)

# Arabic round numbers as spoken (voice notes are transcribed to words: "ثلاثمئة مصباح").
AR_NUMBER_WORDS = {
    "مئة|مائة": 100, "مئتين|مئتان|مئتي|مائتين|مائتان|مائتي": 200, "ثلاثمئة|ثلاثمائة|ثلاث مئة|ثلاث مائة": 300,
    "أربعمئة|اربعمئة|أربعمائة|اربعمائة|أربع مئة|اربع مئة": 400, "خمسمئة|خمسمائة|خمس مئة|خمس مائة": 500,
    "ستمئة|ستمائة|ست مئة": 600, "سبعمئة|سبعمائة|سبع مئة": 700,
    "ثمانمئة|ثمانمائة|ثمانيمئة|ثماني مئة|ثمان مئة": 800, "تسعمئة|تسعمائة|تسع مئة": 900,
    "ألف|الف": 1000, "ألفين|ألفان|الفين|الفان": 2000, "عشرين": 20, "ثلاثين": 30, "أربعين|اربعين": 40,
    "خمسين": 50, "ستين": 60, "سبعين": 70, "ثمانين": 80, "تسعين": 90,
}
AR_NUMBER_RE = re.compile(
    r"(?<![\u0621-\u064a])(و)?(" + "|".join(sorted((w for k in AR_NUMBER_WORDS for w in k.split("|")), key=len,
                                                    reverse=True)) + r")(?![\u0621-\u064a])")
AR_NUMBER_VALUE = {w: v for k, v in AR_NUMBER_WORDS.items() for w in k.split("|")}

# Words that end an item description (context that follows the product name).
STOP_RE = re.compile(
    r"\s(for|to|ship|shipping|delivery|deliver|deliverd|needed|need|required|within|before|by|till|until|asap|"
    r"please|pls|plz|kindly|thanks|thx|ty|if|incl|including|with|in|at|on|all|price|prices|terms|urgent|"
    r"لمحلاتنا|لفندقنا|للفندق|للعرس|للمسجد|لفرعنا|التسليم|الشحن|بشرط|قبل|خلال|ضروري|يرجى|لو|من فضلك|للمعرض)\b.*$",
    re.I)
FILLER_RE = re.compile(r"^(?:(?:of|the|x|×|qty|quantity|nos|عدد|من|ال)\s+)+", re.I)


def _norm(text: str) -> str:
    """Lower-case, Arabic-normalised, Western digits, single spaces (for matching only)."""
    return re.sub(r"[ \t]+", " ", normalize_arabic(text.translate(ARABIC_INDIC)).lower())


# ---------------------------------------------------------------------------------------
# Fields
# ---------------------------------------------------------------------------------------


def find_incoterm(text: str) -> tuple[str | None, int]:
    """First Incoterm written in the text (canonical code) and its position."""
    m = INCOTERM_RE.search(text)
    if not m:
        return None, -1
    code = m.group(1).upper()
    return INCOTERM_ALIASES.get(code, code), m.start()


def find_country(text: str, incoterm: str | None, incoterm_pos: int) -> str | None:
    """Destination country: the place named in a C/D Incoterm phrase, else the first GCC place mentioned."""
    t = _norm(text)
    hits: list[tuple[int, str]] = []
    for variants, country in GAZETTEER:
        for v in variants:
            v_norm = _norm(v)
            for m in re.finditer(rf"(?<![\w؀-ۿ]){re.escape(v_norm)}(?![\w؀-ۿ])", t):
                hits.append((m.start(), country))
    if not hits:
        return None
    hits.sort()
    if incoterm in C_AND_D_TERMS and incoterm_pos >= 0:
        after = [h for h in hits if 0 <= h[0] - incoterm_pos <= 40]
        if after:
            return after[0][1]
    return hits[0][1]


def find_deadline(text: str) -> str | None:
    """A canonical deadline phrase ('26 Nov', 'end of February', 'within 30 days') or None."""
    t = _norm(text)
    if m := re.search(r"(within|in)\s+(\d{1,3})\s+days?|خلال\s+(\d{1,3})\s+يوم", t):
        return f"within {m.group(2) or m.group(3)} days"
    if m := re.search(rf"end of\s+{EN_MONTH_RE}", t):
        return f"end of {MONTH_LONG[EN_MONTHS.index(m.group(1)[:3])]}"
    if m := re.search(rf"نهايه\s+{_norm(AR_MONTH_RE)}", t):
        return f"end of {MONTH_LONG[AR_MONTHS[_ar_month_key(m.group(1))] - 1]}"
    date_en = rf"(\d{{1,2}})(?:st|nd|rd|th)?\s+{EN_MONTH_RE}\b"
    if m := re.search(rf"(before|by|till|until|required by|deadline|need(?:ed)? (?:it |them )?by|delivery|"
                      rf"due|target delivery)\s*:?\s*(?:the\s+)?{date_en}", t):
        return f"{int(m.group(2))} {MONTH_LONG[EN_MONTHS.index(m.group(3)[:3])]}"
    if m := re.search(rf"(قبل|الموعد\s*:?|بتاريخ)\s*(\d{{1,2}})\s+{_norm(AR_MONTH_RE)}", t):
        return f"{int(m.group(2))} {MONTH_LONG[AR_MONTHS[_ar_month_key(m.group(3))] - 1]}"
    if m := re.search(date_en, t):
        return f"{int(m.group(1))} {MONTH_LONG[EN_MONTHS.index(m.group(2)[:3])]}"
    return None


def _ar_month_key(normalised: str) -> str:
    """Map a normalised Arabic month back to its dictionary key."""
    return next(k for k in AR_MONTHS if _norm(k) == normalised)


def detect_language(text: str) -> str:
    """en / ar / mixed from meaningful words (Incoterms, places, units, emails, tokens are ignored)."""
    body = re.sub(r"\S+@\S+|\[[A-Z]+_\d+\]|https?://\S+", " ", text)
    body = INCOTERM_RE.sub(" ", body)
    ar_words = re.findall(r"[؀-ۿ]{2,}", body)
    ignore = {v for variants, _ in GAZETTEER for v in variants} | set(ORIGIN_PLACES) | set(UNITS)
    en_words = [w for w in re.findall(r"[A-Za-z]{2,}", body) if w.lower() not in ignore]
    # Code-switching (Gulf WhatsApp style): a few Arabic words around an English body, or the reverse.
    if len(ar_words) >= 2 and len(en_words) >= 3:
        return "mixed"
    return "ar" if len(ar_words) > len(en_words) else "en"


def find_buyer(text: str) -> str:
    """Buyer name: a signature line after a dash, else the last line that looks like a company."""
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    for line in reversed(lines):
        if m := re.match(r"^[—–-]\s*(.+)$", line):
            return re.split(r",\s*(?=[A-Z؀-ۿ][^,]*$)", m.group(1))[0].strip()
    company = re.compile(r"(llc|fze|fzco|fz llc|trading|co\.|est\.|group|hotels?|gifts|شركة|مؤسسة|محلات|فندق|غاليري|بيت)", re.I)
    for line in reversed(lines):
        if company.search(line) and len(line) < 80 and not re.search(r"\d{3,}", line):
            return line
    return "Unknown buyer"


# ---------------------------------------------------------------------------------------
# Items
# ---------------------------------------------------------------------------------------


def _words_to_number(phrase: str) -> int | None:
    """'eight hundred' -> 800, 'two thousand five hundred' -> 2500, 'two fifty' -> 250."""
    total, current = 0, 0
    for word in phrase.lower().split():
        if word in NUMBER_WORDS:
            current = current * 100 + NUMBER_WORDS[word] if word == "fifty" and current else current + NUMBER_WORDS[word]
        elif word == "hundred":
            current = (current or 1) * 100
        elif word == "thousand":
            total += (current or 1) * 1000
            current = 0
    value = total + current
    return value or None


def _to_number(token: str) -> float | None:
    """'1,200' -> 1200, '1.2k' -> 1200, '٥٠٠' -> 500."""
    t = token.translate(ARABIC_INDIC).lower().replace(",", "")
    try:
        return float(t[:-1]) * 1000 if t.endswith("k") else float(t)
    except ValueError:
        return None


def _clean_description(desc: str) -> str:
    """Strip units, fillers, Incoterm/place/deadline context and punctuation around a product name."""
    d = re.sub(r"\(.*?\)|\(.*$", "", desc)                      # "(medium size)" and unclosed "(..." first
    d = d.strip(" -–—:|•*.,؛،()[]\"'")
    d = re.sub(rf"^(?:{UNIT_RE})\b\.?\s*", "", d, flags=re.I)
    d = FILLER_RE.sub("", d)
    d = re.sub(rf"^(?:{UNIT_RE})\b\.?\s*", "", d, flags=re.I)
    d = FILLER_RE.sub("", d)
    d = INCOTERM_RE.split(d)[0]
    d = STOP_RE.sub("", " " + d).strip()
    d = re.sub(r"\b\d+\s*x\s*\d+\b.*$", "", d)                      # "4x6 ft", "18x18"
    return d.strip(" -–—:|•*.,؛،()[]\"'")


NUM = r"(\d[\d,]*(?:\.\d+)?k?)"
NON_QTY_AFTER = re.compile(r"^\s*(items?|products?|sizes?|colou?rs?|days?|weeks?|months?|%|ft|cm|mm|inch|"
                           rf"{EN_MONTH_RE}\b|يوم|يوما|ايام|أيام|{_norm(AR_MONTH_RE)})", re.I)
NON_QTY_BEFORE = re.compile(r"(?<![A-Za-z])(within|in|before|by|rfq|invoice|inv|po|order|no\.?|#|aed|inr|usd|rs\.?|sets of|"
                            r"خلال|قبل)\s*$", re.I)


def find_items(text: str) -> list[LineItem]:
    """Quantity + product pairs, in reading order."""
    t = text.translate(ARABIC_INDIC)
    for phrase in NUMBER_WORD_RE.findall(t):                         # "eight hundred" -> "800"
        value = _words_to_number(phrase)
        if value:
            t = t.replace(phrase, str(value), 1)
    # "ومئتي مفرش" -> " و 200 مفرش" (the conjunction is kept so the segment split still works)
    t = AR_NUMBER_RE.sub(lambda m: (" و " if m.group(1) else "") + str(AR_NUMBER_VALUE[m.group(2)]), t)
    segments = re.split(r"\n|;|\||•|\s\+\s|\s&\s|\sand\s|\sn\s|\s+و\s+|،|,\s|\.\s", t)
    items: list[LineItem] = []
    pending_desc: str | None = None                                  # "Dhurrie rugs 4x6 ft | 120" (table rows)
    for raw in segments:
        seg = raw.strip()
        if not seg:
            continue
        found = False
        for m in re.finditer(rf"(?<![\w.\-/]){NUM}(?![\w./%\-])", seg):
            before, after = seg[: m.start()], seg[m.end():]
            if NON_QTY_AFTER.match(after) or NON_QTY_BEFORE.search(before):
                continue
            qty = _to_number(m.group(1))
            if qty is None or qty < 5:
                continue
            unit_m = re.match(rf"\s*(?:x\s*)?({UNIT_RE})\b\.?", after, re.I)
            unit = UNITS.get(unit_m.group(1).lower(), "pcs") if unit_m else "pcs"
            desc = _clean_description(after)
            if len(re.findall(r"[\w؀-ۿ]{2,}", desc)) == 0:        # "Block print kaftans – 400 pcs"
                lead = re.sub(r"^(?:\d+\)|\d+\.|[-–•*])\s*", "", before)
                lead = re.sub(r"(?i)\b(qty|quantity|الكمية)\s*:?\s*$", "", lead)
                desc = _clean_description(lead) or (pending_desc or "")
            if not desc or desc.lower() in UNITS:
                continue
            items.append(LineItem(description=desc, quantity=qty, unit=unit))
            found = True
            break
        if not found and re.search(r"[A-Za-z؀-ۿ]{3,}", seg) and not re.search(r"\d", seg):
            pending_desc = _clean_description(seg)
    # Drop exact duplicates (same quantity and description written twice).
    unique: list[LineItem] = []
    for item in items:
        if not any(u.quantity == item.quantity and u.description.lower() == item.description.lower() for u in unique):
            unique.append(item)
    return unique


def parse_rfq(text: str, channel: str = "whatsapp") -> RFQ:
    """Full deterministic parse of one (redacted) enquiry."""
    incoterm, pos = find_incoterm(text)
    return RFQ(
        buyer_name=find_buyer(text),
        buyer_country=find_country(text, incoterm, pos) or "unknown",
        items=find_items(text),
        incoterm=incoterm,
        deadline=find_deadline(text),
        language=detect_language(text),
        channel=channel,
    )


def numbers_in(text: str) -> set[float]:
    """Every quantity-like number written in the text (used to ground model output)."""
    t = text.translate(ARABIC_INDIC)
    values = {v for tok in re.findall(r"\d[\d,]*(?:\.\d+)?k?", t) if (v := _to_number(tok)) is not None}
    values |= {float(v) for p in NUMBER_WORD_RE.findall(t) if (v := _words_to_number(p))}
    return values
