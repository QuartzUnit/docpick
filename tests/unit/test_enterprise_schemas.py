"""Tests for enterprise document schemas (Phase 4)."""

import json

from docpick.schemas import (
    BankStatementSchema,
    BillOfLadingSchema,
    CertificateOfOriginSchema,
    IDDocumentSchema,
    KRTaxInvoiceSchema,
    PurchaseOrderSchema,
    schema_registry,
)
from docpick.validation.base import Validator


# === Schema Registry ===

def test_all_schemas_registered():
    names = schema_registry.names()
    expected = [
        "bank_statement", "bill_of_lading", "certificate_of_origin",
        "id_document", "invoice", "kr_tax_invoice", "purchase_order", "receipt",
    ]
    for name in expected:
        assert name in names, f"Schema '{name}' not registered"


def test_registry_has_8_schemas():
    assert len(schema_registry.names()) == 8


# === Bill of Lading ===

def test_bl_schema_fields():
    fields = BillOfLadingSchema.model_fields
    assert "bl_number" in fields
    assert "shipper_name" in fields
    assert "consignee_name" in fields
    assert "port_of_loading" in fields
    assert "containers" in fields
    assert "total_gross_weight_kg" in fields


def test_bl_json_schema():
    schema = BillOfLadingSchema.model_json_schema()
    assert "properties" in schema
    assert len(json.dumps(schema)) > 200


def test_bl_validation_valid():
    data = {
        "bl_number": "MSKU1234567",
        "shipper_name": "Acme Corp",
        "consignee_name": "Buyer Inc",
        "port_of_loading": "KRPUS",
        "port_of_discharge": "USNYC",
        "shipped_on_board_date": "2026-03-01",
        "issue_date": "2026-03-02",
        "hs_code": "8471.30",
        "freight_currency": "USD",
        "total_gross_weight_kg": 5000.0,
        "containers": [
            {"gross_weight_kg": 2500.0},
            {"gross_weight_kg": 2500.0},
        ],
    }
    validator = Validator(BillOfLadingSchema.ValidationRules.rules)
    result = validator.validate(data)
    assert result.is_valid


def test_bl_validation_container_weight_mismatch():
    data = {
        "bl_number": "BL-001",
        "shipper_name": "X",
        "consignee_name": "Y",
        "port_of_loading": "KRPUS",
        "port_of_discharge": "USNYC",
        "total_gross_weight_kg": 10000.0,
        "containers": [
            {"gross_weight_kg": 3000.0},
            {"gross_weight_kg": 2000.0},
        ],
    }
    validator = Validator(BillOfLadingSchema.ValidationRules.rules)
    result = validator.validate(data)
    assert not result.is_valid
    errors = [e for e in result.errors if e.rule == "sum_equals"]
    assert len(errors) >= 1


# === Purchase Order ===

def test_po_schema_fields():
    fields = PurchaseOrderSchema.model_fields
    assert "po_number" in fields
    assert "buyer_name" in fields
    assert "seller_name" in fields
    assert "line_items" in fields
    assert "total_amount" in fields


def test_po_validation_valid():
    data = {
        "po_number": "PO-2026-001",
        "buyer_name": "Buyer Corp",
        "seller_name": "Seller Inc",
        "total_amount": 110.0,
        "subtotal": 100.0,
        "tax_amount": 10.0,
        "currency": "USD",
        "po_date": "2026-01-01",
        "delivery_date": "2026-03-01",
        "line_items": [{"amount": 60.0}, {"amount": 40.0}],
    }
    validator = Validator(PurchaseOrderSchema.ValidationRules.rules)
    result = validator.validate(data)
    assert result.is_valid


def test_po_validation_sum_error():
    data = {
        "po_number": "PO-001",
        "buyer_name": "X",
        "seller_name": "Y",
        "total_amount": 500.0,
        "subtotal": 100.0,
        "tax_amount": 10.0,
    }
    validator = Validator(PurchaseOrderSchema.ValidationRules.rules)
    result = validator.validate(data)
    assert not result.is_valid


# === Certificate of Origin ===

def test_co_schema_fields():
    fields = CertificateOfOriginSchema.model_fields
    assert "certificate_number" in fields
    assert "exporter_name" in fields
    assert "country_of_origin" in fields
    assert "items" in fields


def test_co_validation_valid():
    data = {
        "certificate_number": "CO-2026-001",
        "exporter_name": "Exporter Corp",
        "country_of_origin": "KR",
        "exporter_country": "KR",
        "consignee_country": "US",
    }
    validator = Validator(CertificateOfOriginSchema.ValidationRules.rules)
    result = validator.validate(data)
    assert result.is_valid


def test_co_validation_bad_country_code():
    data = {
        "certificate_number": "CO-001",
        "exporter_name": "X",
        "country_of_origin": "Korea",  # Should be 2-letter code
        "exporter_country": "KR",
    }
    validator = Validator(CertificateOfOriginSchema.ValidationRules.rules)
    result = validator.validate(data)
    assert not result.is_valid


# === Bank Statement ===

def test_bank_statement_fields():
    fields = BankStatementSchema.model_fields
    assert "account_number" in fields
    assert "opening_balance" in fields
    assert "closing_balance" in fields
    assert "transactions" in fields
    assert "iban" in fields


def test_bank_statement_validation_valid():
    data = {
        "account_number": "123-456-789",
        "opening_balance": 10000.0,
        "closing_balance": 12000.0,
        "period_start": "2026-01-01",
        "period_end": "2026-01-31",
        "iban": "DE89370400440532013000",
    }
    validator = Validator(BankStatementSchema.ValidationRules.rules)
    result = validator.validate(data)
    assert result.is_valid


def test_bank_statement_bad_iban():
    data = {
        "account_number": "123",
        "opening_balance": 10000.0,
        "closing_balance": 12000.0,
        "iban": "DE00000000000000000000",  # Invalid IBAN
    }
    validator = Validator(BankStatementSchema.ValidationRules.rules)
    result = validator.validate(data)
    assert not result.is_valid


# === Korean Tax Invoice ===

def test_kr_tax_invoice_fields():
    fields = KRTaxInvoiceSchema.model_fields
    assert "supplier_business_number" in fields
    assert "buyer_business_number" in fields
    assert "total_supply_amount" in fields
    assert "total_tax_amount" in fields
    assert "line_items" in fields


def test_kr_tax_invoice_validation_valid():
    data = {
        "supplier_business_number": "1248100998",
        "supplier_name": "공급자 상호",
        "buyer_business_number": "1248100998",
        "buyer_name": "공급받는자 상호",
        "total_supply_amount": 100000.0,
        "total_tax_amount": 10000.0,
        "total_amount": 110000.0,
        "line_items": [
            {"supply_amount": 60000.0, "tax_amount": 6000.0},
            {"supply_amount": 40000.0, "tax_amount": 4000.0},
        ],
    }
    validator = Validator(KRTaxInvoiceSchema.ValidationRules.rules)
    result = validator.validate(data)
    assert result.is_valid


def test_kr_tax_invoice_bad_business_number():
    data = {
        "supplier_business_number": "1234567890",  # Invalid
        "supplier_name": "테스트",
        "buyer_business_number": "1248100998",
        "buyer_name": "테스트2",
        "total_supply_amount": 100.0,
        "total_tax_amount": 10.0,
    }
    validator = Validator(KRTaxInvoiceSchema.ValidationRules.rules)
    result = validator.validate(data)
    assert not result.is_valid
    errors = [e for e in result.errors if "checkdigit" in e.rule]
    assert len(errors) == 1


def test_kr_tax_invoice_sum_mismatch():
    data = {
        "supplier_business_number": "1248100998",
        "supplier_name": "X",
        "buyer_business_number": "1248100998",
        "buyer_name": "Y",
        "total_supply_amount": 100.0,
        "total_tax_amount": 10.0,
        "total_amount": 999.0,  # Should be 110
    }
    validator = Validator(KRTaxInvoiceSchema.ValidationRules.rules)
    result = validator.validate(data)
    assert not result.is_valid


# === ID Document ===

def test_id_document_fields():
    fields = IDDocumentSchema.model_fields
    assert "document_number" in fields
    assert "surname" in fields
    assert "given_names" in fields
    assert "date_of_birth" in fields
    assert "mrz_line_1" in fields
    assert "nationality" in fields


def test_id_document_validation_valid():
    data = {
        "document_number": "M12345678",
        "surname": "KIM",
        "given_names": "MINJUNG",
        "date_of_birth": "1990-01-15",
        "date_of_issue": "2020-06-01",
        "date_of_expiry": "2030-06-01",
        "issuing_country": "KOR",
        "nationality": "KOR",
        "sex": "F",
    }
    validator = Validator(IDDocumentSchema.ValidationRules.rules)
    result = validator.validate(data)
    assert result.is_valid


def test_id_document_bad_country_code():
    data = {
        "document_number": "P123456",
        "surname": "PARK",
        "given_names": "JIHOON",
        "date_of_birth": "1985-05-20",
        "issuing_country": "KOREA",  # Should be 3-letter
        "nationality": "KOR",
        "sex": "M",
    }
    validator = Validator(IDDocumentSchema.ValidationRules.rules)
    result = validator.validate(data)
    assert not result.is_valid


def test_id_document_expired():
    data = {
        "document_number": "D999999",
        "surname": "LEE",
        "given_names": "SOOJIN",
        "date_of_birth": "1995-12-01",
        "date_of_issue": "2025-01-01",
        "date_of_expiry": "2020-01-01",  # Expiry before issue
        "nationality": "KOR",
        "sex": "F",
    }
    validator = Validator(IDDocumentSchema.ValidationRules.rules)
    result = validator.validate(data)
    assert not result.is_valid
    errors = [e for e in result.errors if e.rule == "date_before"]
    assert len(errors) >= 1
