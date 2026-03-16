"""Tests for checksum validation algorithms."""

import pytest

from docpick.validation.checksum import (
    CheckDigitRule,
    verify_awb_mod7,
    verify_iban_mod97,
    verify_iso_6346,
    verify_kr_business_number,
    verify_luhn,
)


# === Korean Business Number ===

def test_kr_business_valid():
    # Known valid numbers (format: XXX-XX-XXXXX)
    assert verify_kr_business_number("1248100998") is True
    assert verify_kr_business_number("124-81-00998") is True


def test_kr_business_invalid():
    assert verify_kr_business_number("1234567890") is False
    assert verify_kr_business_number("1111111111") is False


def test_kr_business_wrong_length():
    assert verify_kr_business_number("12345") is False
    assert verify_kr_business_number("12345678901") is False


def test_kr_business_non_numeric():
    assert verify_kr_business_number("123456789a") is False


# === Luhn ===

def test_luhn_valid():
    assert verify_luhn("4532015112830366") is True
    assert verify_luhn("79927398713") is True


def test_luhn_invalid():
    assert verify_luhn("4532015112830367") is False
    assert verify_luhn("1234567890") is False


def test_luhn_with_spaces():
    assert verify_luhn("4532 0151 1283 0366") is True


# === ISO 6346 Container Number ===

def test_iso_6346_valid():
    assert verify_iso_6346("CSQU3054383") is True


def test_iso_6346_invalid():
    assert verify_iso_6346("CSQU3054380") is False


def test_iso_6346_wrong_format():
    assert verify_iso_6346("12345678901") is False
    assert verify_iso_6346("ABCD") is False


# === CheckDigitRule ===

def test_checkdigit_rule_valid():
    rule = CheckDigitRule(field="tax_id", algorithm="kr_business_number")
    result = rule.validate({"tax_id": "1248100998"})
    assert result is None  # Valid


def test_checkdigit_rule_invalid():
    rule = CheckDigitRule(field="tax_id", algorithm="kr_business_number")
    result = rule.validate({"tax_id": "1234567890"})
    assert result is not None
    assert result.field == "tax_id"


def test_checkdigit_rule_missing_field():
    rule = CheckDigitRule(field="tax_id", algorithm="kr_business_number")
    result = rule.validate({"other": "value"})
    assert result is None  # Skip if field missing


def test_checkdigit_unknown_algorithm():
    with pytest.raises(ValueError, match="Unknown algorithm"):
        CheckDigitRule(field="x", algorithm="nonexistent")


# === AWB Modulus 7 ===

def test_awb_mod7_valid():
    # Format: PPP-NNNNNNNC (airline prefix 3 + serial 7 + check 1)
    # Serial 1234567 % 7 = 5, so check digit = 5
    assert verify_awb_mod7("180-12345675") is True


def test_awb_mod7_valid_no_dash():
    assert verify_awb_mod7("18012345675") is True


def test_awb_mod7_invalid():
    assert verify_awb_mod7("180-12345670") is False


def test_awb_mod7_wrong_length():
    assert verify_awb_mod7("12345") is False
    assert verify_awb_mod7("123456789012") is False


def test_awb_mod7_non_numeric():
    assert verify_awb_mod7("18012345A75") is False


# === IBAN Modulus 97 ===

def test_iban_mod97_valid():
    # GB82 WEST 1234 5698 7654 32 — known valid IBAN
    assert verify_iban_mod97("GB82WEST12345698765432") is True


def test_iban_mod97_valid_with_spaces():
    assert verify_iban_mod97("GB82 WEST 1234 5698 7654 32") is True


def test_iban_mod97_valid_de():
    # DE89 3704 0044 0532 0130 00
    assert verify_iban_mod97("DE89370400440532013000") is True


def test_iban_mod97_invalid():
    assert verify_iban_mod97("GB82WEST12345698765433") is False


def test_iban_mod97_too_short():
    assert verify_iban_mod97("GB82") is False


def test_iban_mod97_bad_format():
    assert verify_iban_mod97("1234567890") is False


# === CheckDigitRule with new algorithms ===

def test_checkdigit_rule_awb():
    rule = CheckDigitRule(field="awb_number", algorithm="awb_mod7")
    assert rule.validate({"awb_number": "18012345675"}) is None
    result = rule.validate({"awb_number": "18012345670"})
    assert result is not None


def test_checkdigit_rule_iban():
    rule = CheckDigitRule(field="iban", algorithm="iban_mod97")
    assert rule.validate({"iban": "DE89370400440532013000"}) is None
    result = rule.validate({"iban": "DE89370400440532013001"})
    assert result is not None
