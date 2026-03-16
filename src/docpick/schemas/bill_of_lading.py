"""Bill of Lading (B/L) schema — Ocean / Air / Multimodal."""

from __future__ import annotations

from pydantic import Field

from docpick.schemas.base import DocumentSchema, schema_registry
from docpick.validation.checksum import CheckDigitRule
from docpick.validation.rules import (
    DateBeforeRule,
    RegexRule,
    RequiredFieldRule,
    SumEqualsRule,
)


class ContainerDetail(DocumentSchema):
    """Container information on a B/L."""

    container_number: str | None = Field(None, description="Container number (ISO 6346)")
    seal_number: str | None = None
    container_type: str | None = Field(None, description="20GP, 40HC, etc.")
    packages: int | None = None
    gross_weight_kg: float | None = None
    measurement_cbm: float | None = None


class BillOfLadingSchema(DocumentSchema):
    """Bill of Lading schema (Ocean B/L, Sea Waybill, Multimodal).

    Covers FIATA FBL, liner B/L, and charter party B/L formats.
    """

    # Header
    bl_number: str | None = Field(None, description="B/L number")
    bl_type: str | None = Field(None, description="Original / Waybill / Surrendered")
    booking_number: str | None = None

    # Parties
    shipper_name: str | None = None
    shipper_address: str | None = None
    consignee_name: str | None = Field(None, description="Consignee / To Order")
    consignee_address: str | None = None
    notify_party_name: str | None = None
    notify_party_address: str | None = None

    # Vessel & Route
    vessel_name: str | None = None
    voyage_number: str | None = None
    port_of_loading: str | None = Field(None, description="POL (UN/LOCODE)")
    port_of_discharge: str | None = Field(None, description="POD (UN/LOCODE)")
    place_of_receipt: str | None = None
    place_of_delivery: str | None = None

    # Dates
    shipped_on_board_date: str | None = Field(None, description="On-board date (YYYY-MM-DD)")
    issue_date: str | None = Field(None, description="B/L issue date (YYYY-MM-DD)")

    # Cargo
    containers: list[ContainerDetail] = Field(default_factory=list)
    description_of_goods: str | None = None
    hs_code: str | None = Field(None, description="HS code (harmonized system)")

    # Totals
    total_packages: int | None = None
    total_gross_weight_kg: float | None = None
    total_measurement_cbm: float | None = None

    # Freight
    freight_terms: str | None = Field(None, description="Prepaid / Collect")
    freight_amount: float | None = None
    freight_currency: str | None = Field(None, description="ISO 4217")

    # Additional
    number_of_originals: int | None = Field(None, description="Usually 3")
    place_of_issue: str | None = None
    carrier_name: str | None = None

    class ValidationRules:
        rules = [
            RequiredFieldRule("bl_number"),
            RequiredFieldRule("shipper_name"),
            RequiredFieldRule("consignee_name"),
            RequiredFieldRule("port_of_loading"),
            RequiredFieldRule("port_of_discharge"),
            DateBeforeRule("shipped_on_board_date", "issue_date"),
            SumEqualsRule("containers.gross_weight_kg", "total_gross_weight_kg"),
            SumEqualsRule("containers.measurement_cbm", "total_measurement_cbm"),
            SumEqualsRule("containers.packages", "total_packages"),
            RegexRule("hs_code", r"^\d{4,10}(\.\d+)?$", "HS code format"),
            RegexRule("freight_currency", r"^[A-Z]{3}$", "ISO 4217 currency"),
        ]


# Register
schema_registry.register("bill_of_lading", BillOfLadingSchema)
