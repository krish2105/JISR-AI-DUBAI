"""
trust.py — 80 synthetic enquiries labelled with the buyer-trust signals they contain (EN / AR).

Why this file exists:
    The Buyer Trust tool must raise the right signals and, just as important, stay quiet on normal trade talk
    ("70% against documents", "deliver within 90 days", "our bank is Emirates NBD"). Each enquiry is built from a
    neutral request plus 0-3 planted phrases; the planted phrases ARE the labels. A quarter of the rows are hard
    negatives: phrases that look like a signal but are not one.

    Bias note: the phrases and the detector were written by the same author, so this measures implementation
    correctness and false alarms on look-alikes, not coverage of real fraud wording (that needs pilot data).
"""

import random

BASES = {
    "en": ["Hello, we need {qty} pcs {item} delivered to {city}. Please send your best price.",
           "Dear supplier, kindly quote {qty} units of {item}, CIF {city}.",
           "Hi, interested in {item}, around {qty} pieces for our showroom in {city}."],
    "ar": ["مرحبا، نحتاج {qty} قطعة {item} إلى {city}. أرسلوا أفضل سعر من فضلكم.",
           "السادة المورد، نرجو تسعير {qty} وحدة من {item} شامل الشحن إلى {city}.",
           "نرغب في شراء {item} حوالي {qty} قطعة لمعرضنا في {city}."],
}
ITEMS = {"en": ["brass diya lamps", "pashmina shawls", "cotton table runners", "wooden jewellery boxes"],
         "ar": ["مصابيح نحاسية", "شالات باشمينا", "مفارش طاولة قطنية", "صناديق مجوهرات خشبية"]}
CITIES = {"en": ["Dubai", "Sharjah", "Abu Dhabi"], "ar": ["دبي", "الشارقة", "أبوظبي"]}

# signal -> phrases that MUST raise it
POSITIVE = {
    "free_mail_domain": {"en": ["Email: buyer.desk@gmail.com", "Contact us at gulfdeals@yahoo.com"],
                         "ar": ["البريد: tijara.uae@hotmail.com"]},
    "business_email_domain": {"en": ["Email: purchase@marinahome-demo.ae"], "ar": ["البريد: sales@baytalhadaya-demo.ae"]},
    "credit_terms_request": {"en": ["We will pay after delivery.", "We need 90 days credit on this order."],
                             "ar": ["سندفع بعد الاستلام.", "نطلب الدفع الآجل لمدة 90 يوما."]},
    "bank_change_request": {"en": ["Please note we have a new bank account for payments.",
                                   "Kindly update our beneficiary details before invoicing."],
                            "ar": ["يرجى تغيير الحساب البنكي للدفع.", "لدينا حساب بنكي جديد."]},
    "pressure_urgency": {"en": ["This is urgent, reply immediately.", "Need the quote ASAP."],
                         "ar": ["الطلب عاجل جدا.", "نحتاج الرد فورا."]},
    "third_party_payment": {"en": ["Payment will be made by a third party company in Oman.",
                                   "Our sister company will pay the invoice."],
                            "ar": ["الدفع سيتم عن طريق طرف ثالث."]},
    "trade_licence_given": {"en": ["Trade licence no. 1234567 (Dubai DED)."], "ar": ["رخصة تجارية رقم 7654321"]},
}
# phrases that look similar but must NOT raise the named signal
HARD_NEGATIVE = {
    "credit_terms_request": {"en": ["Delivery within 90 days is fine.", "We pay 30% advance and 70% against documents."],
                             "ar": ["التسليم خلال 90 يوما مناسب.", "ندفع 30% مقدما و70% مقابل المستندات."]},
    "bank_change_request": {"en": ["Our bank is Emirates NBD and we can open an LC.", "Bank details are on our letterhead."],
                            "ar": ["بنكنا هو بنك الإمارات دبي الوطني."]},
    "pressure_urgency": {"en": ["No rush, we plan for next season."], "ar": ["لا داعي للاستعجال."]},
    "third_party_payment": {"en": ["We pay from our own company account."], "ar": ["ندفع من حساب شركتنا."]},
}


def generate_trust(seed: int = 20261009) -> list[dict]:
    """80 rows: {id, language, text, signals (expected), absent (must not fire), split}."""
    rng = random.Random(seed + 7)
    rows = []
    signals = list(POSITIVE)
    for idx in range(80):
        lang = "ar" if idx % 2 else "en"
        text = rng.choice(BASES[lang]).format(qty=rng.choice([50, 100, 250, 500]), item=rng.choice(ITEMS[lang]),
                                              city=rng.choice(CITIES[lang]))
        expected, absent, parts = set(), set(), [text]
        kind = idx % 4                                # 0 clean-ish, 1-2 planted signals, 3 hard negative
        if kind in (1, 2):
            for name in rng.sample(signals, rng.choice([1, 2, 3])):
                options = POSITIVE[name].get(lang) or POSITIVE[name]["en"]
                parts.append(rng.choice(options))
                expected.add(name)
        elif kind == 3:
            name = rng.choice(list(HARD_NEGATIVE))
            parts.append(rng.choice(HARD_NEGATIVE[name].get(lang) or HARD_NEGATIVE[name]["en"]))
            absent.add(name)
        if expected & {"free_mail_domain", "business_email_domain"} == {"free_mail_domain", "business_email_domain"}:
            expected.discard("business_email_domain")          # free mail wins when both are present
            parts = [p for p in parts if "-demo.ae" not in p]
        rows.append({"id": f"trust_{idx:03d}", "language": lang, "text": " ".join(parts),
                     "signals": sorted(expected), "absent": sorted(absent),
                     "split": "test" if idx >= 56 else ("dev" if idx >= 40 else "train")})
    return rows
