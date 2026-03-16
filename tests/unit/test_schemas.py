"""Tests for schema system."""

import json

from docpick.schemas import schema_registry, InvoiceSchema, ReceiptSchema


def test_invoice_schema_fields():
    fields = InvoiceSchema.model_fields
    assert "invoice_number" in fields
    assert "vendor_name" in fields
    assert "total_amount" in fields
    assert "line_items" in fields


def test_receipt_schema_fields():
    fields = ReceiptSchema.model_fields
    assert "merchant_name" in fields
    assert "total" in fields
    assert "line_items" in fields


def test_schema_registry_list():
    names = schema_registry.names()
    assert "invoice" in names
    assert "receipt" in names


def test_schema_registry_get():
    cls = schema_registry.get("invoice")
    assert cls is InvoiceSchema


def test_schema_registry_unknown():
    import pytest
    with pytest.raises(KeyError, match="Unknown schema"):
        schema_registry.get("nonexistent")


def test_invoice_json_schema():
    schema = InvoiceSchema.model_json_schema()
    assert "properties" in schema
    assert "invoice_number" in schema["properties"]
    json_str = json.dumps(schema)
    assert len(json_str) > 100


def test_invoice_create():
    inv = InvoiceSchema(
        invoice_number="INV-001",
        vendor_name="Test Corp",
        total_amount=1000.0,
    )
    assert inv.invoice_number == "INV-001"
    assert inv.total_amount == 1000.0


def test_invoice_extra_fields():
    inv = InvoiceSchema(
        invoice_number="INV-001",
        total_amount=500.0,
        custom_field="extra",
    )
    assert inv.custom_field == "extra"
