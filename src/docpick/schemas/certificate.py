"""Certificate of Origin schema."""

from __future__ import annotations

from pydantic import Field

from docpick.schemas.base import DocumentSchema, schema_registry
from docpick.validation.rules import RegexRule, RequiredFieldRule


class CertificateItem(DocumentSchema):
    """A line item in a Certificate of Origin."""

    description: str | None = None
    hs_code: str | None = Field(None, description="HS code")
    quantity: str | None = None
    weight_kg: float | None = None
    value: float | None = None
    origin_criterion: str | None = Field(None, description="WO, PE, PSR, etc.")


class CertificateOfOriginSchema(DocumentSchema):
    """Certificate of Origin schema (Form A, APTA, RCEP, FTA-specific).

    Used to certify the country of origin of goods for customs
    and preferential tariff treatment.
    """

    # Header
    certificate_number: str | None = Field(None, description="Certificate reference number")
    certificate_type: str | None = Field(None, description="Form A, RCEP, APTA, etc.")
    issue_date: str | None = Field(None, description="Issue date (YYYY-MM-DD)")

    # Exporter
    exporter_name: str | None = None
    exporter_address: str | None = None
    exporter_country: str | None = Field(None, description="ISO 3166-1 alpha-2")

    # Importer / Consignee
    consignee_name: str | None = None
    consignee_address: str | None = None
    consignee_country: str | None = Field(None, description="ISO 3166-1 alpha-2")

    # Transport
    transport_means: str | None = Field(None, description="Vessel / Flight / Truck")
    port_of_loading: str | None = None
    port_of_discharge: str | None = None
    country_of_origin: str | None = Field(None, description="Origin country ISO alpha-2")

    # Items
    items: list[CertificateItem] = Field(default_factory=list)

    # Invoice reference
    invoice_number: str | None = None
    invoice_date: str | None = None

    # Certification
    certifying_authority: str | None = None
    stamp_or_seal: str | None = Field(None, description="Chamber of Commerce / Customs stamp")

    class ValidationRules:
        rules = [
            RequiredFieldRule("certificate_number"),
            RequiredFieldRule("exporter_name"),
            RequiredFieldRule("country_of_origin"),
            RegexRule("exporter_country", r"^[A-Z]{2}$", "ISO 3166-1 alpha-2 country code"),
            RegexRule("consignee_country", r"^[A-Z]{2}$", "ISO 3166-1 alpha-2 country code"),
            RegexRule("country_of_origin", r"^[A-Z]{2}$", "ISO 3166-1 alpha-2 country code"),
        ]


# Register
schema_registry.register("certificate_of_origin", CertificateOfOriginSchema)
