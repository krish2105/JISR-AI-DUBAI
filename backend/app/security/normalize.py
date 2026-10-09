"""
normalize.py — Text normalisation used for DETECTION (never for display or storage).

Why this file exists:
    Attackers hide instructions with tricks: "I g n o r e", "upd8 b@nk", invisible characters,
    full-width letters, Arabic diacritics or letter variants. Before the injection guard looks for
    patterns, the text is turned into a few canonical "views" so one pattern catches all variants.
    The original text is always kept for display and for the models (which see redacted originals).

Arabic rules (also used by the Phase 5 Arabic search analyser):
    remove tashkeel (diacritics) and tatweel; unify alef forms أ إ آ ٱ -> ا; ى -> ي; ة -> ه;
    Arabic-Indic digits ٠-٩ -> 0-9.
"""

import re
import unicodedata

ZERO_WIDTH = re.compile(r"[​-‏‪-‮⁠-⁤﻿]")
TASHKEEL = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭ]")
TATWEEL = "ـ"
ALEF_FORMS = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ة": "ه"})
ARABIC_INDIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
# Common "leet" substitutions, applied only inside words that also contain letters.
LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "8": "ate", "@": "a", "$": "s"})
# Runs of single characters separated by spaces/dots: "i g n o r e" or "i.g.n.o.r.e"
SPACED_LETTERS = re.compile(r"\b(?:[^\W\d_][ .\-_*]{1,3}){3,}[^\W\d_]\b")


def normalize_arabic(text: str) -> str:
    """Canonical Arabic for matching: no diacritics/tatweel, unified alef/ya/ta marbuta, Western digits."""
    text = TASHKEEL.sub("", text).replace(TATWEEL, "")
    return text.translate(ALEF_FORMS).translate(ARABIC_INDIC_DIGITS)


def _clean(text: str) -> str:
    """NFKC (full-width -> normal), no zero-width characters, lower case, Arabic canonical; spacing kept."""
    text = unicodedata.normalize("NFKC", text)
    text = ZERO_WIDTH.sub("", text).lower()
    text = normalize_arabic(text)
    return text.replace("_", " ")                      # file names: order_IGNORE_PREVIOUS -> order ignore previous


def _collapse(text: str) -> str:
    """Single spaces, trimmed."""
    return re.sub(r"\s+", " ", text).strip()


def basic(text: str) -> str:
    """The canonical view: cleaned and with single spaces."""
    return _collapse(_clean(text))


def despace(text: str) -> str:
    """Join letter-by-letter spelling: 'i g n o r e   p r e v i o u s' -> 'ignore previous'.

    Works on text whose original spacing is kept: in spaced writing, words are separated by
    two or more spaces, letters by one.
    """
    def join(match: re.Match) -> str:
        return re.sub(r"[ .\-_*]", "", match.group(0))
    marked = re.sub(r" {2,}", " | ", text)
    return _collapse(SPACED_LETTERS.sub(join, marked).replace(" | ", " ").replace("|", " "))


def unleet(text: str) -> str:
    """Undo leetspeak inside mixed words only ('upd8' -> 'update', 'b@nk' -> 'bank'), keeping real numbers."""
    def fix(match: re.Match) -> str:
        word = match.group(0)
        return word.translate(LEET) if re.search(r"[a-z]", word) and re.search(r"[0-9@$]", word) else word
    return re.sub(r"[a-z0-9@$]+", fix, text)


def views(text: str) -> list[str]:
    """All detection views of a message (deduplicated, in order of increasing transformation)."""
    cleaned = _clean(text)
    b, d = _collapse(cleaned), despace(cleaned)
    return list(dict.fromkeys([b, d, unleet(b), unleet(d)]))
