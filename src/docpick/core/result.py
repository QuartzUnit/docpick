"""Extraction result data structures."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TextBlock:
    """A block of recognized text with position and confidence."""

    text: str
    bbox: tuple[float, float, float, float]  # x1, y1, x2, y2 (normalized 0~1)
    confidence: float  # 0.0~1.0
    page: int = 0
    block_type: str = "text"  # text, title, table, figure, header, footer


@dataclass
class TableCell:
    """A single cell in a detected table."""

    text: str
    row: int
    col: int
    row_span: int = 1
    col_span: int = 1


@dataclass
class Table:
    """A detected table with cells."""

    cells: list[TableCell]
    bbox: tuple[float, float, float, float]
    page: int = 0
    rows: int = 0
    cols: int = 0

    def to_markdown(self) -> str:
        """Convert table to markdown format."""
        if not self.cells:
            return ""
        grid: dict[tuple[int, int], str] = {}
        max_row = max(c.row for c in self.cells)
        max_col = max(c.col for c in self.cells)
        for cell in self.cells:
            grid[(cell.row, cell.col)] = cell.text

        lines = []
        for r in range(max_row + 1):
            row_cells = [grid.get((r, c), "") for c in range(max_col + 1)]
            lines.append("| " + " | ".join(row_cells) + " |")
            if r == 0:
                lines.append("| " + " | ".join(["---"] * (max_col + 1)) + " |")
        return "\n".join(lines)


@dataclass
class LayoutInfo:
    """Document layout information."""

    page_count: int = 1
    is_scanned: bool = False
    has_tables: bool = False
    has_figures: bool = False
    detected_languages: list[str] = field(default_factory=list)
    orientation: int = 0  # degrees


@dataclass
class OCRResult:
    """Result from OCR engine."""

    text: str
    blocks: list[TextBlock] = field(default_factory=list)
    tables: list[Table] = field(default_factory=list)
    layout: LayoutInfo | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    engine: str = ""
    processing_time_ms: float = 0.0

    @property
    def avg_confidence(self) -> float:
        if not self.blocks:
            return 0.0
        return sum(b.confidence for b in self.blocks) / len(self.blocks)

    @property
    def low_confidence_blocks(self) -> list[TextBlock]:
        return [b for b in self.blocks if b.confidence < 0.7]

    def to_markdown(self) -> str:
        """Convert OCR result to structured markdown."""
        parts = []
        for block in sorted(self.blocks, key=lambda b: (b.page, b.bbox[1], b.bbox[0])):
            if block.block_type == "title":
                parts.append(f"## {block.text}")
            else:
                parts.append(block.text)
        for table in self.tables:
            parts.append(table.to_markdown())
        return "\n\n".join(parts)


@dataclass
class ValidationError:
    """A validation error for a specific field."""

    field: str
    rule: str
    message: str
    expected: Any = None
    actual: Any = None


@dataclass
class ValidationWarning:
    """A validation warning (non-critical)."""

    field: str
    rule: str
    message: str


@dataclass
class ValidationResult:
    """Result of schema validation."""

    is_valid: bool = True
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[ValidationWarning] = field(default_factory=list)
    rules_applied: int = 0
    rules_passed: int = 0


@dataclass
class ExtractionResult:
    """Final extraction result combining OCR, LLM extraction, and validation."""

    data: dict[str, Any] = field(default_factory=dict)
    confidence: dict[str, float] = field(default_factory=dict)
    validation: ValidationResult = field(default_factory=ValidationResult)
    ocr_result: OCRResult | None = None
    text: str = ""
    markdown: str = ""
    schema_name: str = ""
    mode: str = "ocr+llm"  # ocr+llm, vlm, ocr_only
    processing_time_ms: float = 0.0
    errors: list[str] = field(default_factory=list)

    def to_json(self, pretty: bool = True) -> str:
        import json

        output = {
            "data": self.data,
            "confidence": self.confidence,
            "validation": {
                "is_valid": self.validation.is_valid,
                "errors": [
                    {"field": e.field, "rule": e.rule, "message": e.message}
                    for e in self.validation.errors
                ],
                "warnings": [
                    {"field": w.field, "rule": w.rule, "message": w.message}
                    for w in self.validation.warnings
                ],
            },
            "metadata": {
                "schema": self.schema_name,
                "mode": self.mode,
                "processing_time_ms": self.processing_time_ms,
            },
        }
        if self.errors:
            output["errors"] = self.errors
        return json.dumps(output, indent=2 if pretty else None, ensure_ascii=False)
