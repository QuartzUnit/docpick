"""Purchase Order (PO) schema."""

from __future__ import annotations

from pydantic import Field

from docpick.schemas.base import DocumentSchema, schema_registry
from docpick.validation.rules import (
    DateBeforeRule,
    RegexRule,
    RequiredFieldRule,
    SumEqualsRule,
)


class POLineItem(DocumentSchema):
    """A single line item in a purchase order."""

    line_number: int | None = None
    item_number: str | None = Field(None, description="SKU / Part number")
    description: str | None = None
    quantity: float | None = None
    unit: str | None = Field(None, description="EA, KG, M, etc.")
    unit_price: float | None = None
    amount: float | None = None
    hs_code: str | None = Field(None, description="HS code for customs")
    delivery_date: str | None = Field(None, description="Required delivery date (YYYY-MM-DD)")


class PurchaseOrderSchema(DocumentSchema):
    """Purchase Order schema for procurement automation."""

    # Header
    po_number: str | None = Field(None, description="Purchase Order number")
    po_date: str | None = Field(None, description="Issue date (YYYY-MM-DD)")
    revision: str | None = None

    # Buyer
    buyer_name: str | None = None
    buyer_address: str | None = None
    buyer_contact: str | None = None
    buyer_tax_id: str | None = None

    # Seller / Supplier
    seller_name: str | None = None
    seller_address: str | None = None
    seller_contact: str | None = None
    seller_tax_id: str | None = None

    # Line items
    line_items: list[POLineItem] = Field(default_factory=list)

    # Totals
    subtotal: float | None = None
    tax_amount: float | None = None
    total_amount: float | None = None
    currency: str | None = Field(None, description="ISO 4217 currency code")

    # Terms
    payment_terms: str | None = Field(None, description="Net 30, L/C, T/T, etc.")
    delivery_terms: str | None = Field(None, description="Incoterms (FOB, CIF, etc.)")
    delivery_date: str | None = Field(None, description="Required delivery date (YYYY-MM-DD)")
    ship_to_address: str | None = None

    # Additional
    notes: str | None = None

    class ValidationRules:
        rules = [
            RequiredFieldRule("po_number"),
            RequiredFieldRule("buyer_name"),
            RequiredFieldRule("seller_name"),
            RequiredFieldRule("total_amount"),
            SumEqualsRule("line_items.amount", "subtotal"),
            SumEqualsRule(["subtotal", "tax_amount"], "total_amount"),
            DateBeforeRule("po_date", "delivery_date"),
            RegexRule("currency", r"^[A-Z]{3}$", "ISO 4217 currency"),
        ]


# Register
schema_registry.register("purchase_order", PurchaseOrderSchema)
