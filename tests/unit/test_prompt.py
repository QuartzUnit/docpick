"""Tests for prompt generation."""

import json

from pydantic import BaseModel

from docpick.llm.prompt import build_extraction_prompt, build_vlm_extraction_prompt, parse_llm_json


class SimpleSchema(BaseModel):
    name: str | None = None
    amount: float | None = None


def test_build_extraction_prompt():
    messages = build_extraction_prompt("Invoice No: 123\nTotal: $500", SimpleSchema)
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert "JSON Schema" in messages[1]["content"]
    assert "Invoice No: 123" in messages[1]["content"]


def test_build_extraction_prompt_with_context():
    messages = build_extraction_prompt(
        "test text",
        SimpleSchema,
        context={"language": "ko", "tables": ["| A | B |"]},
    )
    content = messages[1]["content"]
    assert "Detected Tables" in content
    assert "Document Language: ko" in content


def test_build_vlm_prompt():
    messages = build_vlm_extraction_prompt(SimpleSchema)
    assert len(messages) == 2
    assert "document image" in messages[1]["content"]


def test_parse_llm_json_clean():
    result = parse_llm_json('{"name": "Test", "amount": 100}')
    assert result["name"] == "Test"
    assert result["amount"] == 100


def test_parse_llm_json_code_block():
    result = parse_llm_json('```json\n{"name": "Test"}\n```')
    assert result["name"] == "Test"


def test_parse_llm_json_with_text():
    result = parse_llm_json('Here is the result:\n{"name": "Test", "amount": 50}\nDone.')
    assert result["name"] == "Test"


def test_parse_llm_json_invalid():
    import pytest
    with pytest.raises(json.JSONDecodeError):
        parse_llm_json("not json at all")
