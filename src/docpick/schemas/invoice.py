"""Invoice / Tax Invoice schema."""

from __future__ import annotations

from pydantic import Field

from docpick.schemas.base import DocumentSchema, schema_registry
from docpick.validation.checksum import CheckDigitRule
from docpick.validation.rules import DateBeforeRule, RequiredFieldRule, SumEqualsRule


class InvoiceLineItem(DocumentSchema):
    """A single line item in an invoice."""

    description: str | None = None
    quantity: float | None = None
    unit: str | None = None
    unit_price: float | None = None
    amount: float | None = None
    tax_rate: float | None = None
    hs_code: str | None = Field(None, description="HS code for customs")


class InvoiceSchema(DocumentSchema):
    """Universal Invoice / Tax Invoice (세금계산서) schema.

    Covers international commercial invoices and Korean e-Tax invoices.
    """

    # Header
    invoice_number: str | None = Field(None, description="Invoice ID / 승인번호")
    invoice_date: str | None = Field(None, description="Issue date (YYYY-MM-DD)")
    due_date: str | None = Field(None, description="Payment due date")
    currency: str | None = Field(None, description="ISO 4217 currency code (e.g., USD, KRW)")
    po_number: str | None = Field(None, description="Purchase Order reference")

    # Vendor / Supplier (공급자)
    vendor_name: str | None = Field(None, description="Supplier / 상호")
    vendor_address: str | None = None
    vendor_tax_id: str | None = Field(None, description="Business registration number / 사업자등록번호")
    vendor_representative: str | None = Field(None, description="Representative / 대표자")
    vendor_business_type: str | None = Field(None, description="업태")
    vendor_business_category: str | None = Field(None, description="종목")

    # Customer / Buyer (공급받는자)
    customer_name: str | None = Field(None, description="Buyer / 상호")
    customer_address: str | None = None
    customer_tax_id: str | None = Field(None, description="Buyer tax ID / 사업자등록번호")

    # Line items
    line_items: list[InvoiceLineItem] = Field(default_factory=list)

    # Totals
    subtotal: float | None = Field(None, description="Subtotal / 공급가액")
    tax_amount: float | None = Field(None, description="Tax / 세액")
    total_amount: float | None = Field(None, description="Grand total / 합계")

    # Payment
    payment_terms: str | None = None
    payment_method: str | None = None

    # Trade (for commercial invoices)
    incoterms: str | None = Field(None, description="Incoterms 2020 (e.g., FOB, CIF)")
    country_of_origin: str | None = None

    class ValidationRules:
        rules = [
            SumEqualsRule("line_items.amount", "subtotal"),
            SumEqualsRule(["subtotal", "tax_amount"], "total_amount"),
            DateBeforeRule("invoice_date", "due_date"),
            CheckDigitRule("vendor_tax_id", "kr_business_number"),
            CheckDigitRule("customer_tax_id", "kr_business_number"),
            RequiredFieldRule("invoice_number"),
            RequiredFieldRule("vendor_name"),
            RequiredFieldRule("total_amount"),
        ]


# Register
schema_registry.register("invoice", InvoiceSchema)
