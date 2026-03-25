# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.2] - 2026-03-17

### Added
- MCP server module with registry metadata
- Schema validation improvements

### Fixed
- Version mismatch between `__init__.py` and tests

## [0.1.1] - 2026-03-16

### Fixed
- PaddleOCR v3.4 API compatibility

## [0.1.0] - 2026-03-16

### Added
- Initial release
- Schema-driven document extraction pipeline (OCR + local LLM)
- 8 built-in document schemas: invoice, receipt, bill of lading, purchase order, Korean e-tax invoice, bank statement, ID document, certificate of origin
- 3 OCR engine backends: PaddleOCR, EasyOCR, GOT-OCR2.0
- LLM providers: vLLM, Ollama, OpenAI-compatible endpoints
- Validation: checkdigit verification, cross-field rules, cross-document consistency
- Batch processor and CLI
- 217 tests
- Zero cloud dependency — runs entirely on local hardware
- Apache 2.0 license (no GPL/AGPL dependencies)
