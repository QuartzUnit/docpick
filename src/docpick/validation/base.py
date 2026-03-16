"""Validation rule base classes."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from docpick.core.result import ValidationError, ValidationResult, ValidationWarning


class ValidationRule(ABC):
    """Abstract base class for validation rules."""

    @abstractmethod
    def validate(self, data: dict[str, Any]) -> ValidationError | ValidationWarning | None:
        """Validate extracted data. Returns error/warning or None if valid."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Rule identifier."""
        ...


class Validator:
    """Runs a set of validation rules against extracted data."""

    def __init__(self, rules: list[ValidationRule] | None = None) -> None:
        self.rules = rules or []

    def validate(self, data: dict[str, Any]) -> ValidationResult:
        errors: list[ValidationError] = []
        warnings: list[ValidationWarning] = []
        passed = 0

        for rule in self.rules:
            result = rule.validate(data)
            if result is None:
                passed += 1
            elif isinstance(result, ValidationError):
                errors.append(result)
            elif isinstance(result, ValidationWarning):
                warnings.append(result)
                passed += 1  # Warnings count as passed

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            rules_applied=len(self.rules),
            rules_passed=passed,
        )
