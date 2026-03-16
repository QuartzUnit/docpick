"""Cross-document validation — verify consistency across multiple documents.

Typical trade document flow:
  L/C (Letter of Credit)
    → CI (Commercial Invoice)
    → B/L (Bill of Lading)
    → PL (Packing List)
    → CO (Certificate of Origin)

Cross-validation checks:
  - CI total ≤ L/C amount (UCP 600)
  - B/L goods description matches CI
  - B/L total weight matches PL total weight
  - B/L port of loading matches L/C requirement
  - CO origin country matches CI/B/L
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from docpick.core.result import ValidationError, ValidationWarning


@dataclass
class CrossFieldMapping:
    """Defines a field mapping between two documents for cross-validation."""

    source_doc: str
    source_field: str
    target_doc: str
    target_field: str
    rule: str = "equals"  # equals, less_than_or_equal, contains
    tolerance: float = 0.01  # For numeric comparisons
    description: str = ""


@dataclass
class CrossDocumentResult:
    """Result of cross-document validation."""

    is_valid: bool = True
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[ValidationWarning] = field(default_factory=list)
    checks_applied: int = 0
    checks_passed: int = 0


def _get_nested(data: dict, path: str) -> Any:
    """Get a nested value using dot notation."""
    parts = path.split(".")
    current: Any = data
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
        if current is None:
            return None
    return current


class CrossDocumentValidator:
    """Validates consistency across multiple extracted documents.

    Usage:
        validator = CrossDocumentValidator()
        validator.add_mapping("invoice", "total_amount", "bl", "freight_amount", "less_than_or_equal")
        validator.add_mapping("bl", "total_gross_weight_kg", "packing_list", "total_weight")

        result = validator.validate({
            "invoice": invoice_data,
            "bl": bl_data,
            "packing_list": pl_data,
        })
    """

    def __init__(self) -> None:
        self._mappings: list[CrossFieldMapping] = []

    def add_mapping(
        self,
        source_doc: str,
        source_field: str,
        target_doc: str,
        target_field: str,
        rule: str = "equals",
        tolerance: float = 0.01,
        description: str = "",
    ) -> None:
        """Add a cross-document field mapping."""
        self._mappings.append(CrossFieldMapping(
            source_doc=source_doc,
            source_field=source_field,
            target_doc=target_doc,
            target_field=target_field,
            rule=rule,
            tolerance=tolerance,
            description=description,
        ))

    def validate(self, documents: dict[str, dict[str, Any]]) -> CrossDocumentResult:
        """Validate all mappings against provided document data.

        Args:
            documents: Dict mapping document name to extracted data dict.
                       e.g., {"invoice": {...}, "bl": {...}, "packing_list": {...}}
        """
        errors: list[ValidationError] = []
        warnings: list[ValidationWarning] = []
        passed = 0

        for mapping in self._mappings:
            source_data = documents.get(mapping.source_doc)
            target_data = documents.get(mapping.target_doc)

            if source_data is None or target_data is None:
                # Skip if document not provided
                continue

            source_val = _get_nested(source_data, mapping.source_field)
            target_val = _get_nested(target_data, mapping.target_field)

            if source_val is None or target_val is None:
                # Skip if field not present
                continue

            error = self._check_rule(mapping, source_val, target_val)
            if error is None:
                passed += 1
            else:
                errors.append(error)

        return CrossDocumentResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            checks_applied=len(self._mappings),
            checks_passed=passed,
        )

    def _check_rule(
        self,
        mapping: CrossFieldMapping,
        source_val: Any,
        target_val: Any,
    ) -> ValidationError | None:
        """Check a single cross-document rule."""
        field_desc = f"{mapping.source_doc}.{mapping.source_field} vs {mapping.target_doc}.{mapping.target_field}"

        if mapping.rule == "equals":
            return self._check_equals(mapping, source_val, target_val, field_desc)
        elif mapping.rule == "less_than_or_equal":
            return self._check_lte(mapping, source_val, target_val, field_desc)
        elif mapping.rule == "contains":
            return self._check_contains(mapping, source_val, target_val, field_desc)
        else:
            return ValidationError(
                field=field_desc,
                rule="cross_document",
                message=f"Unknown cross-document rule: {mapping.rule}",
            )

    def _check_equals(
        self, mapping: CrossFieldMapping, source: Any, target: Any, field_desc: str
    ) -> ValidationError | None:
        # Try numeric comparison first
        try:
            s_num = float(source)
            t_num = float(target)
            if abs(s_num - t_num) <= mapping.tolerance:
                return None
            return ValidationError(
                field=field_desc,
                rule="cross_equals",
                message=f"{field_desc}: {source} != {target}" + (f" ({mapping.description})" if mapping.description else ""),
                expected=source,
                actual=target,
            )
        except (ValueError, TypeError):
            pass

        # String comparison
        if str(source).strip().lower() == str(target).strip().lower():
            return None
        return ValidationError(
            field=field_desc,
            rule="cross_equals",
            message=f"{field_desc}: '{source}' != '{target}'" + (f" ({mapping.description})" if mapping.description else ""),
            expected=source,
            actual=target,
        )

    def _check_lte(
        self, mapping: CrossFieldMapping, source: Any, target: Any, field_desc: str
    ) -> ValidationError | None:
        try:
            s_num = float(source)
            t_num = float(target)
            if s_num <= t_num + mapping.tolerance:
                return None
            return ValidationError(
                field=field_desc,
                rule="cross_lte",
                message=f"{field_desc}: {source} > {target}" + (f" ({mapping.description})" if mapping.description else ""),
                expected=f"<= {target}",
                actual=source,
            )
        except (ValueError, TypeError):
            return ValidationError(
                field=field_desc,
                rule="cross_lte",
                message=f"{field_desc}: cannot compare non-numeric values",
            )

    def _check_contains(
        self, mapping: CrossFieldMapping, source: Any, target: Any, field_desc: str
    ) -> ValidationError | None:
        s_str = str(source).strip().lower()
        t_str = str(target).strip().lower()
        if s_str in t_str or t_str in s_str:
            return None
        return ValidationError(
            field=field_desc,
            rule="cross_contains",
            message=f"{field_desc}: '{source}' not found in '{target}'" + (f" ({mapping.description})" if mapping.description else ""),
            expected=source,
            actual=target,
        )


def create_trade_document_validator() -> CrossDocumentValidator:
    """Create a pre-configured validator for standard trade document flow.

    Validates: Invoice ↔ B/L ↔ Packing List ↔ Certificate of Origin
    """
    v = CrossDocumentValidator()

    # Invoice ↔ B/L
    v.add_mapping("invoice", "vendor_name", "bl", "shipper_name", "contains",
                  description="Shipper should match invoice vendor")
    v.add_mapping("invoice", "customer_name", "bl", "consignee_name", "contains",
                  description="Consignee should match invoice buyer")

    # B/L ↔ Packing List (weights and packages)
    v.add_mapping("bl", "total_gross_weight_kg", "packing_list", "total_gross_weight_kg", "equals",
                  tolerance=0.5, description="B/L and PL gross weight must match")
    v.add_mapping("bl", "total_packages", "packing_list", "total_packages", "equals",
                  description="B/L and PL total packages must match")

    # Invoice ↔ Certificate of Origin
    v.add_mapping("invoice", "country_of_origin", "certificate", "country_of_origin", "equals",
                  description="Origin country must match across documents")

    return v
