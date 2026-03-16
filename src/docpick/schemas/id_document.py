"""ID Document schema — Passport, National ID, Driver's License (MRZ support)."""

from __future__ import annotations

from pydantic import Field

from docpick.schemas.base import DocumentSchema, schema_registry
from docpick.validation.rules import DateBeforeRule, RegexRule, RequiredFieldRule


class IDDocumentSchema(DocumentSchema):
    """ID Document schema with MRZ (Machine Readable Zone) support.

    Covers ICAO Doc 9303 compliant documents: passports, ID cards,
    and travel documents with MRZ.
    """

    # Document
    document_type: str | None = Field(None, description="P (passport), I (ID card), D (driver's license)")
    document_number: str | None = None
    issuing_country: str | None = Field(None, description="ISO 3166-1 alpha-3 country code")
    issuing_authority: str | None = None

    # Personal
    surname: str | None = None
    given_names: str | None = None
    nationality: str | None = Field(None, description="ISO 3166-1 alpha-3")
    date_of_birth: str | None = Field(None, description="YYYY-MM-DD")
    sex: str | None = Field(None, description="M / F / X")
    place_of_birth: str | None = None

    # Validity
    date_of_issue: str | None = Field(None, description="YYYY-MM-DD")
    date_of_expiry: str | None = Field(None, description="YYYY-MM-DD")

    # MRZ (Machine Readable Zone)
    mrz_line_1: str | None = Field(None, description="MRZ first line (44 chars for passport)")
    mrz_line_2: str | None = Field(None, description="MRZ second line (44 chars for passport)")
    mrz_line_3: str | None = Field(None, description="MRZ third line (for ID cards, 30 chars)")

    # Additional (varies by document type)
    personal_number: str | None = Field(None, description="Korean 주민등록번호 or national ID number")
    address: str | None = None
    driver_license_class: str | None = Field(None, description="License class (1종/2종 or A/B/C)")

    class ValidationRules:
        rules = [
            RequiredFieldRule("document_number"),
            RequiredFieldRule("surname"),
            RequiredFieldRule("given_names"),
            RequiredFieldRule("date_of_birth"),
            DateBeforeRule("date_of_birth", "date_of_issue"),
            DateBeforeRule("date_of_issue", "date_of_expiry"),
            RegexRule("issuing_country", r"^[A-Z]{3}$", "ISO 3166-1 alpha-3 country code"),
            RegexRule("nationality", r"^[A-Z]{3}$", "ISO 3166-1 alpha-3 country code"),
            RegexRule("sex", r"^[MFX]$", "Sex code (M/F/X)"),
        ]


# Register
schema_registry.register("id_document", IDDocumentSchema)
