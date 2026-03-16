"""Tests for cross-field validation rules."""

from docpick.validation.rules import (
    DateBeforeRule,
    FieldEqualsRule,
    RangeRule,
    RegexRule,
    RequiredFieldRule,
    SumEqualsRule,
)


# === SumEquals ===

def test_sum_equals_valid():
    rule = SumEqualsRule(["subtotal", "tax"], "total")
    result = rule.validate({"subtotal": 100.0, "tax": 10.0, "total": 110.0})
    assert result is None


def test_sum_equals_invalid():
    rule = SumEqualsRule(["subtotal", "tax"], "total")
    result = rule.validate({"subtotal": 100.0, "tax": 10.0, "total": 200.0})
    assert result is not None
    assert result.field == "total"
    assert "sum_equals" in result.rule


def test_sum_equals_tolerance():
    rule = SumEqualsRule(["a", "b"], "c", tolerance=0.05)
    result = rule.validate({"a": 10.0, "b": 20.0, "c": 30.04})
    assert result is None  # Within tolerance


def test_sum_equals_missing_source():
    rule = SumEqualsRule(["a", "b"], "c")
    result = rule.validate({"a": 10.0, "c": 30.0})
    assert result is None  # Can't validate


def test_sum_equals_missing_target():
    rule = SumEqualsRule(["a", "b"], "c")
    result = rule.validate({"a": 10.0, "b": 20.0})
    assert result is None


def test_sum_equals_array():
    rule = SumEqualsRule("line_items.amount", "subtotal")
    data = {
        "line_items": [
            {"amount": 50.0},
            {"amount": 30.0},
            {"amount": 20.0},
        ],
        "subtotal": 100.0,
    }
    result = rule.validate(data)
    assert result is None


def test_sum_equals_array_mismatch():
    rule = SumEqualsRule("line_items.amount", "subtotal")
    data = {
        "line_items": [
            {"amount": 50.0},
            {"amount": 30.0},
        ],
        "subtotal": 100.0,
    }
    result = rule.validate(data)
    assert result is not None


# === DateBefore ===

def test_date_before_valid():
    rule = DateBeforeRule("invoice_date", "due_date")
    result = rule.validate({"invoice_date": "2026-01-01", "due_date": "2026-02-01"})
    assert result is None


def test_date_before_invalid():
    rule = DateBeforeRule("invoice_date", "due_date")
    result = rule.validate({"invoice_date": "2026-03-01", "due_date": "2026-02-01"})
    assert result is not None
    assert "date_before" in result.rule


def test_date_before_equal():
    rule = DateBeforeRule("start", "end")
    result = rule.validate({"start": "2026-01-01", "end": "2026-01-01"})
    assert result is None  # Equal is OK


def test_date_before_missing():
    rule = DateBeforeRule("start", "end")
    result = rule.validate({"start": "2026-01-01"})
    assert result is None


# === RequiredField ===

def test_required_present():
    rule = RequiredFieldRule("name")
    result = rule.validate({"name": "Test"})
    assert result is None


def test_required_missing():
    rule = RequiredFieldRule("name")
    result = rule.validate({"other": "value"})
    assert result is not None
    assert "required" in result.rule


def test_required_empty_string():
    rule = RequiredFieldRule("name")
    result = rule.validate({"name": ""})
    assert result is not None


def test_required_whitespace():
    rule = RequiredFieldRule("name")
    result = rule.validate({"name": "   "})
    assert result is not None


# === FieldEquals ===

def test_field_equals_match():
    rule = FieldEqualsRule("bl.total_packages", "pl.total_packages")
    data = {"bl": {"total_packages": "100"}, "pl": {"total_packages": "100"}}
    assert rule.validate(data) is None


def test_field_equals_mismatch():
    rule = FieldEqualsRule("a", "b")
    result = rule.validate({"a": "100", "b": "200"})
    assert result is not None
    assert "field_equals" in result.rule


def test_field_equals_missing_field():
    rule = FieldEqualsRule("a", "b")
    assert rule.validate({"a": "100"}) is None


def test_field_equals_numeric_string():
    rule = FieldEqualsRule("a", "b")
    assert rule.validate({"a": 100, "b": "100"}) is None  # str() comparison


# === Range ===

def test_range_within():
    rule = RangeRule("amount", min_val=0, max_val=1000000)
    assert rule.validate({"amount": 500.0}) is None


def test_range_below_min():
    rule = RangeRule("amount", min_val=0)
    result = rule.validate({"amount": -10.0})
    assert result is not None
    assert "range" in result.rule


def test_range_above_max():
    rule = RangeRule("amount", max_val=1000)
    result = rule.validate({"amount": 2000.0})
    assert result is not None


def test_range_at_boundary():
    rule = RangeRule("x", min_val=0, max_val=100)
    assert rule.validate({"x": 0}) is None
    assert rule.validate({"x": 100}) is None


def test_range_missing_field():
    rule = RangeRule("amount", min_val=0)
    assert rule.validate({"other": 10}) is None


def test_range_non_numeric():
    rule = RangeRule("amount", min_val=0)
    result = rule.validate({"amount": "not-a-number"})
    assert result is not None
    assert "not numeric" in result.message


def test_range_min_only():
    rule = RangeRule("tax_rate", min_val=0)
    assert rule.validate({"tax_rate": 999999}) is None


def test_range_max_only():
    rule = RangeRule("discount", max_val=100)
    assert rule.validate({"discount": 50}) is None


# === Regex ===

def test_regex_match():
    rule = RegexRule("currency", r"^[A-Z]{3}$", "ISO 4217 currency code")
    assert rule.validate({"currency": "USD"}) is None


def test_regex_no_match():
    rule = RegexRule("currency", r"^[A-Z]{3}$", "ISO 4217 currency code")
    result = rule.validate({"currency": "usd"})
    assert result is not None
    assert "regex" in result.rule


def test_regex_missing_field():
    rule = RegexRule("code", r"^\d{4}$")
    assert rule.validate({"other": "x"}) is None


def test_regex_date_format():
    rule = RegexRule("date", r"^\d{4}-\d{2}-\d{2}$", "YYYY-MM-DD date format")
    assert rule.validate({"date": "2026-03-12"}) is None
    result = rule.validate({"date": "03/12/2026"})
    assert result is not None


def test_regex_hs_code():
    rule = RegexRule("hs_code", r"^\d{4,10}(\.\d+)?$", "HS code")
    assert rule.validate({"hs_code": "8471.30"}) is None
    assert rule.validate({"hs_code": "847130"}) is None
    result = rule.validate({"hs_code": "ABC"})
    assert result is not None
