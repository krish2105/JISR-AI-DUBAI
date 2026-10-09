"""
analyzers.py — Turn English and Arabic text into search tokens for BM25 (keyword search).

Why this file exists:
    An English analyser applied to Arabic text fails silently: "والمصابيح" (and the lamps), "المصابيح"
    (the lamps) and "مصابيح" (lamps) would be three unrelated words. We analyse each script with its own rules
    and index both, so English and Arabic queries both find the right tariff lines (v3 §22.4).

    English: lower case, stop words removed, Snowball stemming ("lamps" -> "lamp").
    Arabic : canonical letters (normalize_arabic: alef/ya/ta marbuta, no diacritics/tatweel, Western digits),
             then LIGHT stemming (Larkey-style "light10"): strip one conjunction/preposition prefix and the
             definite article, then common plural/feminine/possessive suffixes, keeping at least 3 letters.
    The original text is never changed: analysis is only for matching.
"""

import re

import py_rust_stemmers

from app.security.normalize import normalize_arabic

_EN_STEMMER = py_rust_stemmers.SnowballStemmer("english")
EN_STOP = set("""a an and are as at be by for from has have in is it its of on or other others than that the this
those to was were which with not nes n.e.s whether thereof therefor such kind used""".split())
AR_STOP = set(normalize_arabic(w) for w in """في من على الى إلى عن مع او أو و ال هذا هذه التي الذي غير
وغيرها غيرها بما ما لا كل""".split())
AR_PREFIXES = ("وال", "بال", "كال", "فال", "لل", "ال", "و", "ف", "ب", "ك", "ل")
AR_SUFFIXES = ("ها", "ان", "ات", "ون", "ين", "يه", "يه", "ه", "ي")
TOKEN_RE = re.compile(r"[a-z0-9]+|[ء-ي]+")


def stem_arabic(word: str) -> str:
    """Light Arabic stemming on an already-normalised word."""
    for p in AR_PREFIXES:
        if word.startswith(p) and len(word) - len(p) >= 3:
            word = word[len(p):]
            break
    for s in AR_SUFFIXES:
        if word.endswith(s) and len(word) - len(s) >= 3:
            word = word[: -len(s)]
            break
    return word


def analyze(text: str) -> list[str]:
    """Tokens for BM25: English stems and Arabic light stems from the same text."""
    text = normalize_arabic(text.lower())
    out = []
    for tok in TOKEN_RE.findall(text):
        if tok.isascii():
            if tok in EN_STOP or (len(tok) < 2 and not tok.isdigit()):
                continue
            out.append(_EN_STEMMER.stem_word(tok))
        else:
            if tok in AR_STOP or len(tok) < 2:
                continue
            out.append(stem_arabic(tok))
    return out


def query_language(text: str) -> str:
    """'ar', 'en' or 'mixed' by script share (used for language-balanced results and reporting)."""
    ar = len(re.findall(r"[؀-ۿ]", text))
    en = len(re.findall(r"[A-Za-z]", text))
    if ar and en and min(ar, en) / max(ar, en) > 0.25:
        return "mixed"
    return "ar" if ar > en else "en"
