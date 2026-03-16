"""Korean Electronic Tax Invoice (전자세금계산서) schema."""

from __future__ import annotations

from pydantic import Field

from docpick.schemas.base import DocumentSchema, schema_registry
from docpick.validation.checksum import CheckDigitRule
from docpick.validation.rules import (
    DateBeforeRule,
    RequiredFieldRule,
    SumEqualsRule,
)


class TaxInvoiceLineItem(DocumentSchema):
    """품목 (line item) in a Korean tax invoice."""

    supply_date: str | None = Field(None, description="공급일자 (YYYY-MM-DD)")
    item_name: str | None = Field(None, description="품목명")
    specification: str | None = Field(None, description="규격")
    quantity: float | None = Field(None, description="수량")
    unit_price: float | None = Field(None, description="단가")
    supply_amount: float | None = Field(None, description="공급가액")
    tax_amount: float | None = Field(None, description="세액")
    remark: str | None = Field(None, description="비고")


class KRTaxInvoiceSchema(DocumentSchema):
    """한국 전자세금계산서 (Korean e-Tax Invoice) schema.

    국세청 전자세금계산서 표준 서식 기반. 매출/매입 세금계산서 공통.
    """

    # 승인번호
    approval_number: str | None = Field(None, description="승인번호 (24자리)")
    issue_date: str | None = Field(None, description="작성일자 (YYYY-MM-DD)")

    # 공급자 (매출)
    supplier_business_number: str | None = Field(None, description="공급자 사업자등록번호 (10자리)")
    supplier_name: str | None = Field(None, description="공급자 상호")
    supplier_representative: str | None = Field(None, description="공급자 대표자")
    supplier_address: str | None = Field(None, description="공급자 사업장 주소")
    supplier_business_type: str | None = Field(None, description="업태")
    supplier_business_category: str | None = Field(None, description="종목")
    supplier_email: str | None = None

    # 공급받는자 (매입)
    buyer_business_number: str | None = Field(None, description="공급받는자 사업자등록번호 (10자리)")
    buyer_name: str | None = Field(None, description="공급받는자 상호")
    buyer_representative: str | None = Field(None, description="공급받는자 대표자")
    buyer_address: str | None = Field(None, description="공급받는자 사업장 주소")
    buyer_business_type: str | None = Field(None, description="업태")
    buyer_business_category: str | None = Field(None, description="종목")
    buyer_email: str | None = None

    # 품목
    line_items: list[TaxInvoiceLineItem] = Field(default_factory=list)

    # 합계
    total_supply_amount: float | None = Field(None, description="합계 공급가액")
    total_tax_amount: float | None = Field(None, description="합계 세액")
    total_amount: float | None = Field(None, description="합계 금액 (공급가액 + 세액)")

    # 기타
    cash_amount: float | None = Field(None, description="현금")
    check_amount: float | None = Field(None, description="수표")
    promissory_note_amount: float | None = Field(None, description="어음")
    receivable_amount: float | None = Field(None, description="외상미수금")
    remark: str | None = Field(None, description="비고")
    invoice_type: str | None = Field(None, description="일반 / 수정 / 영세율")

    class ValidationRules:
        rules = [
            RequiredFieldRule("supplier_business_number"),
            RequiredFieldRule("supplier_name"),
            RequiredFieldRule("buyer_business_number"),
            RequiredFieldRule("buyer_name"),
            RequiredFieldRule("total_supply_amount"),
            RequiredFieldRule("total_tax_amount"),
            CheckDigitRule("supplier_business_number", "kr_business_number"),
            CheckDigitRule("buyer_business_number", "kr_business_number"),
            SumEqualsRule("line_items.supply_amount", "total_supply_amount"),
            SumEqualsRule("line_items.tax_amount", "total_tax_amount"),
            SumEqualsRule(["total_supply_amount", "total_tax_amount"], "total_amount"),
        ]


# Register
schema_registry.register("kr_tax_invoice", KRTaxInvoiceSchema)
