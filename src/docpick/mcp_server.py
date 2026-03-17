"""Docpick MCP server — expose document extraction as MCP tools for Claude Code."""

import json

from fastmcp import FastMCP

mcp = FastMCP(
    "docpick",
    instructions="Schema-driven document extraction with local OCR + LLM. Document in, Structured JSON out.",
)


@mcp.tool()
def extract_document(
    file_path: str,
    schema: str = "invoice",
    ocr_engine: str = "auto",
    output_format: str = "json",
) -> str:
    """Extract structured data from a document using OCR + LLM.

    Supports PDF and image files (PNG, JPG, TIFF).
    Returns structured JSON matching the specified schema.

    Args:
        file_path: Path to the document file (PDF, PNG, JPG, TIFF).
        schema: Schema to use for extraction. Built-in: invoice, receipt,
                bill_of_lading, purchase_order, kr_tax_invoice,
                bank_statement, id_document, certificate_of_origin.
        ocr_engine: OCR engine to use: "auto" (default), "paddle", "easyocr", "got", "vlm".
        output_format: "json" (default) or "text" (OCR text only).
    """
    from docpick import DocpickPipeline, DocpickConfig
    from docpick.schemas import get_schema

    config = DocpickConfig.load()
    if ocr_engine != "auto":
        config.ocr.engine = ocr_engine

    pipeline = DocpickPipeline(config=config)
    schema_model = get_schema(schema)
    result = pipeline.extract(file_path, schema=schema_model)

    if output_format == "text":
        return result.text or (result.ocr_result.text if result.ocr_result else "")

    return result.to_json()


@mcp.tool()
def ocr_document(
    file_path: str,
    engine: str = "auto",
) -> str:
    """Run OCR on a document without LLM extraction.

    Returns recognized text as markdown with structure preserved.

    Args:
        file_path: Path to the document file (PDF, PNG, JPG, TIFF).
        engine: OCR engine: "auto" (default), "paddle", "easyocr", "got".
    """
    from docpick import DocpickPipeline, DocpickConfig

    config = DocpickConfig.load()
    config.ocr.engine = engine

    pipeline = DocpickPipeline(config=config)
    ocr_result = pipeline.ocr(file_path)

    return json.dumps({
        "text": ocr_result.text,
        "markdown": ocr_result.to_markdown(),
        "engine": ocr_result.engine,
        "avg_confidence": round(ocr_result.avg_confidence, 3),
        "block_count": len(ocr_result.blocks),
        "table_count": len(ocr_result.tables),
        "processing_time_ms": round(ocr_result.processing_time_ms, 1),
    }, ensure_ascii=False)


@mcp.tool()
def list_schemas() -> str:
    """List all available built-in document schemas with their fields."""
    from docpick.schemas import SCHEMA_REGISTRY

    schemas = []
    for name, schema_cls in SCHEMA_REGISTRY.items():
        fields = list(schema_cls.model_fields.keys())
        schemas.append({"name": name, "fields": fields})

    return json.dumps(schemas, ensure_ascii=False)


def main():
    """Run the MCP server (stdio transport)."""
    mcp.run()


if __name__ == "__main__":
    main()
