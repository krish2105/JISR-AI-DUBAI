"""
test_security_v0.py — Basic redaction and injection screening (hardened in Phase 3).
"""

from app.demo.samples import get_sample
from app.security.injection_guard import scan
from app.security.redactor import redact


def test_redactor_masks_email_phone_iban_and_keeps_domain():
    """Personal data is replaced by tokens; the business email domain is kept for trust signals."""
    result = redact("Mail ahmed.k@baytalhadaya-demo.ae or call +971 50 123 4567. IBAN AE07 0331 2345 6789 0123 456")
    assert "ahmed.k" not in result.text and "123 4567" not in result.text and "AE07" not in result.text
    assert "[EMAIL_1]@baytalhadaya-demo.ae" in result.text
    assert "[PHONE_1]" in result.text and "[IBAN_1]" in result.text
    assert result.counts == {"IBAN": 1, "EMAIL": 1, "PHONE": 1}


def test_redactor_reuses_tokens_and_leaves_quantities_alone():
    """The same number gets the same token; order quantities like '500 pcs' are untouched."""
    result = redact("Need 500 pcs. Call +971501234567, again +971501234567, or +971559999999.")
    assert "500 pcs" in result.text
    assert result.text.count("[PHONE_1]") == 2 and "[PHONE_2]" in result.text


def test_guard_flags_the_hostile_sample():
    """The bank-change sample raises bank, override and payment-pressure flags."""
    flags = scan(redact(get_sample("hostile_bank_change").message).text)
    assert {"bank_change", "instruction_override", "payment_pressure"} <= set(flags)


def test_guard_passes_normal_samples():
    """Normal English and Arabic enquiries raise no flags (no false positives)."""
    for sample_id in ("en_brass_runners", "ar_gift_boxes"):
        assert scan(redact(get_sample(sample_id).message).text) == [], sample_id


def test_guard_catches_arabic_bank_change():
    """Arabic phrasing of a bank-account change is flagged too."""
    assert "bank_change" in scan("يرجى تغيير الحساب البنكي إلى الحساب الجديد")
