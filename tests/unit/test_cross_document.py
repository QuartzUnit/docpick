"""Tests for cross-document validation."""

from docpick.validation.cross_document import (
    CrossDocumentValidator,
    create_trade_document_validator,
)


# === CrossDocumentValidator basics ===

def test_cross_doc_equals_valid():
    v = CrossDocumentValidator()
    v.add_mapping("bl", "total_packages", "pl", "total_packages", "equals")
    result = v.validate({
        "bl": {"total_packages": 100},
        "pl": {"total_packages": 100},
    })
    assert result.is_valid
    assert result.checks_passed == 1


def test_cross_doc_equals_mismatch():
    v = CrossDocumentValidator()
    v.add_mapping("bl", "total_packages", "pl", "total_packages", "equals")
    result = v.validate({
        "bl": {"total_packages": 100},
        "pl": {"total_packages": 200},
    })
    assert not result.is_valid
    assert len(result.errors) == 1
    assert "cross_equals" in result.errors[0].rule


def test_cross_doc_equals_string():
    v = CrossDocumentValidator()
    v.add_mapping("invoice", "vendor_name", "bl", "shipper_name", "equals")
    result = v.validate({
        "invoice": {"vendor_name": "Acme Corp"},
        "bl": {"shipper_name": "Acme Corp"},
    })
    assert result.is_valid


def test_cross_doc_equals_string_case_insensitive():
    v = CrossDocumentValidator()
    v.add_mapping("a", "name", "b", "name", "equals")
    result = v.validate({
        "a": {"name": "ACME CORP"},
        "b": {"name": "acme corp"},
    })
    assert result.is_valid


def test_cross_doc_lte_valid():
    v = CrossDocumentValidator()
    v.add_mapping("invoice", "total", "lc", "amount", "less_than_or_equal",
                  description="Invoice total ≤ L/C amount")
    result = v.validate({
        "invoice": {"total": 9000.0},
        "lc": {"amount": 10000.0},
    })
    assert result.is_valid


def test_cross_doc_lte_exceeded():
    v = CrossDocumentValidator()
    v.add_mapping("invoice", "total", "lc", "amount", "less_than_or_equal")
    result = v.validate({
        "invoice": {"total": 15000.0},
        "lc": {"amount": 10000.0},
    })
    assert not result.is_valid
    assert "cross_lte" in result.errors[0].rule


def test_cross_doc_contains_valid():
    v = CrossDocumentValidator()
    v.add_mapping("invoice", "vendor_name", "bl", "shipper_name", "contains")
    result = v.validate({
        "invoice": {"vendor_name": "Acme"},
        "bl": {"shipper_name": "Acme Corporation Ltd."},
    })
    assert result.is_valid


def test_cross_doc_contains_mismatch():
    v = CrossDocumentValidator()
    v.add_mapping("invoice", "vendor_name", "bl", "shipper_name", "contains")
    result = v.validate({
        "invoice": {"vendor_name": "Acme Corp"},
        "bl": {"shipper_name": "Globex Industries"},
    })
    assert not result.is_valid


def test_cross_doc_missing_document():
    v = CrossDocumentValidator()
    v.add_mapping("invoice", "total", "bl", "freight", "equals")
    result = v.validate({
        "invoice": {"total": 1000},
        # "bl" is missing
    })
    # Should skip, not error
    assert result.is_valid


def test_cross_doc_missing_field():
    v = CrossDocumentValidator()
    v.add_mapping("invoice", "total", "bl", "freight", "equals")
    result = v.validate({
        "invoice": {"total": 1000},
        "bl": {},  # field missing
    })
    assert result.is_valid


def test_cross_doc_numeric_tolerance():
    v = CrossDocumentValidator()
    v.add_mapping("bl", "weight", "pl", "weight", "equals", tolerance=0.5)
    result = v.validate({
        "bl": {"weight": 5000.3},
        "pl": {"weight": 5000.0},
    })
    assert result.is_valid


def test_cross_doc_multiple_checks():
    v = CrossDocumentValidator()
    v.add_mapping("a", "x", "b", "x", "equals")
    v.add_mapping("a", "y", "b", "y", "equals")
    v.add_mapping("a", "z", "b", "z", "equals")
    result = v.validate({
        "a": {"x": 1, "y": 2, "z": 3},
        "b": {"x": 1, "y": 2, "z": 99},
    })
    assert not result.is_valid
    assert result.checks_passed == 2
    assert len(result.errors) == 1


# === Pre-configured trade document validator ===

def test_trade_validator_valid():
    v = create_trade_document_validator()
    result = v.validate({
        "invoice": {
            "vendor_name": "Acme Corp",
            "customer_name": "Buyer Inc",
            "country_of_origin": "KR",
        },
        "bl": {
            "shipper_name": "Acme Corporation",
            "consignee_name": "Buyer Inc.",
            "total_gross_weight_kg": 5000.0,
            "total_packages": 100,
        },
        "packing_list": {
            "total_gross_weight_kg": 5000.0,
            "total_packages": 100,
        },
        "certificate": {
            "country_of_origin": "KR",
        },
    })
    assert result.is_valid


def test_trade_validator_weight_mismatch():
    v = create_trade_document_validator()
    result = v.validate({
        "bl": {
            "total_gross_weight_kg": 5000.0,
            "total_packages": 100,
        },
        "packing_list": {
            "total_gross_weight_kg": 4500.0,  # Mismatch!
            "total_packages": 100,
        },
    })
    assert not result.is_valid
