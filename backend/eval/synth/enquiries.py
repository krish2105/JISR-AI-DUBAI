"""
enquiries.py — Generate labelled synthetic buyer enquiries (English, Arabic, mixed).

Why this file exists:
    We must measure the agents before tuning them. Real pilot data is not available yet, so we
    generate realistic enquiries from templates where every label (items, quantities, Incoterm,
    destination country, deadline, language, personal data) is KNOWN BY CONSTRUCTION. No model
    writes or labels this data, so the evaluation cannot be biased by the model under test.

    Difficulty levels:
      easy    clean sentences, digits, standard units
      medium  bullet lists, extra chatter, several items
      hard    WhatsApp style: lowercase, abbreviations, "1.2k", number words, Arabic-Indic digits
    Hard negatives: legitimate mentions of banks/accounts/urgency that must NOT be flagged.

All companies, people, phone numbers and emails are fictional.
"""

import random
from dataclasses import dataclass

# ---------------------------------------------------------------------------------------
# Vocabulary (fictional sellers' typical Jaipur product range)
# ---------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Product:
    """A product family with English and Arabic names and a typical unit."""

    en: str
    ar: str
    unit: str          # pcs | sets | boxes
    category: str      # handicrafts | textiles | gifting | general


PRODUCTS = [
    Product("brass diya lamps", "مصابيح ديا نحاسية", "pcs", "handicrafts"),
    Product("hand-block printed cotton table runners", "مفارش طاولة قطنية مطبوعة يدوياً", "pcs", "textiles"),
    Product("carved wooden gift boxes", "صناديق هدايا خشبية منقوشة", "pcs", "gifting"),
    Product("pashmina shawls", "شالات باشمينا", "pcs", "textiles"),
    Product("embroidered cushion covers", "أغطية وسائد مطرزة", "pcs", "textiles"),
    Product("marble coasters", "قواعد أكواب رخامية", "sets", "handicrafts"),
    Product("blue pottery vases", "مزهريات من الفخار الأزرق", "pcs", "handicrafts"),
    Product("leather bound journals", "دفاتر بغلاف جلدي", "pcs", "gifting"),
    Product("jute tote bags", "حقائب من الجوت", "pcs", "general"),
    Product("sandalwood incense sticks", "أعواد بخور خشب الصندل", "boxes", "general"),
    Product("brass serving trays", "صواني تقديم نحاسية", "pcs", "gifting"),
    Product("cotton bath towels", "مناشف حمام قطنية", "pcs", "textiles"),
    Product("silk scarves", "أوشحة حريرية", "pcs", "textiles"),
    Product("terracotta planters", "أصص من الطين المحروق", "pcs", "handicrafts"),
    Product("copper water bottles", "قوارير ماء نحاسية", "pcs", "gifting"),
    Product("quilted cotton bedspreads", "مفارش سرير قطنية مبطنة", "pcs", "textiles"),
]

AR_UNIT = {"pcs": "قطعة", "sets": "طقم", "boxes": "علبة"}

# (English name, Arabic name, ISO country) — destinations across the UAE and the GCC.
PLACES = [
    ("Dubai", "دبي", "AE"), ("Jebel Ali", "جبل علي", "AE"), ("Abu Dhabi", "أبوظبي", "AE"),
    ("Sharjah", "الشارقة", "AE"), ("Ajman", "عجمان", "AE"), ("Riyadh", "الرياض", "SA"),
    ("Jeddah", "جدة", "SA"), ("Doha", "الدوحة", "QA"), ("Muscat", "مسقط", "OM"),
    ("Kuwait City", "مدينة الكويت", "KW"), ("Manama", "المنامة", "BH"),
]
UAE_WEIGHT = 0.7   # most enquiries come from the UAE (the corridor we target)

BUYER_EN_A = ["Bayt Al Hadaya", "Al Waha", "Desert Rose", "Gulf Star", "Pearl Coast", "Falcon Crest",
              "Marina Home", "Sahara Lane", "Palm Grove", "Al Nakheel Arcade", "Blue Dhow", "Golden Sands"]
BUYER_EN_B = ["Trading LLC", "Gifts FZE", "General Trading", "Home Decor LLC", "Hospitality Supplies",
              "Corporate Gifting LLC", "Interiors FZCO"]
BUYER_AR = ["مؤسسة الواحة للهدايا", "شركة النخلة للتجارة العامة", "مؤسسة اللؤلؤة للديكور", "شركة الصقر للتوريدات",
            "مؤسسة الرمال الذهبية", "شركة نجمة الخليج التجارية", "مؤسسة بيت الهدايا", "شركة المرسى للضيافة"]

INCOTERMS = ["CIF", "FOB", "EXW", "CFR", "DAP", "DDP"]
INDIAN_PORTS = ["Mundra", "Nhava Sheva", "Jaipur ICD"]
# month number -> (short English, long English, Arabic). Text and labels use the SAME month.
MONTH_NAMES = {11: ("Nov", "November", "نوفمبر"), 12: ("Dec", "December", "ديسمبر"),
               1: ("Jan", "January", "يناير"), 2: ("Feb", "February", "فبراير")}
NUMBER_WORDS = {100: "one hundred", 200: "two hundred", 250: "two fifty", 300: "three hundred",
                500: "five hundred", 1000: "one thousand"}
ARABIC_INDIC = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")
EMAIL_DOMAINS = ["{slug}-demo.ae", "{slug}-demo.com", "gmail.com", "outlook.com"]

HARD_NEGATIVE_LINES = [
    "Payment by LC through our bank as usual.",
    "We will pay 30% advance via bank transfer, balance against documents.",
    "Our new account manager Sara will follow up on samples.",
    "Please note our accounts team needs the proforma invoice today for the LC application.",
    "Urgent requirement for our Diwali promotion, please prioritise.",
    "Kindly update the quantity in your last proforma, prices remain the same.",
]
AR_HARD_NEGATIVE_LINES = [
    "الدفع عن طريق اعتماد مستندي من بنكنا كالمعتاد.",
    "سندفع 30% مقدماً بتحويل بنكي والباقي مقابل المستندات.",
]


# ---------------------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------------------


class EnquiryGenerator:
    """Builds one labelled enquiry at a time from a seeded random source (reproducible)."""

    def __init__(self, seed: int) -> None:
        self.rng = random.Random(seed)

    # ----- small helpers -----

    def pick_place(self) -> tuple[str, str, str]:
        """Destination: UAE most of the time, sometimes elsewhere in the GCC."""
        uae = [p for p in PLACES if p[2] == "AE"]
        gcc = [p for p in PLACES if p[2] != "AE"]
        return self.rng.choice(uae if self.rng.random() < UAE_WEIGHT else gcc)

    def pick_items(self, n: int) -> list[dict]:
        """n distinct products with quantities."""
        items = []
        for product in self.rng.sample(PRODUCTS, n):
            qty = self.rng.choice([20, 50, 100, 120, 150, 200, 250, 300, 400, 500, 600, 750, 1000, 1200, 1500, 2000])
            items.append({"product": product, "quantity": qty})
        return items

    def incoterm(self, place_en: str) -> tuple[str | None, str, str]:
        """Return (code, English phrase, Arabic phrase); sometimes no Incoterm at all."""
        if self.rng.random() < 0.15:
            return None, "", ""
        code = self.rng.choice(INCOTERMS)
        if code in ("FOB", "EXW"):
            origin = self.rng.choice(INDIAN_PORTS) if code == "FOB" else "Jaipur"
            return code, f"{code} {origin}", f"{code} {origin}"
        return code, f"{code} {place_en}", f"{code} {place_en}"

    def deadline(self) -> tuple[dict | None, str, str]:
        """Return (structured gold label, English phrase, Arabic phrase), all from the same values.

        Gold labels are structured so English and Arabic answers can be compared fairly:
            {"kind": "date", "day": 26, "month": 11} | {"kind": "end_of_month", "month": 12}
            | {"kind": "within_days", "days": 30}
        """
        kind = self.rng.random()
        if kind < 0.2:
            return None, "", ""
        month = self.rng.choice(list(MONTH_NAMES))
        short, long_, ar = MONTH_NAMES[month]
        if kind < 0.6:
            day = self.rng.randint(5, 28)
            return ({"kind": "date", "day": day, "month": month},
                    f"before {day} {self.rng.choice([short, long_])}", f"قبل {day} {ar}")
        if kind < 0.8:
            return {"kind": "end_of_month", "month": month}, f"by end of {long_}", f"قبل نهاية {ar}"
        days = self.rng.choice([15, 21, 30, 45])
        return {"kind": "within_days", "days": days}, f"within {days} days", f"خلال {days} يوماً"

    def contact(self, buyer_slug: str) -> tuple[str, list[dict]]:
        """A fictional contact line and the PII it contains (for redaction evaluation)."""
        roll = self.rng.random()
        pii: list[dict] = []
        parts = []
        if roll < 0.75:
            local = self.rng.choice(["ahmed.k", "fatima.r", "sales", "purchase", "omar", "priya.m", "info"])
            domain = self.rng.choice(EMAIL_DOMAINS).format(slug=buyer_slug)
            email = f"{local}@{domain}"
            parts.append(email)
            pii.append({"type": "EMAIL", "value": local, "full": email, "domain": domain})
        if roll > 0.25:
            fmt = self.rng.choice(["+971 5{a} {b} {c}", "05{a}-{b}-{c}", "+971 5{a}{b}{c}", "+91 98{a}{b} {c}"])
            phone = fmt.format(a=self.rng.randint(0, 9), b=self.rng.randint(100, 999), c=self.rng.randint(1000, 9999))
            parts.append(phone)
            pii.append({"type": "PHONE", "value": phone})
        return ", ".join(parts), pii

    # ----- quantity / item rendering -----

    def qty_text(self, qty: int, hard: bool) -> str:
        """How a buyer writes a quantity: 500, 1,200, 1.2k, five hundred, ٥٠٠ ..."""
        if not hard:
            return f"{qty:,}" if qty >= 1000 and self.rng.random() < 0.5 else str(qty)
        style = self.rng.random()
        if style < 0.3 and qty >= 1000:
            return f"{qty / 1000:g}k"
        if style < 0.5 and qty in NUMBER_WORDS:
            return NUMBER_WORDS[qty]
        if style < 0.7:
            return f"qty {qty}"
        return str(qty)

    def items_en(self, items: list[dict], hard: bool, bullets: bool) -> str:
        """Render items in English (inline list or bullet lines)."""
        rendered = []
        for it in items:
            p, q = it["product"], self.qty_text(it["quantity"], hard)
            unit = "" if hard and self.rng.random() < 0.5 else f" {p.unit}"
            rendered.append(f"{q}{unit} {p.en}")
        if bullets:
            return "\n".join(f"- {r}" for r in rendered)
        if len(rendered) == 1:
            return rendered[0]
        joiner = " + " if hard else ", "
        return joiner.join(rendered[:-1]) + (" & " if hard else " and ") + rendered[-1]

    def items_ar(self, items: list[dict], indic_digits: bool) -> str:
        """Render items in Arabic: '500 قطعة من مصابيح ديا نحاسية و 200 ...'."""
        rendered = []
        for it in items:
            q = str(it["quantity"])
            if indic_digits:
                q = q.translate(ARABIC_INDIC)
            rendered.append(f"{q} {AR_UNIT[it['product'].unit]} من {it['product'].ar}")
        return " و ".join(rendered)

    # ----- one enquiry -----

    def make(self, idx: int, language: str, difficulty: str, hard_negative: bool = False) -> dict:
        """Build one enquiry with its gold labels."""
        n_items = {"easy": self.rng.choice([1, 2]), "medium": self.rng.choice([2, 3]), "hard": self.rng.choice([1, 2, 3])}[difficulty]
        items = self.pick_items(n_items)
        place_en, place_ar, country = self.pick_place()
        inc_code, inc_en, inc_ar = self.incoterm(place_en)
        dl_gold, dl_en, dl_ar = self.deadline()

        if language == "ar":
            buyer = self.rng.choice(BUYER_AR)
            slug = f"buyer{idx}"
        else:
            buyer = f"{self.rng.choice(BUYER_EN_A)} {self.rng.choice(BUYER_EN_B)}"
            slug = buyer.split()[0].lower() + buyer.split()[1].lower()
        contact, pii = self.contact(slug)

        if language == "en":
            text = self._en_text(difficulty, items, place_en, inc_en, dl_en, contact, buyer, hard_negative)
        elif language == "ar":
            text = self._ar_text(difficulty, items, place_ar, inc_ar, dl_ar, contact, buyer, hard_negative)
        else:
            text = self._mixed_text(items, place_en, place_ar, inc_en, dl_en, contact, buyer)

        # A label must be answerable from the text: if no destination place is written, the country is unknown
        # (fixed in synthetic-v3; 46 enquiries previously carried a country only implied by their phone number).
        if place_en.lower() not in text.lower() and place_ar not in text:
            country = None

        return {
            "id": f"enq_{idx:04d}",
            "language": language,
            "difficulty": difficulty,
            "hard_negative": hard_negative,
            "category": items[0]["product"].category,
            "channel": "whatsapp" if self.rng.random() < 0.7 else "email",
            "text": text,
            "labels": {
                "buyer_name": buyer,
                "buyer_country": country,
                "items": [{"description_en": it["product"].en, "description_ar": it["product"].ar,
                           "quantity": it["quantity"], "unit": it["product"].unit} for it in items],
                "incoterm": inc_code,
                "deadline": dl_gold,
                "language": language,
                "injection_expected": False,
                "pii": pii,
            },
        }

    def _en_text(self, difficulty, items, place, inc, dl, contact, buyer, hard_negative) -> str:
        """English templates by difficulty."""
        terms = f" {inc}" if inc else ""
        when = f", delivery {dl}" if dl else ""
        negative = f" {self.rng.choice(HARD_NEGATIVE_LINES)}" if hard_negative else ""
        if difficulty == "easy":
            body = (f"Hello, we are based in {place}. We need {self.items_en(items, False, False)}{terms}{when}. "
                    f"Please share your best price.{negative}")
        elif difficulty == "medium":
            body = (f"Hi team,\nRequirement for our {place} outlet:\n{self.items_en(items, False, True)}\n"
                    f"{('Terms: ' + inc + '.') if inc else 'Please advise shipping terms.'} "
                    f"{('Need it ' + dl + '.') if dl else ''}{negative}\nKindly send quotation with lead time.")
        else:
            body = (f"hii pls quote {self.items_en(items, True, False)}{(' ' + inc.lower()) if inc else ''}"
                    f"{(' ' + dl) if dl else ' asap'}. {negative.strip().lower()} thx")
        sign = f"\n{contact}" if contact else ""
        return f"{body}{sign}\n— {buyer}"

    def _ar_text(self, difficulty, items, place, inc, dl, contact, buyer, hard_negative) -> str:
        """Arabic templates by difficulty (hard uses Arabic-Indic digits)."""
        items_text = self.items_ar(items, indic_digits=difficulty == "hard")
        terms = f" ({inc})" if inc else ""
        when = f"، التسليم {dl}" if dl else ""
        negative = f" {self.rng.choice(AR_HARD_NEGATIVE_LINES)}" if hard_negative else ""
        if difficulty == "easy":
            body = f"مرحباً، نحتاج {items_text}{terms}{when}. يرجى إرسال عرض السعر.{negative}"
        elif difficulty == "medium":
            body = f"السلام عليكم،\nلدينا طلب لفرعنا في {place}: {items_text}{terms}{when}.\nنرجو إرسال أفضل سعر ومدة التوريد.{negative}"
        else:
            body = f"السلام عليكم نبي عرض سعر {items_text}{terms}{when} ضروري{negative}"
        sign = f"\nللتواصل: {contact}" if contact else ""
        return f"{body}{sign}\n— {buyer}"

    def _mixed_text(self, items, place_en, place_ar, inc, dl, contact, buyer) -> str:
        """Code-switched Arabic/English, as many Gulf buyers write on WhatsApp."""
        items_text = self.items_en(items, False, False)
        style = self.rng.random()
        if style < 0.5:
            body = (f"السلام عليكم, we need {items_text} for our {place_en} shop. "
                    f"{('السعر ' + inc + ' please.') if inc else 'السعر please.'} {dl} شكراً")
        else:
            body = (f"مرحبا، please send quotation for {items_text}. التسليم إلى {place_ar}"
                    f"{(' ' + inc) if inc else ''}{(', ' + dl) if dl else ''}. يعطيك العافية")
        sign = f"\n{contact}" if contact else ""
        return f"{body}{sign}\n— {buyer}"


def generate_enquiries(seed: int = 20261009) -> list[dict]:
    """300 enquiries: 150 English, 105 Arabic, 45 mixed; 10 hard negatives; stratified splits."""
    gen = EnquiryGenerator(seed)
    plan = (
        [("en", "easy")] * 50 + [("en", "medium")] * 50 + [("en", "hard")] * 50
        + [("ar", "easy")] * 40 + [("ar", "medium")] * 35 + [("ar", "hard")] * 30
        + [("mixed", "medium")] * 25 + [("mixed", "hard")] * 20
    )
    rows = []
    for idx, (language, difficulty) in enumerate(plan, start=1):
        # Every 25th English/Arabic enquiry carries a legitimate bank/urgency line (false-positive test).
        hard_negative = language != "mixed" and idx % 25 == 0
        rows.append(gen.make(idx, language, difficulty, hard_negative))
    # Stratified split by (language, difficulty): 60% train / 20% dev / 20% test, deterministic.
    groups: dict[tuple, list[dict]] = {}
    for row in rows:
        groups.setdefault((row["language"], row["difficulty"]), []).append(row)
    for group in groups.values():
        gen.rng.shuffle(group)
        n = len(group)
        for i, row in enumerate(group):
            row["split"] = "train" if i < 0.6 * n else ("dev" if i < 0.8 * n else "test")
    return rows
