"""Tests for error handling improvements."""

import json
from unittest.mock import MagicMock, patch

from PIL import Image

from docpick.core.pipeline import DocpickPipeline
from docpick.core.config import DocpickConfig
from docpick.core.result import ExtractionResult, OCRResult, TextBlock
from docpick.llm.prompt import parse_llm_json, build_retry_messages


# === parse_llm_json improvements ===

def test_parse_json_direct():
    result = parse_llm_json('{"name": "test", "value": 42}')
    assert result == {"name": "test", "value": 42}


def test_parse_json_markdown_block():
    text = '```json\n{"name": "test"}\n```'
    result = parse_llm_json(text)
    assert result == {"name": "test"}


def test_parse_json_with_surrounding_text():
    text = 'Here is the result:\n{"name": "test"}\nDone.'
    result = parse_llm_json(text)
    assert result == {"name": "test"}


def test_parse_json_trailing_comma():
    text = '{"name": "test", "value": 42,}'
    result = parse_llm_json(text)
    assert result == {"name": "test", "value": 42}


def test_parse_json_trailing_comma_in_array():
    text = '{"items": [1, 2, 3,]}'
    result = parse_llm_json(text)
    assert result == {"items": [1, 2, 3]}


def test_parse_json_trailing_comma_nested():
    text = '{"a": {"b": 1,}, "c": [1, 2,],}'
    result = parse_llm_json(text)
    assert result == {"a": {"b": 1}, "c": [1, 2]}


def test_parse_json_surrounded_and_trailing_comma():
    text = 'The extracted data:\n{"name": "test", "value": 42,}\nEnd of extraction.'
    result = parse_llm_json(text)
    assert result == {"name": "test", "value": 42}


def test_parse_json_failure():
    import pytest
    with pytest.raises(json.JSONDecodeError):
        parse_llm_json("this is not json at all")


# === build_retry_messages ===

def test_build_retry_messages():
    msgs = build_retry_messages("bad output")
    assert len(msgs) == 2
    assert msgs[0]["role"] == "assistant"
    assert msgs[0]["content"] == "bad output"
    assert msgs[1]["role"] == "user"
    assert "valid JSON" in msgs[1]["content"]


# === ExtractionResult errors field ===

def test_extraction_result_errors_field():
    result = ExtractionResult(errors=["OCR failed", "Fell back to easyocr"])
    assert len(result.errors) == 2


def test_extraction_result_errors_in_json():
    result = ExtractionResult(errors=["test error"])
    output = json.loads(result.to_json())
    assert "errors" in output
    assert output["errors"] == ["test error"]


def test_extraction_result_no_errors_not_in_json():
    result = ExtractionResult()
    output = json.loads(result.to_json())
    assert "errors" not in output


# === Pipeline OCR fallback ===

def test_pipeline_ocr_fallback_on_failure():
    """When primary OCR fails, pipeline should try fallback engines."""
    config = DocpickConfig.load()
    pipeline = DocpickPipeline(config)

    # Mock primary engine that fails
    mock_engine = MagicMock()
    mock_engine.name = "paddle"
    mock_engine.recognize.side_effect = RuntimeError("PaddleOCR crash")
    pipeline._ocr_engine = mock_engine

    errors: list[str] = []
    img = Image.new("RGB", (100, 100), "white")

    # Mock get_engine to return a working fallback
    fallback_result = OCRResult(text="fallback text", engine="easyocr")
    mock_fallback = MagicMock()
    mock_fallback.recognize.return_value = fallback_result

    with patch("docpick.ocr.auto.get_engine", return_value=mock_fallback):
        result = pipeline._recognize_with_fallback(img, ["en"], errors)

    assert result.text == "fallback text"
    assert any("failed" in e for e in errors)
    assert any("Fell back" in e for e in errors)


def test_pipeline_ocr_all_engines_fail():
    """When all OCR engines fail, return empty result."""
    config = DocpickConfig.load()
    pipeline = DocpickPipeline(config)

    mock_engine = MagicMock()
    mock_engine.name = "paddle"
    mock_engine.recognize.side_effect = RuntimeError("crash")
    pipeline._ocr_engine = mock_engine

    errors: list[str] = []
    img = Image.new("RGB", (100, 100), "white")

    # All fallbacks fail too
    with patch("docpick.ocr.auto.get_engine", side_effect=RuntimeError("no engine")):
        result = pipeline._recognize_with_fallback(img, ["en"], errors)

    assert result.text == ""
    assert result.engine == "none"
    assert any("All OCR engines failed" in e for e in errors)


def test_pipeline_document_load_failure():
    """Pipeline returns error result when document can't be loaded."""
    pipeline = DocpickPipeline()
    result = pipeline.extract("/nonexistent/path/document.pdf")

    assert result.errors
    assert any("Document load failed" in e for e in result.errors)
    assert result.data == {}


def test_pipeline_llm_failure_returns_partial():
    """When LLM fails, pipeline still returns OCR text."""
    config = DocpickConfig.load()
    pipeline = DocpickPipeline(config)

    # Mock OCR
    mock_engine = MagicMock()
    mock_engine.recognize.return_value = OCRResult(
        text="Invoice #123\nTotal: $500",
        blocks=[TextBlock("Invoice #123", (0, 0, 1, 0.5), 0.95)],
        engine="paddle",
    )
    pipeline._ocr_engine = mock_engine

    # Mock LLM that fails
    mock_llm = MagicMock()
    mock_llm.extract_fields.side_effect = RuntimeError("LLM timeout")
    pipeline._llm_provider = mock_llm

    from docpick.schemas.invoice import InvoiceSchema
    img = Image.new("RGB", (100, 100), "white")
    result = pipeline.extract(img, schema=InvoiceSchema, mode="ocr+llm")

    assert result.text == "Invoice #123\nTotal: $500"
    assert result.data == {}
    assert any("LLM extraction failed" in e for e in result.errors)


# === LLM retry ===

def test_vllm_provider_retry_on_json_error():
    """VLLMProvider retries with correction prompt on JSON parse failure."""
    from docpick.llm.vllm_provider import VLLMProvider
    from docpick.schemas.invoice import InvoiceSchema

    provider = VLLMProvider()

    call_count = 0

    def mock_call_chat(messages):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return "Here is the data: {invalid json"
        return '{"invoice_number": "INV-001"}'

    provider._call_chat = mock_call_chat
    result = provider.extract_fields("Invoice #001", InvoiceSchema)

    assert call_count == 2
    assert result == {"invoice_number": "INV-001"}


def test_vllm_provider_retry_exhausted():
    """VLLMProvider raises after exhausting retries."""
    import pytest
    from docpick.llm.vllm_provider import VLLMProvider
    from docpick.schemas.invoice import InvoiceSchema

    provider = VLLMProvider()
    provider._call_chat = lambda msgs: "not json at all"

    with pytest.raises(json.JSONDecodeError):
        provider.extract_fields("test", InvoiceSchema, max_retries=1)


def test_ollama_provider_retry_on_json_error():
    """OllamaProvider retries with correction prompt on JSON parse failure."""
    from docpick.llm.vllm_provider import OllamaProvider
    from docpick.schemas.receipt import ReceiptSchema

    provider = OllamaProvider()

    call_count = 0

    def mock_call_chat(messages):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return "```json\n{bad json,}\n```"
        return '{"merchant_name": "Store A"}'

    provider._call_chat = mock_call_chat
    result = provider.extract_fields("Receipt from Store A", ReceiptSchema)

    assert call_count == 2
    assert result == {"merchant_name": "Store A"}
