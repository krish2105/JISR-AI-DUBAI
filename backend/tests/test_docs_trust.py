"""
test_docs_trust.py — Document Consistency Checker and Buyer Trust signals (Phase 6).

Each check has a trigger test and a non-trigger test; formatting differences must never raise a finding.
"""

import copy

import pytest

from app.tools import buyer_trust, doc_checker
from app.tools.buyer_trust import SanctionsEntry, assess, load_sanctions, normalise_name, sanctions_signal
from app.tools.doc_checker import check_document_set, number, same_hs


@pytest.fixture
def clean() -> dict:
    return {
        "invoice": {"currency": "AED", "total": 12020.0, "lines": [
            {"description": "Brass diya lamps", "hs_code": "94055000", "quantity": 500, "unit_price": 20.84,
             "amount": 10420.0},
            {"description": "Cotton table runners", "hs_code": "63025100", "quantity": 200, "unit_price": 8.0,
             "amount": 1600.0}]},
        "quote_currency": "AED",
        "packing_list": {"lines": [
            {"description": "Brass diya lamps", "hs_code": "94055000", "quantity": 500, "net_kg": 400,
             "gross_kg": 450},
            {"description": "Cotton table runners", "hs_code": "63025100", "quantity": 200, "net_kg": 60,
             "gross_kg": 70}]},
        "certificate_of_origin": {"present": True, "hs_codes": ["94055000", "63025100"]},
        "cepa_preference_claimed": True,
        "shipping": {"transshipment_port": None, "through_bill_of_lading": True},
        "export_declaration": {"shipping_bill_no": "SB1234567"},
    }


def types(docs: dict) -> list[str]:
    return [f["type"] for f in check_document_set(docs)]


def test_clean_set_has_no_findings(clean):
    assert check_document_set(clean) == []


def test_formatting_and_line_order_never_raise_findings(clean):
    noisy = copy.deepcopy(clean)
    noisy["invoice"]["lines"][0]["hs_code"] = "9405.50.00"
    noisy["invoice"]["lines"][0]["amount"] = "10,420.00"
    noisy["invoice"]["total"] = "AED 12,020.00"
    noisy["invoice"]["currency"] = "aed "
    noisy["packing_list"]["lines"].reverse()                      # different order on the packing list
    noisy["packing_list"]["lines"][0]["quantity"] = "200 pcs"
    noisy["certificate_of_origin"]["hs_codes"] = ["630251", "940550"]   # 6 digits, other order
    assert check_document_set(noisy) == []


@pytest.mark.parametrize("mutate, expected_type, expected_field", [
    (lambda d: d["packing_list"]["lines"][1].update(quantity=210), "qty_mismatch", "packing_list.line[1].quantity"),
    (lambda d: d["packing_list"]["lines"][0].update(hs_code="85393200"), "hs_mismatch",
     "packing_list.line[0].hs_code"),
    (lambda d: d["certificate_of_origin"].update(hs_codes=["94055000", "44209090"]), "hs_mismatch",
     "certificate_of_origin.line[1].hs_code"),
    (lambda d: (d["invoice"]["lines"][0].update(amount=10500.0), d["invoice"].update(total=12100.0)),
     "line_total_mismatch", "invoice.line[0].amount"),
    (lambda d: d["invoice"].update(total=13000.0), "invoice_total_mismatch", "invoice.total"),
    (lambda d: d.update(certificate_of_origin={"present": False}), "missing_coo", "certificate_of_origin"),
    (lambda d: d.update(export_declaration={"shipping_bill_no": ""}), "missing_export_declaration",
     "export_declaration.shipping_bill_no"),
    (lambda d: d["invoice"].update(currency="USD"), "currency_mismatch", "invoice.currency"),
    (lambda d: d["packing_list"]["lines"][0].update(net_kg=500), "weight_inconsistency",
     "packing_list.line[0].net_kg"),
    (lambda d: d.update(shipping={"transshipment_port": "Salalah", "through_bill_of_lading": False}),
     "consignment_gap", "shipping.transshipment_port"),
])
def test_each_mistake_is_found_on_the_right_field(clean, mutate, expected_type, expected_field):
    mutate(clean)
    findings = check_document_set(clean)
    assert [(f["type"], f["field"]) for f in findings] == [(expected_type, expected_field)]
    assert findings[0]["fix"] and findings[0]["severity"] in ("high", "medium")


def test_no_preference_claimed_means_no_coo_needed(clean):
    clean["cepa_preference_claimed"] = False
    clean["certificate_of_origin"] = {"present": False}
    assert check_document_set(clean) == []


def test_transshipment_with_through_bill_is_fine(clean):
    clean["shipping"] = {"transshipment_port": "Salalah", "through_bill_of_lading": True}
    assert check_document_set(clean) == []


def test_draft_stage_skips_documents_that_do_not_exist_yet(clean):
    clean["certificate_of_origin"] = {"present": False}
    clean["export_declaration"] = {"shipping_bill_no": None}
    assert check_document_set(clean, stage="draft") == []
    assert {f["type"] for f in check_document_set(clean)} == {"missing_coo", "missing_export_declaration"}


def test_treaty_findings_carry_a_reference(clean):
    clean["shipping"] = {"transshipment_port": "Colombo", "through_bill_of_lading": False}
    assert check_document_set(clean)[0]["rule_ref"] == "CEPA Article 3.12"


def test_normalisation_helpers():
    assert same_hs("6214.20.10", "62142010") and same_hs("621420", "62142010") and same_hs("6214", "62142010")
    assert not same_hs("62", "62142010") and not same_hs("9405", "74192090")
    assert not same_hs("94055000", "85393200")
    assert number("1,200 pcs") == 1200 and number("AED 52,840.50") == 52840.5 and number(None) is None
    assert doc_checker.IS_STUB is False


# ---------- buyer trust --------------------------------------------------------------------------------


def signals(text: str, **kw) -> set[str]:
    return {s["signal"] for s in assess(text, use_list=False, **kw)}


def test_trust_signals_trigger_and_stay_quiet():
    assert "free_mail_domain" in signals("Contact me at [EMAIL_1]@gmail.com")
    assert "business_email_domain" in signals("[EMAIL_1]@baytalhadaya-demo.ae")
    assert "credit_terms_request" in signals("We will pay after delivery.")
    assert "credit_terms_request" not in signals("Delivery within 90 days is fine.")
    assert "bank_change_request" in signals("Please note our new bank account.")
    assert "bank_change_request" not in signals("Our bank is Emirates NBD.")
    assert "bank_change_request" in signals("hello", injection_flags=["bank_detail_change"])
    assert "third_party_payment" in signals("Payment will be made by a third party company.")
    assert "trade_licence_given" in signals("Trade licence no. 1234567")
    assert "destination_outside_gcc" in signals("hi", buyer_country="US")
    assert "destination_outside_gcc" not in signals("hi", buyer_country="AE")
    assert "large_first_order" in signals("hi", quote_total_aed=250_000)


def test_signals_never_use_verdict_words():
    out = assess("We need 90 days credit, urgent. [EMAIL_1]@gmail.com", buyer_name="Gulf Star",
                 entries=(SanctionsEntry("Gulf Star", "QDe.999", "2001-01-01"),))
    text = " ".join(f"{s['signal']} {s['why']}" for s in out).lower()
    assert "fraud" not in text.replace("invoice-fraud pattern", "") and "sanctioned" not in text
    assert buyer_trust.needs_review(out)


def test_sanctions_matching_is_conservative():
    entries = (SanctionsEntry("Al Noor Trading Company", "QDe.900", "2010-05-01"),
               SanctionsEntry("Ahmed Example Person", "QDi.901", "2012-01-01"))
    hit = sanctions_signal("AL-NOOR TRADING CO. LLC", entries)
    assert hit["signal"] == "possible_sanctions_match" and "QDe.900" in hit["evidence"]
    assert sanctions_signal("Noor Gifts FZE", entries)["signal"] == "sanctions_no_close_match"
    assert sanctions_signal("Anything", None)["signal"] == "sanctions_list_not_loaded"
    assert normalise_name("Trading Al Noor LLC") == normalise_name("al noor")


def test_un_xml_loader(tmp_path):
    xml = """<CONSOLIDATED_LIST><INDIVIDUALS><INDIVIDUAL>
    <FIRST_NAME>AHMED</FIRST_NAME><SECOND_NAME>EXAMPLE</SECOND_NAME>
    <REFERENCE_NUMBER>QDi.901</REFERENCE_NUMBER><LISTED_ON>2012-01-01</LISTED_ON>
    <INDIVIDUAL_ALIAS><ALIAS_NAME>Abu Example</ALIAS_NAME></INDIVIDUAL_ALIAS></INDIVIDUAL></INDIVIDUALS>
    <ENTITIES><ENTITY><FIRST_NAME>AL NOOR TRADING COMPANY</FIRST_NAME><REFERENCE_NUMBER>QDe.900</REFERENCE_NUMBER>
    <LISTED_ON>2010-05-01</LISTED_ON></ENTITY></ENTITIES></CONSOLIDATED_LIST>"""
    path = tmp_path / "un.xml"
    path.write_text(xml, encoding="utf-8")
    names = {e.name for e in load_sanctions(path)}
    assert names == {"AHMED EXAMPLE", "Abu Example", "AL NOOR TRADING COMPANY"}
    assert load_sanctions(tmp_path / "missing.xml") is None
