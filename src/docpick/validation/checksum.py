"""Checkdigit validation algorithms."""

from __future__ import annotations

from typing import Any

from docpick.core.result import ValidationError
from docpick.validation.base import ValidationRule


def _get_nested(data: dict, path: str) -> Any:
    """Get a nested value from dict using dot notation."""
    parts = path.split(".")
    current = data
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
        if current is None:
            return None
    return current


def verify_kr_business_number(value: str) -> bool:
    """Verify Korean business registration number (사업자등록번호).

    Format: 10 digits (XXX-XX-XXXXX). Check digit is the last digit.
    """
    digits = value.replace("-", "").replace(" ", "")
    if len(digits) != 10 or not digits.isdigit():
        return False

    weights = [1, 3, 7, 1, 3, 7, 1, 3, 5]
    total = sum(int(d) * w for d, w in zip(digits[:9], weights))
    total += (int(digits[8]) * 5) // 10
    check = (10 - (total % 10)) % 10
    return check == int(digits[9])


def verify_luhn(value: str) -> bool:
    """Verify Luhn checksum (credit card numbers, etc.)."""
    digits = value.replace("-", "").replace(" ", "")
    if not digits.isdigit():
        return False

    total = 0
    for i, d in enumerate(reversed(digits)):
        n = int(d)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def verify_mrz_check(value: str, check_digit: str) -> bool:
    """Verify MRZ check digit (ICAO Doc 9303).

    Characters: 0-9 (values 0-9), A-Z (values 10-35), < (value 0).
    """
    weights = [7, 3, 1]
    char_values = {}
    for i in range(10):
        char_values[str(i)] = i
    for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
        char_values[c] = i + 10
    char_values["<"] = 0

    total = 0
    for i, c in enumerate(value.upper()):
        v = char_values.get(c, 0)
        total += v * weights[i % 3]

    return (total % 10) == int(check_digit)


def verify_iso_6346(value: str) -> bool:
    """Verify ISO 6346 container number (4 letters + 7 digits, last is check)."""
    cleaned = value.replace("-", "").replace(" ", "").upper()
    if len(cleaned) != 11:
        return False
    if not cleaned[:4].isalpha() or not cleaned[4:].isdigit():
        return False

    # ISO 6346 algorithm
    char_values = {}
    for i in range(10):
        char_values[str(i)] = i
    val = 10
    for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        char_values[c] = val
        val += 1
        if val % 11 == 0:
            val += 1

    total = sum(char_values.get(c, 0) * (2 ** i) for i, c in enumerate(cleaned[:10]))
    check = total % 11 % 10
    return check == int(cleaned[10])


def verify_awb_mod7(value: str) -> bool:
    """Verify Air Waybill number (11 digits, Modulus 7).

    Format: PPP-NNNNNNNN where PPP is airline prefix (3 digits),
    NNNNNNNN is serial (7 digits) + check digit (1 digit).
    Check: first 7 serial digits mod 7 == last digit.
    """
    digits = value.replace("-", "").replace(" ", "")
    if len(digits) != 11 or not digits.isdigit():
        return False

    # Last digit is check digit, check against serial portion (digits 3-9)
    serial = int(digits[3:10])
    check = int(digits[10])
    return serial % 7 == check


def verify_iban_mod97(value: str) -> bool:
    """Verify IBAN using Modulus 97 (ISO 13616).

    Move first 4 chars to end, convert letters to numbers (A=10..Z=35),
    result mod 97 must equal 1.
    """
    cleaned = value.replace(" ", "").replace("-", "").upper()
    if len(cleaned) < 5 or not cleaned[:2].isalpha() or not cleaned[2:4].isdigit():
        return False

    # Rearrange: move first 4 chars to end
    rearranged = cleaned[4:] + cleaned[:4]

    # Convert letters to numbers
    numeric = ""
    for c in rearranged:
        if c.isdigit():
            numeric += c
        elif c.isalpha():
            numeric += str(ord(c) - ord("A") + 10)
        else:
            return False

    return int(numeric) % 97 == 1


_ALGORITHMS = {
    "kr_business_number": verify_kr_business_number,
    "luhn": verify_luhn,
    "iso_6346": verify_iso_6346,
    "awb_mod7": verify_awb_mod7,
    "iban_mod97": verify_iban_mod97,
}


class CheckDigitRule(ValidationRule):
    """Validate a field using a check digit algorithm."""

    def __init__(self, field: str, algorithm: str) -> None:
        self.field = field
        self.algorithm = algorithm
        if algorithm not in _ALGORITHMS:
            raise ValueError(f"Unknown algorithm: {algorithm}. Available: {list(_ALGORITHMS)}")

    def validate(self, data: dict[str, Any]) -> ValidationError | None:
        value = _get_nested(data, self.field)
        if value is None:
            return None  # Skip if field not present

        value_str = str(value)
        verify_fn = _ALGORITHMS[self.algorithm]

        if not verify_fn(value_str):
            return ValidationError(
                field=self.field,
                rule=f"checkdigit:{self.algorithm}",
                message=f"Check digit validation failed for {self.field}: '{value_str}'",
                actual=value_str,
            )
        return None

    @property
    def name(self) -> str:
        return f"checkdigit:{self.algorithm}:{self.field}"
