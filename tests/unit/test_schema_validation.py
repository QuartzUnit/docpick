"""Tests for schema-level validation integration."""

from docpick.schemas import InvoiceSchema, ReceiptSchema
from docpick.validation.base import Validator


# === InvoiceSchema ValidationRules ===

def test_invoice_has_validation_rules():
    rules_class = getattr(InvoiceSchema, "ValidationRules", None)
    assert rules_class is not None
    assert len(rules_class.rules) > 0


def test_invoice_validation_valid():
    data = {
        "invoice_number": "INV-001",
        "invoice_date": "2026-01-01",
        "due_date": "2026-02-01",
        "vendor_name": "Acme Corp",
        "vendor_tax_id": "1248100998",
        "total_amount": 110.0,
        "subtotal": 100.0,
        "tax_amount": 10.0,
        "line_items": [
            {"amount": 60.0},
            {"amount": 40.0},
        ],
    }
    validator = Validator(InvoiceSchema.ValidationRules.rules)
    result = validator.validate(data)
    assert result.is_valid
    assert result.rules_applied == 8
    assert len(result.errors) == 0


def test_invoice_validation_sum_error():
    data = {
        "invoice_number": "INV-001",
        "vendor_name": "Acme Corp",
        "total_amount": 200.0,
        "subtotal": 100.0,
        "tax_amount": 10.0,
    }
    validator = Validator(InvoiceSchema.ValidationRules.rules)
    result = validator.validate(data)
    assert not result.is_valid
    errors = [e for e in result.errors if e.rule == "sum_equals"]
    assert len(errors) > 0


def test_invoice_validation_date_error():
    data = {
        "invoice_number": "INV-001",
        "vendor_name": "Acme Corp",
        "total_amount": 100.0,
        "invoice_date": "2026-03-01",
        "due_date": "2026-01-01",  # Before invoice date
    }
    validator = Validator(InvoiceSchema.ValidationRules.rules)
    result = validator.validate(data)
    assert not result.is_valid
    errors = [e for e in result.errors if e.rule == "date_before"]
    assert len(errors) == 1


def test_invoice_validation_bad_tax_id():
    data = {
        "invoice_number": "INV-001",
        "vendor_name": "Acme Corp",
        "total_amount": 100.0,
        "vendor_tax_id": "1234567890",  # Invalid check digit
    }
    validator = Validator(InvoiceSchema.ValidationRules.rules)
    result = validator.validate(data)
    assert not result.is_valid
    errors = [e for e in result.errors if "checkdigit" in e.rule]
    assert len(errors) == 1


def test_invoice_validation_missing_required():
    data = {}  # No required fields
    validator = Validator(InvoiceSchema.ValidationRules.rules)
    result = validator.validate(data)
    # RequiredFieldRule returns warnings, not errors
    assert len(result.warnings) == 3  # invoice_number, vendor_name, total_amount


# === ReceiptSchema ValidationRules ===

def test_receipt_has_validation_rules():
    rules_class = getattr(ReceiptSchema, "ValidationRules", None)
    assert rules_class is not None
    assert len(rules_class.rules) > 0


def test_receipt_validation_valid():
    data = {
        "merchant_name": "Coffee Shop",
        "merchant_tax_id": "1248100998",
        "total": 33.0,
        "subtotal": 30.0,
        "tax": 3.0,
        "line_items": [
            {"total_price": 15.0},
            {"total_price": 15.0},
        ],
    }
    validator = Validator(ReceiptSchema.ValidationRules.rules)
    result = validator.validate(data)
    assert result.is_valid
    assert len(result.errors) == 0


def test_receipt_validation_sum_error():
    data = {
        "merchant_name": "Coffee Shop",
        "total": 100.0,
        "subtotal": 30.0,
        "tax": 3.0,
    }
    validator = Validator(ReceiptSchema.ValidationRules.rules)
    result = validator.validate(data)
    assert not result.is_valid


def test_receipt_validation_missing_required():
    data = {"subtotal": 10.0}
    validator = Validator(ReceiptSchema.ValidationRules.rules)
    result = validator.validate(data)
    assert len(result.warnings) == 2  # merchant_name, total
