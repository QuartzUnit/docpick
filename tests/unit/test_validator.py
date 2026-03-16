"""Tests for Validator class integration."""

from docpick.validation.base import Validator
from docpick.validation.checksum import CheckDigitRule
from docpick.validation.rules import (
    DateBeforeRule,
    FieldEqualsRule,
    RangeRule,
    RegexRule,
    RequiredFieldRule,
    SumEqualsRule,
)


def test_validator_empty_rules():
    v = Validator()
    result = v.validate({"x": 1})
    assert result.is_valid
    assert result.rules_applied == 0
    assert result.rules_passed == 0


def test_validator_all_pass():
    v = Validator([
        RequiredFieldRule("name"),
        RangeRule("age", min_val=0, max_val=150),
    ])
    result = v.validate({"name": "Test", "age": 30})
    assert result.is_valid
    assert result.rules_applied == 2
    assert result.rules_passed == 2


def test_validator_mixed_errors_warnings():
    v = Validator([
        RequiredFieldRule("name"),           # Warning (missing)
        RangeRule("age", min_val=0),         # Error (negative)
        RegexRule("email", r"@"),            # Pass
    ])
    result = v.validate({"age": -5, "email": "a@b.com"})
    assert not result.is_valid
    assert len(result.errors) == 1       # age range
    assert len(result.warnings) == 1     # name required


def test_validator_complex_rules():
    """Test Validator with a realistic set of invoice-like rules."""
    v = Validator([
        SumEqualsRule(["subtotal", "tax"], "total"),
        DateBeforeRule("issue_date", "due_date"),
        CheckDigitRule("tax_id", "kr_business_number"),
        RequiredFieldRule("invoice_no"),
        FieldEqualsRule("ship_qty", "received_qty"),
        RangeRule("total", min_val=0),
        RegexRule("currency", r"^[A-Z]{3}$"),
    ])
    data = {
        "invoice_no": "INV-001",
        "issue_date": "2026-01-01",
        "due_date": "2026-02-01",
        "tax_id": "1248100998",
        "subtotal": 100.0,
        "tax": 10.0,
        "total": 110.0,
        "ship_qty": "50",
        "received_qty": "50",
        "currency": "KRW",
    }
    result = v.validate(data)
    assert result.is_valid
    assert result.rules_applied == 7
    assert result.rules_passed == 7


def test_validator_multiple_errors():
    v = Validator([
        SumEqualsRule(["a", "b"], "c"),
        RangeRule("x", min_val=0),
        RegexRule("code", r"^\d+$"),
    ])
    data = {
        "a": 10,
        "b": 20,
        "c": 999,     # sum error
        "x": -1,      # range error
        "code": "abc", # regex error
    }
    result = v.validate(data)
    assert not result.is_valid
    assert len(result.errors) == 3


def test_validator_warnings_count_as_passed():
    v = Validator([RequiredFieldRule("missing_field")])
    result = v.validate({})
    assert result.is_valid  # warnings don't make it invalid
    assert result.rules_passed == 1
    assert len(result.warnings) == 1
