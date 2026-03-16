"""Receipt schema."""

from __future__ import annotations

from pydantic import Field

from docpick.schemas.base import DocumentSchema, schema_registry
from docpick.validation.checksum import CheckDigitRule
from docpick.validation.rules import RequiredFieldRule, SumEqualsRule


class ReceiptLineItem(DocumentSchema):
    """A single item on a receipt."""

    description: str | None = None
    quantity: float | None = None
    unit_price: float | None = None
    total_price: float | None = None
    category: str | None = None


class ReceiptSchema(DocumentSchema):
    """Receipt schema for retail, restaurant, and expense receipts."""

    # Merchant
    merchant_name: str | None = None
    merchant_address: str | None = None
    merchant_phone: str | None = None
    merchant_tax_id: str | None = Field(None, description="Business registration number")

    # Transaction
    receipt_number: str | None = None
    transaction_date: str | None = Field(None, description="Date (YYYY-MM-DD)")
    transaction_time: str | None = Field(None, description="Time (HH:MM)")

    # Items
    line_items: list[ReceiptLineItem] = Field(default_factory=list)

    # Totals
    subtotal: float | None = None
    tax: float | None = None
    tip: float | None = None
    total: float | None = None
    currency: str | None = Field(None, description="ISO 4217 currency code")

    # Payment
    payment_method: str | None = Field(None, description="CASH, CARD, etc.")
    card_last_four: str | None = None

    class ValidationRules:
        rules = [
            SumEqualsRule("line_items.total_price", "subtotal"),
            SumEqualsRule(["subtotal", "tax"], "total"),
            CheckDigitRule("merchant_tax_id", "kr_business_number"),
            RequiredFieldRule("merchant_name"),
            RequiredFieldRule("total"),
        ]


# Register
schema_registry.register("receipt", ReceiptSchema)
