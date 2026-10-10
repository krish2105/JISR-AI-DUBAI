"""
trade_terms.py — Bridge between how sellers name goods and how the HS 2022 tariff words them.

Why this file exists:
    Sellers write "brass diya lamps", "table runners", "agarbatti". The tariff says "non-electrical luminaires",
    "table linen", "odoriferous preparations which operate by burning". Keyword and meaning search both miss
    such pairs, so the HS classifier adds the tariff's own vocabulary to the query before searching.

    This is a small, reviewable glossary of common India -> UAE export goods (English and Arabic). It only adds
    search words; it never decides a code. The ranked headings still come from the official tariff text and
    are shown with a confidence and "needs human check". Written from general HS knowledge (WCO HS 2022
    heading texts), not tuned on the evaluation test split (docs/DECISIONS.md K10).
"""

import re

# (pattern in the seller's words, tariff vocabulary to add). Patterns are case-insensitive; Arabic uses letter
# boundaries so "شال" does not match inside another word.
GLOSSARY: list[tuple[str, str]] = [
    # lighting
    (r"diya|deepak|oil lamps?|قنديل|قناديل|سراج|ديا", "non-electrical luminaires and lighting fittings"),
    (r"lamps?|lanterns?|مصباح|مصابيح|فانوس|فوانيس", "luminaires lighting fittings lamps"),
    (r"led bulbs?|light bulbs?|لمبات?|لمبة", "LED lamps light-emitting diode light sources"),
    # home textiles
    (r"(table )?runners?|table ?cloths?|table covers?|napkins?|place ?mats?|مفرش طاولة|مفارش|ممر طاولة",
     "table linen"),
    (r"bed ?sheets?|bed ?linen|pillow ?(covers?|cases?)|duvet covers?|شراشف|شرشف|أغطية سرير|ملاءات",
     "bed linen"),
    (r"towels?|مناشف|منشفة|فوط", "toilet linen and kitchen linen of terry towelling"),
    (r"cushion covers?|أغطية وسائد|أغطية الوسائد", "other furnishing articles cushion covers"),
    (r"curtains?|drapes?|ستائر|ستارة", "curtains drapes interior blinds"),
    (r"rugs?|dhurries|dhurrie|durries|carpets?|kilims?|سجاد|سجادة|بساط", "carpets and other textile floor coverings"),
    (r"jute bags?|sacks?|أكياس جوت", "sacks and bags for the packing of goods of jute"),
    # apparel
    (r"shawls?|stoles?|scarf|scarves|dupattas?|pashmina|شال|شالات|وشاح|باشمينا",
     "shawls scarves mufflers mantillas veils"),
    (r"t-?shirts?|تي شيرت", "T-shirts singlets knitted or crocheted"),
    # household and metal articles
    (r"bottles?|tumblers?|jugs?|utensils?|cookware|kitchenware|bowls?|trays?|platters?|زجاجات?|قارورة|أواني|"
     r"أدوات مطبخ|أكواب|صوان|صواني|صينية",
     "table kitchen or other household articles"),
    (r"planters?|flower ?pots?|plant pots?|أصص|أصيص", "flower pots ornamental articles household articles"),
    (r"coasters?|قواعد أكواب", "table articles household articles"),
    (r"journals?|diar(y|ies)|notebooks?|دفاتر|دفتر", "registers account books note books diaries"),
    (r"bed ?spreads?|quilts?|مفارش سرير|لحاف", "bedspreads quilts furnishing articles"),
    (r"statues?|statuettes?|idols?|figurines?|sculptures?|تماثيل|تمثال", "statuettes and other ornaments"),
    (r"(jewell?ery )?boxes|caskets?|صناديق|صندوق|علب", "caskets and cases for jewellery boxes cases"),
    (r"photo frames?|picture frames?|براويز|إطارات صور", "wooden frames for paintings photographs mirrors"),
    (r"bangles?|أساور|اسوار", "imitation jewellery bangles"),
    (r"handbags?|purses?|clutch(es)?|حقائب يد|حقيبة يد", "handbags"),
    (r"shoes|sandals|footwear|juttis?|mojaris?|chappals?|أحذية|حذاء|صنادل", "footwear with outer soles and uppers"),
    # food and agriculture
    (r"agarbatti|incense( sticks)?|dhoop|بخور|أعواد البخور",
     "agarbatti odoriferous preparations which operate by burning"),
    (r"basmati|أرز|ارز", "rice"),
    (r"turmeric|haldi|كركم", "turmeric curcuma spices"),
    (r"cardamom|elaichi|هيل|هال", "cardamoms spices"),
    (r"chill?ies|chilli powder|فلفل أحمر|شطة", "fruits of the genus Capsicum dried crushed or ground"),
    (r"ghee|سمن", "butter and other fats and oils derived from milk dairy spreads"),
    (r"buffalo meat|carabeef|لحم جاموس", "meat of bovine animals frozen boneless"),
    (r"cashews?|كاجو", "cashew nuts fresh or dried shelled"),
    (r"mangoes|mango|مانجو|مانجا", "mangoes guavas mangosteens fresh or dried"),
    # materials (Arabic -> English, so the English tariff text and vectors line up)
    (r"نحاس أصفر|نحاسية|نحاسي|نحاس", "copper brass"),
    (r"خشبية|خشبي|خشب", "wood wooden"),
    (r"قطنية|قطني|قطن", "cotton"),
    (r"حريرية|حرير", "silk"),
    (r"صوفية|صوفي|صوف", "wool"),
    (r"جلدية|جلدي|جلد", "leather"),
    (r"خزفية|خزفي|خزف|سيراميك", "ceramic"),
    (r"الفولاذ المقاوم للصدأ|ستانلس", "stainless steel"),
]

_BOUND_L = r"(?<![A-Za-zء-ي])(?:و?[بلك]?ال|و)?"          # Arabic article / conjunction prefixes
_BOUND_R = r"(?![A-Za-zء-ي])"
_COMPILED = [(re.compile(f"{_BOUND_L}(?:{p}){_BOUND_R}", re.I), terms) for p, terms in GLOSSARY]


def tariff_terms(description: str) -> list[str]:
    """Tariff vocabulary for the goods named in a description (in glossary order, without duplicates)."""
    return list(dict.fromkeys(terms for rx, terms in _COMPILED if rx.search(description)))


def expand(description: str) -> str:
    """The description plus its tariff vocabulary in brackets ('brass diya lamps (non-electrical luminaires ...)')."""
    terms = tariff_terms(description)
    return f"{description} ({'; '.join(terms)})" if terms else description

