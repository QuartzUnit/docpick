"""Cross-field validation rules."""

from __future__ import annotations

import re
from typing import Any

from docpick.core.result import ValidationError, ValidationWarning
from docpick.validation.base import ValidationRule


def _get_nested(data: dict, path: str) -> Any:
    """Get a nested value using dot notation. Supports array aggregation."""
    parts = path.split(".")
    current: Any = data
    for part in parts:
        if isinstance(current, list):
            # Aggregate: collect field from all items
            return [item.get(part) if isinstance(item, dict) else None for item in current]
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
        if current is None:
            return None
    return current


class SumEqualsRule(ValidationRule):
    """Validate that sum of source fields equals target field."""

    def __init__(self, sources: str | list[str], target: str, tolerance: float = 0.01) -> None:
        self.sources = [sources] if isinstance(sources, str) else sources
        self.target = target
        self.tolerance = tolerance

    def validate(self, data: dict[str, Any]) -> ValidationError | None:
        target_val = _get_nested(data, self.target)
        if target_val is None:
            return None

        total = 0.0
        for source in self.sources:
            val = _get_nested(data, source)
            if val is None:
                return None  # Can't validate if source missing
            if isinstance(val, list):
                # Sum array values
                vals = [v for v in val if v is not None]
                if not vals:
                    return None
                total += sum(float(v) for v in vals)
            else:
                total += float(val)

        if abs(total - float(target_val)) > self.tolerance:
            return ValidationError(
                field=self.target,
                rule="sum_equals",
                message=f"Sum of {self.sources} ({total:.2f}) != {self.target} ({target_val})",
                expected=total,
                actual=target_val,
            )
        return None

    @property
    def name(self) -> str:
        return f"sum_equals:{'+'.join(self.sources)}={self.target}"


class DateBeforeRule(ValidationRule):
    """Validate that date A is before date B."""

    def __init__(self, before_field: str, after_field: str) -> None:
        self.before_field = before_field
        self.after_field = after_field

    def validate(self, data: dict[str, Any]) -> ValidationError | None:
        before = _get_nested(data, self.before_field)
        after = _get_nested(data, self.after_field)
        if before is None or after is None:
            return None

        if str(before) > str(after):
            return ValidationError(
                field=self.after_field,
                rule="date_before",
                message=f"{self.before_field} ({before}) should be before {self.after_field} ({after})",
                expected=f"{before} <= {after}",
                actual=f"{before} > {after}",
            )
        return None

    @property
    def name(self) -> str:
        return f"date_before:{self.before_field}<{self.after_field}"


class RequiredFieldRule(ValidationRule):
    """Validate that a field is present and non-null."""

    def __init__(self, field: str) -> None:
        self.field = field

    def validate(self, data: dict[str, Any]) -> ValidationWarning | None:
        val = _get_nested(data, self.field)
        if val is None or (isinstance(val, str) and not val.strip()):
            return ValidationWarning(
                field=self.field,
                rule="required",
                message=f"Required field '{self.field}' is missing or empty",
            )
        return None

    @property
    def name(self) -> str:
        return f"required:{self.field}"


class FieldEqualsRule(ValidationRule):
    """Validate that two fields have the same value."""

    def __init__(self, field_a: str, field_b: str) -> None:
        self.field_a = field_a
        self.field_b = field_b

    def validate(self, data: dict[str, Any]) -> ValidationError | None:
        val_a = _get_nested(data, self.field_a)
        val_b = _get_nested(data, self.field_b)
        if val_a is None or val_b is None:
            return None

        if str(val_a) != str(val_b):
            return ValidationError(
                field=self.field_b,
                rule="field_equals",
                message=f"{self.field_a} ({val_a}) != {self.field_b} ({val_b})",
                expected=val_a,
                actual=val_b,
            )
        return None

    @property
    def name(self) -> str:
        return f"field_equals:{self.field_a}=={self.field_b}"


class RangeRule(ValidationRule):
    """Validate that a numeric field is within a range."""

    def __init__(self, field: str, min_val: float | None = None, max_val: float | None = None) -> None:
        self.field = field
        self.min_val = min_val
        self.max_val = max_val

    def validate(self, data: dict[str, Any]) -> ValidationError | None:
        val = _get_nested(data, self.field)
        if val is None:
            return None

        try:
            num = float(val)
        except (ValueError, TypeError):
            return ValidationError(
                field=self.field,
                rule="range",
                message=f"Field '{self.field}' is not numeric: {val}",
                actual=val,
            )

        if self.min_val is not None and num < self.min_val:
            return ValidationError(
                field=self.field,
                rule="range",
                message=f"{self.field} ({num}) < min ({self.min_val})",
                expected=f">= {self.min_val}",
                actual=num,
            )
        if self.max_val is not None and num > self.max_val:
            return ValidationError(
                field=self.field,
                rule="range",
                message=f"{self.field} ({num}) > max ({self.max_val})",
                expected=f"<= {self.max_val}",
                actual=num,
            )
        return None

    @property
    def name(self) -> str:
        parts = []
        if self.min_val is not None:
            parts.append(f"{self.min_val}<=")
        parts.append(self.field)
        if self.max_val is not None:
            parts.append(f"<={self.max_val}")
        return f"range:{''.join(parts)}"


class RegexRule(ValidationRule):
    """Validate that a field matches a regex pattern."""

    def __init__(self, field: str, pattern: str, description: str = "") -> None:
        self.field = field
        self.pattern = pattern
        self.description = description
        self._compiled = re.compile(pattern)

    def validate(self, data: dict[str, Any]) -> ValidationError | None:
        val = _get_nested(data, self.field)
        if val is None:
            return None

        val_str = str(val)
        if not self._compiled.search(val_str):
            desc = self.description or f"pattern '{self.pattern}'"
            return ValidationError(
                field=self.field,
                rule="regex",
                message=f"{self.field} ('{val_str}') does not match {desc}",
                expected=self.pattern,
                actual=val_str,
            )
        return None

    @property
    def name(self) -> str:
        return f"regex:{self.field}~{self.pattern}"
