"""Bank Statement schema."""

from __future__ import annotations

from pydantic import Field

from docpick.schemas.base import DocumentSchema, schema_registry
from docpick.validation.checksum import CheckDigitRule
from docpick.validation.rules import DateBeforeRule, RangeRule, RequiredFieldRule, SumEqualsRule


class Transaction(DocumentSchema):
    """A single transaction in a bank statement."""

    date: str | None = Field(None, description="Transaction date (YYYY-MM-DD)")
    description: str | None = None
    reference: str | None = None
    debit: float | None = Field(None, description="Withdrawal amount")
    credit: float | None = Field(None, description="Deposit amount")
    balance: float | None = Field(None, description="Running balance after transaction")
    category: str | None = None


class BankStatementSchema(DocumentSchema):
    """Bank Statement schema for financial document extraction.

    Supports monthly/quarterly statements from retail and corporate banks.
    """

    # Account
    bank_name: str | None = None
    branch_name: str | None = None
    account_number: str | None = None
    account_holder: str | None = None
    iban: str | None = Field(None, description="IBAN (international)")
    currency: str | None = Field(None, description="ISO 4217 currency code")

    # Period
    statement_date: str | None = Field(None, description="Statement date (YYYY-MM-DD)")
    period_start: str | None = Field(None, description="Period start (YYYY-MM-DD)")
    period_end: str | None = Field(None, description="Period end (YYYY-MM-DD)")

    # Balances
    opening_balance: float | None = None
    closing_balance: float | None = None
    total_debits: float | None = None
    total_credits: float | None = None

    # Transactions
    transactions: list[Transaction] = Field(default_factory=list)

    class ValidationRules:
        rules = [
            RequiredFieldRule("account_number"),
            RequiredFieldRule("opening_balance"),
            RequiredFieldRule("closing_balance"),
            DateBeforeRule("period_start", "period_end"),
            CheckDigitRule("iban", "iban_mod97"),
        ]


# Register
schema_registry.register("bank_statement", BankStatementSchema)
