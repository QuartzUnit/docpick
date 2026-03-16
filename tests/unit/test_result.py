"""Tests for result data structures."""

import json

from docpick.core.result import (
    ExtractionResult,
    OCRResult,
    Table,
    TableCell,
    TextBlock,
    ValidationError,
    ValidationResult,
)


def test_text_block():
    block = TextBlock(text="Hello", bbox=(0.1, 0.2, 0.3, 0.4), confidence=0.95)
    assert block.text == "Hello"
    assert block.confidence == 0.95
    assert block.page == 0
    assert block.block_type == "text"


def test_ocr_result_avg_confidence():
    result = OCRResult(
        text="test",
        blocks=[
            TextBlock(text="A", bbox=(0, 0, 1, 1), confidence=0.9),
            TextBlock(text="B", bbox=(0, 0, 1, 1), confidence=0.8),
        ],
    )
    assert abs(result.avg_confidence - 0.85) < 1e-10


def test_ocr_result_empty():
    result = OCRResult(text="")
    assert result.avg_confidence == 0.0
    assert result.low_confidence_blocks == []


def test_ocr_result_low_confidence():
    result = OCRResult(
        text="test",
        blocks=[
            TextBlock(text="A", bbox=(0, 0, 1, 1), confidence=0.9),
            TextBlock(text="B", bbox=(0, 0, 1, 1), confidence=0.5),
            TextBlock(text="C", bbox=(0, 0, 1, 1), confidence=0.3),
        ],
    )
    low = result.low_confidence_blocks
    assert len(low) == 2
    assert low[0].text == "B"
    assert low[1].text == "C"


def test_table_to_markdown():
    table = Table(
        cells=[
            TableCell(text="Name", row=0, col=0),
            TableCell(text="Amount", row=0, col=1),
            TableCell(text="Apple", row=1, col=0),
            TableCell(text="$5", row=1, col=1),
        ],
        bbox=(0, 0, 1, 1),
        rows=2,
        cols=2,
    )
    md = table.to_markdown()
    assert "| Name | Amount |" in md
    assert "| --- | --- |" in md
    assert "| Apple | $5 |" in md


def test_extraction_result_to_json():
    result = ExtractionResult(
        data={"invoice_number": "INV-001", "total_amount": 100.0},
        confidence={"invoice_number": 0.95, "total_amount": 0.88},
        validation=ValidationResult(is_valid=True),
        schema_name="InvoiceSchema",
        mode="ocr+llm",
        processing_time_ms=1234.5,
    )
    output = json.loads(result.to_json())
    assert output["data"]["invoice_number"] == "INV-001"
    assert output["confidence"]["invoice_number"] == 0.95
    assert output["validation"]["is_valid"] is True
    assert output["metadata"]["schema"] == "InvoiceSchema"


def test_extraction_result_with_errors():
    result = ExtractionResult(
        data={"total": 100},
        validation=ValidationResult(
            is_valid=False,
            errors=[ValidationError(field="total", rule="sum", message="Mismatch")],
        ),
    )
    output = json.loads(result.to_json())
    assert output["validation"]["is_valid"] is False
    assert len(output["validation"]["errors"]) == 1
    assert output["validation"]["errors"][0]["field"] == "total"
