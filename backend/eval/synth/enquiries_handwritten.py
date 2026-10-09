"""
enquiries_handwritten.py — 30 hand-written enquiries in styles the templates never produce (TEST ONLY).

Why this file exists:
    Template-generated enquiries share structure across train/dev/test, so a parser built on the train split
    can still look better than it really is. These 30 messages were written by hand BEFORE the Phase 4 parser
    existed, in varied real-world styles: formal emails, forwarded WhatsApp chats, voice-note transcripts,
    tables, signatures in odd places, products outside the demo catalogue, Gulf Arabic, code-switching.
    They are reported separately as `extraction_f1_handwritten` and must never be used to tune the parser.

Labels: deadlines are structured like the template set; buyer_country is None when no place is written.
All names, companies and numbers are fictional.
"""


def _item(en: str, ar: str, qty: int, unit: str = "pcs") -> dict:
    """One gold item: core product words as written (English and Arabic), quantity, unit."""
    return {"description_en": en, "description_ar": ar, "quantity": qty, "unit": unit}


def _date(day: int, month: int) -> dict:
    return {"kind": "date", "day": day, "month": month}


# (id, language, text, buyer_name, country, items, incoterm, deadline)
_ROWS = [
    ("hw_01", "en",
     "Dear Sir/Madam,\n\nFurther to our call, kindly quote your best FOB Nhava Sheva price for the following:\n"
     "1) Block print cotton kaftans – 400 pcs (assorted sizes)\n2) Embroidered velvet clutches – 250 pcs\n\n"
     "We need the goods in our Dubai warehouse by 30 November.\n\nWarm regards,\nProcurement Team\nOasis Living Interiors LLC",
     "Oasis Living Interiors LLC", "AE", [_item("block print cotton kaftans", "قفاطين قطنية", 400),
                                          _item("embroidered velvet clutches", "حقائب يد مخملية", 250)],
     "FOB", _date(30, 11)),
    ("hw_02", "en",
     "Forwarded message:\n> Hi, can you check with the Jaipur supplier – we want 1500 marble coasters (sets of 4) "
     "and 300 brass door knockers, CIF Sharjah.\n\nPlease revert with price + lead time.\nRegards, Hamdan — Gulf Crest Hospitality",
     "Gulf Crest Hospitality", "AE", [_item("marble coasters", "قواعد رخامية", 1500, "sets"),
                                      _item("brass door knockers", "مطارق أبواب نحاسية", 300)],
     "CIF", None),
    ("hw_03", "en",
     "[Voice note transcript] yeah hi this is from Lulu Gifts in Abu Dhabi um we're looking at around eight hundred "
     "of the sandalwood boxes the small ones and maybe two hundred camel bone photo frames need them within 21 days thanks",
     "Lulu Gifts", "AE", [_item("sandalwood boxes", "صناديق خشب الصندل", 800),
                          _item("camel bone photo frames", "إطارات صور", 200)],
     None, {"kind": "within_days", "days": 21}),
    ("hw_04", "en",
     "Item | Qty\nDhurrie rugs 4x6 ft | 120\nJute storage baskets | 600\nTerms: DAP Doha. Delivery before 15 Jan.\n— Al Bidda Home Trading",
     "Al Bidda Home Trading", "QA", [_item("dhurrie rugs", "سجاد دري", 120), _item("jute storage baskets", "سلال جوت", 600)],
     "DAP", _date(15, 1)),
    ("hw_05", "en",
     "Hello! Corporate gifting season again 🙂 Need 2,000 leather notebooks with logo embossing and 2,000 brass pens. "
     "Ship CFR Dammam please. — Najd Corporate Gifts, Riyadh",
     "Najd Corporate Gifts", "SA", [_item("leather notebooks", "دفاتر جلدية", 2000), _item("brass pens", "أقلام نحاسية", 2000)],
     "CFR", None),
    ("hw_06", "en",
     "We require 75 hand-knotted woollen carpets, EXW Jaipur, our forwarder will collect. Target delivery: end of February.\n"
     "Thanks,\nKhalid\nSilk Route Carpets FZE",
     "Silk Route Carpets FZE", None, [_item("hand-knotted woollen carpets", "سجاد صوف", 75)],
     "EXW", {"kind": "end_of_month", "month": 2}),
    ("hw_07", "en",
     "pls send rates for 350 pcs blue pottery mugs n 350 pcs blue pottery plates, ddp ajman. urgent for hotel opening. ty\n-Ajman Bay Resort purchasing",
     "Ajman Bay Resort purchasing", "AE", [_item("blue pottery mugs", "أكواب فخار أزرق", 350),
                                           _item("blue pottery plates", "أطباق فخار أزرق", 350)],
     "DDP", None),
    ("hw_08", "en",
     "Subject: RFQ 2026/118 – brass lanterns\n\nQuantity: 900 units\nIncoterm: CIF Jebel Ali\nRequired by: 10 Dec\n\n"
     "Buyer: Marina Souk Trading LLC",
     "Marina Souk Trading LLC", "AE", [_item("brass lanterns", "فوانيس نحاسية", 900)], "CIF", _date(10, 12)),
    ("hw_09", "en",
     "Hi there, is it possible to get 60 marble elephant figurines and 40 marble tea-light holders? We are in Muscat. "
     "Prices FOB Mundra are fine.\nBest, Majan Craft House",
     "Majan Craft House", "OM", [_item("marble elephant figurines", "تماثيل فيلة رخامية", 60),
                                 _item("marble tea-light holders", "حاملات شموع رخامية", 40)],
     "FOB", None),
    ("hw_10", "en",
     "Re: your catalogue – we'd like 3 items:\n• 500 x mango wood serving boards\n• 500 x mango wood salad bowls\n"
     "• 250 x cotton napkin sets\nAll CIF Kuwait, needed within 45 days.\nAl Hamra Kitchenware Co.",
     "Al Hamra Kitchenware Co.", "KW", [_item("mango wood serving boards", "ألواح تقديم خشب المانجو", 500),
                                        _item("mango wood salad bowls", "أوعية سلطة خشب المانجو", 500),
                                        _item("cotton napkin sets", "أطقم مناديل قطنية", 250, "sets")],
     "CIF", {"kind": "within_days", "days": 45}),
    ("hw_11", "en",
     "Hello, small trial order: 100 pcs silver-plated trays. If quality ok we repeat monthly. CFR Bahrain (Khalifa Bin Salman port). "
     "— Dilmun Fine Gifts, Manama",
     "Dilmun Fine Gifts", "BH", [_item("silver-plated trays", "صواني مطلية بالفضة", 100)], "CFR", None),
    ("hw_12", "en",
     "Need quotation 1200 embroidered cushion covers 18x18 + 1200 cushion fillers. DAP our Al Quoz warehouse, Dubai, by 5 Jan. "
     "Thank you — Desert Bloom Home LLC",
     "Desert Bloom Home LLC", "AE", [_item("embroidered cushion covers", "أغطية وسائد مطرزة", 1200),
                                     _item("cushion fillers", "حشوات وسائد", 1200)],
     "DAP", _date(5, 1)),
    ("hw_13", "ar",
     "السلام عليكم ورحمة الله\nنرغب في الحصول على عرض سعر لعدد 600 فانوس نحاسي مزخرف، والشحن CIF ميناء جبل علي.\n"
     "نحتاج البضاعة قبل 20 ديسمبر.\nمع التحية،\nشركة الفنار للتجارة العامة",
     "شركة الفنار للتجارة العامة", "AE", [_item("brass lanterns", "فانوس نحاسي مزخرف", 600)], "CIF", _date(20, 12)),
    ("hw_14", "ar",
     "مرحبا، عندنا طلبية لمحلاتنا في الرياض: 300 سجادة يدوية و 150 مخدة مطرزة. الأسعار DDP الرياض لو سمحت.\n— مؤسسة نجد للمفروشات",
     "مؤسسة نجد للمفروشات", "SA", [_item("hand made rugs", "سجادة يدوية", 300), _item("embroidered pillows", "مخدة مطرزة", 150)],
     "DDP", None),
    ("hw_15", "ar",
     "تحية طيبة، نود الاستفسار عن سعر 1000 علبة بخور عود و 500 مبخرة نحاسية، التسليم خلال 30 يوماً إلى الدوحة.\n"
     "شركة دانة الخليج",
     "شركة دانة الخليج", "QA", [_item("oud incense boxes", "علبة بخور عود", 1000, "boxes"),
                                 _item("brass incense burners", "مبخرة نحاسية", 500)],
     None, {"kind": "within_days", "days": 30}),
    ("hw_16", "ar",
     "ابي عرض سعر ٤٠٠ شال كشمير و ٢٠٠ وشاح حرير، FOB موندرا. ضروري قبل نهاية يناير\n— محلات الخزامى",
     "محلات الخزامى", None, [_item("cashmere shawls", "شال كشمير", 400), _item("silk scarves", "وشاح حرير", 200)],
     "FOB", {"kind": "end_of_month", "month": 1}),
    ("hw_17", "ar",
     "الأخوة الكرام، نحتاج 250 طقم فناجين قهوة مطلية و 250 دلة نحاسية لفندقنا في مسقط، بشرط CFR مسقط.\nفندق اللبان",
     "فندق اللبان", "OM", [_item("coffee cup sets", "طقم فناجين قهوة", 250, "sets"), _item("brass coffee pots", "دلة نحاسية", 250)],
     "CFR", None),
    ("hw_18", "ar",
     "السلام عليكم\nالكمية: 800 قطعة صواني خشب منقوشة\nالشروط: DAP الشارقة\nالموعد: 12 فبراير\nمؤسسة القاسمي للهدايا",
     "مؤسسة القاسمي للهدايا", "AE", [_item("carved wooden trays", "صواني خشب منقوشة", 800)], "DAP", _date(12, 2)),
    ("hw_19", "ar",
     "مساء الخير، ممكن سعر 120 قطعة ثريات نحاسية للمسجد؟ التسليم في الكويت.\nشركة الصباح للإنارة",
     "شركة الصباح للإنارة", "KW", [_item("brass chandeliers", "ثريات نحاسية", 120)], None, None),
    ("hw_20", "ar",
     "نطلب ٢٥٠٠ كيس قماش جوت مطبوع بشعار الشركة، EXW جايبور، خلال ١٥ يوماً.\n— شركة البحر الأحمر للتسويق، جدة",
     "شركة البحر الأحمر للتسويق", "SA", [_item("printed jute bags", "كيس قماش جوت مطبوع", 2500)], "EXW",
     {"kind": "within_days", "days": 15}),
    ("hw_21", "ar",
     "لدينا معرض في أبوظبي ونحتاج 90 قطعة تماثيل رخامية صغيرة و 60 مزهرية فخار، CIF أبوظبي، قبل 25 نوفمبر.\nغاليري السعديات",
     "غاليري السعديات", "AE", [_item("small marble statues", "تماثيل رخامية صغيرة", 90), _item("pottery vases", "مزهرية فخار", 60)],
     "CIF", _date(25, 11)),
    ("hw_22", "ar",
     "سلام، بغيت أعرف سعر 50 سجادة صلاة مطرزة. التوصيل للمنامة لو أمكن.\n— بيت الحرفيين",
     "بيت الحرفيين", "BH", [_item("embroidered prayer rugs", "سجادة صلاة مطرزة", 50)], None, None),
    ("hw_23", "mixed",
     "مرحبا team, we need 400 pcs brass diyas و 400 pcs tea light holders for Diwali stock. CIF Jebel Ali, before 1 Nov please.\n"
     "— Al Karama Festive Supplies",
     "Al Karama Festive Supplies", "AE", [_item("brass diyas", "ديا نحاسية", 400), _item("tea light holders", "حاملات شموع", 400)],
     "CIF", _date(1, 11)),
    ("hw_24", "mixed",
     "السلام عليكم Rajesh bhai, شو أخبار الأسعار؟ we need 700 cotton bedsheets double size, FOB Mundra, خلال 30 يوم.\n— Sahara Linen Trading",
     "Sahara Linen Trading", None, [_item("cotton bedsheets", "شراشف قطنية", 700)], "FOB",
     {"kind": "within_days", "days": 30}),
    ("hw_25", "mixed",
     "Hi, نحتاج 1,000 hand-painted ceramic mugs و 500 coasters للفندق في دبي. DDP Dubai. Thanks يعطيك العافية\n— Creek Side Hotels",
     "Creek Side Hotels", "AE", [_item("hand-painted ceramic mugs", "أكواب سيراميك مرسومة", 1000),
                                 _item("coasters", "قواعد أكواب", 500)],
     "DDP", None),
    ("hw_26", "mixed",
     "Order request – طلبية\n250 brass bells (أجراس نحاسية)\n250 wooden elephants\nTerms: CFR Jeddah\nDeadline: 18 Dec\nRed Sea Décor Est.",
     "Red Sea Décor Est.", "SA", [_item("brass bells", "أجراس نحاسية", 250), _item("wooden elephants", "فيلة خشبية", 250)],
     "CFR", _date(18, 12)),
    ("hw_27", "mixed",
     "مرحبا، please quote 2k pcs promotional tote bags (cotton canvas) for our Sharjah event, DAP Sharjah. شكراً\n— Expo Events FZ LLC",
     "Expo Events FZ LLC", "AE", [_item("promotional tote bags", "حقائب ترويجية", 2000)], "DAP", None),
    ("hw_28", "mixed",
     "السلام عليكم, 150 sets of silver tea sets للعرس، التسليم قبل 30 Jan to Doha. شكراً\n— Al Maha Weddings",
     "Al Maha Weddings", "QA", [_item("silver tea sets", "أطقم شاي فضية", 150, "sets")], None, _date(30, 1)),
    ("hw_29", "en",
     "Hi Priya, following our meeting in Dubai, please confirm price for 3,500 recycled paper gift bags and 3,500 tissue paper packs. "
     "Need EXW pricing only.\nBest regards,\nAnita Menon\nPurchasing, Emirates Retail Group",
     "Emirates Retail Group", "AE", [_item("recycled paper gift bags", "أكياس هدايا ورقية", 3500),
                                     _item("tissue paper packs", "عبوات ورق مناديل", 3500)],
     "EXW", None),
    ("hw_30", "en",
     "Quote needed!! 200 hand-carved wooden jharokhas (wall decor), 2 sizes, 100 each. CIF Jebel Ali. Before 22 Dec if possible.\n"
     "Thanks — Heritage Walls Decor Trading",
     "Heritage Walls Decor Trading", "AE", [_item("hand-carved wooden jharokhas", "جهروكا خشبية", 200)], "CIF", _date(22, 12)),
]


def generate_handwritten() -> list[dict]:
    """The 30 hand-written enquiries as labelled records (all split 'test')."""
    rows = []
    for rid, language, text, buyer, country, items, incoterm, deadline in _ROWS:
        rows.append({
            "id": rid, "language": language, "difficulty": "handwritten", "hard_negative": False, "category": "handwritten",
            "channel": "email" if "Subject:" in text or "Dear" in text else "whatsapp", "split": "test", "text": text,
            "labels": {"buyer_name": buyer, "buyer_country": country, "items": items, "incoterm": incoterm,
                       "deadline": deadline, "language": language, "injection_expected": False, "pii": []},
        })
    assert len(rows) == 30
    return rows
