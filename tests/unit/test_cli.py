"""Tests for CLI commands."""

import json
import tempfile
from pathlib import Path

from click.testing import CliRunner

from docpick.cli import main


runner = CliRunner()


# === schemas list ===

def test_cli_schemas_list():
    result = runner.invoke(main, ["schemas", "list"])
    assert result.exit_code == 0
    assert "invoice" in result.output
    assert "receipt" in result.output


# === schemas show ===

def test_cli_schemas_show_invoice():
    result = runner.invoke(main, ["schemas", "show", "invoice"])
    assert result.exit_code == 0
    assert "invoice_number" in result.output
    assert "vendor_name" in result.output


def test_cli_schemas_show_receipt():
    result = runner.invoke(main, ["schemas", "show", "receipt"])
    assert result.exit_code == 0
    assert "merchant_name" in result.output


def test_cli_schemas_show_unknown():
    result = runner.invoke(main, ["schemas", "show", "nonexistent"])
    assert result.exit_code != 0


# === config show ===

def test_cli_config_show():
    result = runner.invoke(main, ["config", "show"])
    assert result.exit_code == 0
    assert "ocr" in result.output
    assert "llm" in result.output


# === validate ===

def test_cli_validate_valid():
    data = {
        "invoice_number": "INV-001",
        "vendor_name": "Acme Corp",
        "total_amount": 110.0,
        "subtotal": 100.0,
        "tax_amount": 10.0,
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        f.flush()
        result = runner.invoke(main, ["validate", f.name, "--schema", "invoice"])
    assert result.exit_code == 0
    assert "Valid" in result.output or "is_valid" in result.output


def test_cli_validate_invalid():
    data = {
        "total_amount": 200.0,
        "subtotal": 100.0,
        "tax_amount": 10.0,
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        f.flush()
        result = runner.invoke(main, ["validate", f.name, "--schema", "invoice"])
    assert result.exit_code == 0
    assert "Invalid" in result.output or "errors" in result.output


def test_cli_validate_extraction_result_format():
    """Test that validate accepts ExtractionResult JSON format (nested data key)."""
    extraction_result = {
        "data": {
            "invoice_number": "INV-001",
            "vendor_name": "Acme Corp",
            "total_amount": 110.0,
            "subtotal": 100.0,
            "tax_amount": 10.0,
        },
        "metadata": {"schema": "InvoiceSchema"},
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(extraction_result, f)
        f.flush()
        result = runner.invoke(main, ["validate", f.name, "--schema", "invoice"])
    assert result.exit_code == 0
    assert "Valid" in result.output or "is_valid" in result.output


def test_cli_validate_output_file():
    data = {"invoice_number": "INV-001", "vendor_name": "X", "total_amount": 100.0}
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        f.flush()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as out:
            result = runner.invoke(main, ["validate", f.name, "--schema", "invoice", "--output", out.name])
            assert result.exit_code == 0
            output_data = json.loads(Path(out.name).read_text())
            assert "is_valid" in output_data


# === JSON Schema file loading ===

def test_cli_resolve_json_schema_file():
    schema = {
        "title": "TestDoc",
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "amount": {"type": "number"},
        },
        "required": ["title"],
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(schema, f)
        f.flush()
        # Use schemas show with file path — this should resolve dynamically
        from docpick.cli import _resolve_schema
        cls = _resolve_schema(f.name)
        assert cls is not None
        assert "title" in cls.model_fields
        assert "amount" in cls.model_fields


# === version ===

def test_cli_version():
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output
