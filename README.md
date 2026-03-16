# Docpick

> Document in, Structured JSON out. Locally. With your schema.

**docpick** is a lightweight, schema-driven document extraction pipeline that combines local OCR engines with local LLMs to extract structured JSON from any document — invoices, receipts, bills of lading, tax forms, and more.

- **Zero cloud dependency** — runs entirely on your machine (CPU or GPU)
- **Custom schemas** — define your own Pydantic models or use 8 built-in document schemas
- **Validation built-in** — checkdigit verification, cross-field rules, cross-document consistency
- **Apache 2.0** — no GPL/AGPL dependencies

## Install

```bash
pip install docpick            # core (LLM extraction only)
pip install docpick[paddle]    # + PaddleOCR (recommended)
pip install docpick[easyocr]   # + EasyOCR (Korean-optimized)
pip install docpick[got]       # + GOT-OCR2.0 (GPU, vision-language)
pip install docpick[all]       # all OCR backends
```

**Requirements:** Python 3.11+ / LLM endpoint (vLLM, Ollama, or OpenAI-compatible)

## Quick Start

### Python API

```python
from docpick import DocpickPipeline
from docpick.schemas import InvoiceSchema

pipeline = DocpickPipeline()
result = pipeline.extract("invoice.pdf", schema=InvoiceSchema)

print(result.data)           # Structured dict matching schema
print(result.validation)     # Validation errors/warnings
print(result.confidence)     # Per-field confidence scores
```

### CLI

```bash
# Extract structured data
docpick extract invoice.pdf --schema invoice --output result.json

# OCR only (no LLM)
docpick ocr document.png --lang ko,en

# Validate extracted JSON
docpick validate result.json --schema invoice

# Batch process a directory
docpick batch ./documents/ --schema invoice --output ./results/ --concurrency 4

# List available schemas
docpick schemas list

# Show schema details
docpick schemas show invoice
```

## Built-in Schemas

| Schema | Document Type | Key Validations |
|--------|--------------|-----------------|
| `invoice` | Commercial invoices | Line item sums, tax ID checkdigit, date order |
| `receipt` | Retail/restaurant receipts | Total = subtotal + tax + tip |
| `bill_of_lading` | Ocean/air B/L | Container weight sums, ISO 6346, HS code format |
| `purchase_order` | Purchase orders | PO total = line items, delivery date order |
| `kr_tax_invoice` | Korean e-tax invoice (세금계산서) | Business number checkdigit (x2), supply/tax/total sums |
| `bank_statement` | Bank statements | IBAN mod97, period date order |
| `id_document` | Passport/ID (ICAO 9303) | MRZ, ISO 3166 country codes, date ranges |
| `certificate_of_origin` | Certificate of Origin | ISO 3166 alpha-2 country codes |

## Custom Schemas

Define your own schema with Pydantic:

```python
from pydantic import BaseModel
from docpick import DocpickPipeline
from docpick.validation.rules import SumEqualsRule, RequiredFieldRule

class MyDocument(BaseModel):
    """Custom document schema."""
    company_name: str | None = None
    total_amount: float | None = None
    tax_amount: float | None = None
    net_amount: float | None = None
    items: list[dict] | None = None

    class ValidationRules:
        rules = [
            RequiredFieldRule("company_name"),
            SumEqualsRule(["net_amount", "tax_amount"], "total_amount"),
        ]

pipeline = DocpickPipeline()
result = pipeline.extract("my_document.pdf", schema=MyDocument)
```

Or use a JSON Schema file:

```bash
docpick extract document.pdf --schema my_schema.json
```

## Validation

### Check Digit Algorithms

| Algorithm | Use Case |
|-----------|----------|
| `kr_business_number` | Korean business registration number (10 digits) |
| `luhn` | Credit card numbers |
| `iso_6346` | Shipping container numbers |
| `iban_mod97` | International bank account numbers |
| `awb_mod7` | Air waybill numbers |
| `mrz` | Machine Readable Zone (passport/ID) |

### Cross-Field Rules

| Rule | Description |
|------|-------------|
| `SumEqualsRule` | Sum of fields equals target (with tolerance) |
| `DateBeforeRule` | Date A must precede Date B |
| `RequiredFieldRule` | Field must be non-null and non-empty |
| `FieldEqualsRule` | Two fields must be equal |
| `RangeRule` | Numeric field within min/max bounds |
| `RegexRule` | Field matches regex pattern |

### Cross-Document Validation

Validate consistency across related documents (e.g., Invoice + B/L + Packing List):

```python
from docpick.validation.cross_document import create_trade_document_validator

validator = create_trade_document_validator()
result = validator.validate({
    "invoice": invoice_data,
    "bl": bl_data,
    "packing_list": packing_list_data,
    "certificate": certificate_data,
})
print(result.is_valid)
```

## OCR Engines

| Engine | Type | GPU | Languages | Best For |
|--------|------|-----|-----------|----------|
| PaddleOCR | Traditional OCR | Optional | 111 | General documents (default) |
| EasyOCR | Traditional OCR | Optional | 80+ | Korean text |
| GOT-OCR2.0 | Vision-Language | Required | Multi | Complex layouts |
| VLM | Vision-Language | Required | Multi | Direct image → JSON |

### 2-Tier Auto Engine

The default `auto` engine uses confidence-based fallback:

1. **Tier 1 (CPU):** PaddleOCR → EasyOCR
2. **Tier 2 (GPU):** GOT-OCR2.0 → VLM

If Tier 1 average confidence falls below threshold (default 0.7), automatically escalates to Tier 2.

## LLM Providers

| Provider | Endpoint | Default Model |
|----------|----------|---------------|
| vLLM | `http://localhost:8000/v1` | Qwen/Qwen3.5-32B-AWQ |
| Ollama | `http://localhost:11434` | qwen3.5:7b |

Configure via CLI or YAML:

```bash
docpick config set llm.provider ollama
docpick config set llm.base_url http://localhost:11434
docpick config set llm.model qwen3.5:7b
```

## Error Handling

The pipeline is designed to be resilient:

- **OCR failure** → automatic fallback to next available engine
- **LLM JSON parse failure** → automatic retry with correction prompt (up to 1 retry)
- **Partial results** → returns whatever was extracted, with errors logged in `result.errors`
- **Document load failure** → returns empty result with error message

```python
result = pipeline.extract("damaged.pdf", schema=InvoiceSchema)
if result.errors:
    print("Pipeline warnings:", result.errors)
if result.data:
    print("Partial extraction:", result.data)
```

## Batch Processing

Process entire directories with parallel workers:

```python
from docpick.batch import BatchProcessor
from docpick.schemas import InvoiceSchema

processor = BatchProcessor(concurrency=4)
result = processor.process_directory(
    "./invoices/",
    schema=InvoiceSchema,
    recursive=True,
)

print(f"Processed {result.succeeded}/{result.total} files")
for path, extraction in result.results.items():
    print(f"{path}: {extraction.data.get('total_amount')}")
```

## Architecture

```
Document (PDF/Image)
  → DocumentLoader (pypdfium2)
  → Tier 1: OCR (PaddleOCR/EasyOCR, CPU)
    → [confidence < threshold] → Tier 2: VLM (GOT/VLM, GPU)
  → LLM Extractor (vLLM/Ollama, schema prompt)
  → Pydantic Validation (checkdigit, cross-field, cross-document)
  → ExtractionResult (structured JSON + confidence + validation)
```

## License

Apache 2.0 — all dependencies are Apache 2.0 or MIT licensed.
