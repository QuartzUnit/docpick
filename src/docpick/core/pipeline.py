"""Main pipeline orchestrator."""

from __future__ import annotations

import base64
import io
import logging
import time
from pathlib import Path
from typing import Any

from PIL import Image
from pydantic import BaseModel

from docpick.core.config import DocpickConfig
from docpick.core.document import DocumentLoader
from docpick.core.result import ExtractionResult, OCRResult, ValidationResult

logger = logging.getLogger(__name__)


class DocpickPipeline:
    """Main pipeline: Document → OCR → LLM → Structured JSON.

    Usage:
        pipeline = DocpickPipeline()
        result = pipeline.extract("invoice.pdf", schema=InvoiceSchema)
        print(result.data)
    """

    def __init__(self, config: DocpickConfig | None = None) -> None:
        self.config = config or DocpickConfig.load()
        self._loader = DocumentLoader()
        self._ocr_engine = None
        self._llm_provider = None

    @property
    def ocr_engine(self):
        if self._ocr_engine is None:
            from docpick.ocr.auto import get_engine
            kwargs = {}
            if self.config.ocr.engine == "auto":
                kwargs["confidence_threshold"] = self.config.ocr.confidence_threshold
            self._ocr_engine = get_engine(self.config.ocr.engine, **kwargs)
        return self._ocr_engine

    @property
    def llm_provider(self):
        if self._llm_provider is None:
            from docpick.llm.vllm_provider import get_provider
            self._llm_provider = get_provider(
                self.config.llm.provider,
                base_url=self.config.llm.base_url,
                model=self.config.llm.model,
                temperature=self.config.llm.temperature,
                max_tokens=self.config.llm.max_tokens,
                timeout=self.config.llm.timeout,
            )
        return self._llm_provider

    def extract(
        self,
        source: str | Path | Image.Image,
        schema: type[BaseModel] | None = None,
        mode: str = "auto",
        languages: list[str] | None = None,
    ) -> ExtractionResult:
        """Extract structured data from a document.

        Args:
            source: File path (PDF/image) or PIL Image.
            schema: Pydantic model defining expected fields. None = OCR only.
            mode: Extraction mode ('auto', 'ocr+llm', 'vlm', 'ocr_only').
            languages: OCR languages. None = use config default.

        Returns:
            ExtractionResult with structured data, confidence, and validation.
        """
        start = time.monotonic()
        langs = languages or self.config.ocr.languages
        errors: list[str] = []

        # Resolve mode
        if mode == "auto":
            mode = "vlm" if (self.config.vlm.enabled and schema) else "ocr+llm" if schema else "ocr_only"

        # Load document
        try:
            images = self._load_images(source)
        except Exception as e:
            logger.error("Failed to load document: %s", e)
            elapsed = (time.monotonic() - start) * 1000
            return ExtractionResult(
                mode=mode,
                processing_time_ms=elapsed,
                errors=[f"Document load failed: {e}"],
            )

        if mode == "vlm":
            return self._extract_vlm(images, schema, start, errors)
        elif mode == "ocr_only":
            return self._extract_ocr_only(images, langs, start, errors)
        else:  # ocr+llm
            return self._extract_ocr_llm(images, schema, langs, start, errors)

    def _load_images(self, source: str | Path | Image.Image) -> list[Image.Image]:
        """Load source into list of PIL Images."""
        if isinstance(source, Image.Image):
            return [source]
        return self._loader.load(source)

    def _recognize_with_fallback(
        self, image: Image.Image, languages: list[str], errors: list[str]
    ) -> OCRResult:
        """Run OCR with fallback to other engines on failure."""
        try:
            return self.ocr_engine.recognize(image, languages)
        except Exception as e:
            engine_name = getattr(self.ocr_engine, "name", "unknown")
            errors.append(f"OCR engine '{engine_name}' failed: {e}")
            logger.warning("OCR failed with %s: %s. Trying fallback engines...", engine_name, e)

        # Try fallback engines
        from docpick.ocr.auto import get_engine
        fallback_order = ["paddle", "easyocr"]
        current_engine = self.config.ocr.engine

        for fallback_name in fallback_order:
            if fallback_name == current_engine:
                continue
            try:
                fallback = get_engine(fallback_name)
                result = fallback.recognize(image, languages)
                errors.append(f"Fell back to '{fallback_name}' engine")
                logger.info("Fallback to %s succeeded", fallback_name)
                return result
            except Exception:
                continue

        # All engines failed — return empty result
        errors.append("All OCR engines failed")
        logger.error("All OCR engines failed for this image")
        return OCRResult(text="", engine="none")

    def _extract_ocr_only(
        self, images: list[Image.Image], languages: list[str], start: float, errors: list[str]
    ) -> ExtractionResult:
        """OCR only — no LLM extraction."""
        ocr_results = [self._recognize_with_fallback(img, languages, errors) for img in images]
        merged = self._merge_ocr_results(ocr_results)
        elapsed = (time.monotonic() - start) * 1000

        return ExtractionResult(
            text=merged.text,
            markdown=merged.to_markdown(),
            ocr_result=merged,
            mode="ocr_only",
            processing_time_ms=elapsed,
            errors=errors,
        )

    def _extract_ocr_llm(
        self,
        images: list[Image.Image],
        schema: type[BaseModel] | None,
        languages: list[str],
        start: float,
        errors: list[str],
    ) -> ExtractionResult:
        """OCR + LLM structured extraction."""
        # Step 1: OCR (with fallback)
        ocr_results = [self._recognize_with_fallback(img, languages, errors) for img in images]
        merged = self._merge_ocr_results(ocr_results)

        if schema is None:
            elapsed = (time.monotonic() - start) * 1000
            return ExtractionResult(
                text=merged.text,
                markdown=merged.to_markdown(),
                ocr_result=merged,
                mode="ocr_only",
                processing_time_ms=elapsed,
                errors=errors,
            )

        # Step 2: LLM extraction (with retry built into provider)
        context = self._build_context(merged)
        data = None
        try:
            data = self.llm_provider.extract_fields(merged.text, schema, context)
        except Exception as e:
            errors.append(f"LLM extraction failed: {e}")
            logger.error("LLM extraction failed: %s", e)

        # Step 3: Validation (even partial data gets validated)
        validation = ValidationResult()
        if data:
            validation = self._validate(data, schema)
        else:
            data = {}

        # Step 4: Build confidence scores
        confidence = self._estimate_confidence(data, merged) if data else {}

        elapsed = (time.monotonic() - start) * 1000
        schema_name = schema.__name__ if hasattr(schema, "__name__") else ""

        return ExtractionResult(
            data=data,
            confidence=confidence,
            validation=validation,
            ocr_result=merged,
            text=merged.text,
            markdown=merged.to_markdown(),
            schema_name=schema_name,
            mode="ocr+llm",
            processing_time_ms=elapsed,
            errors=errors,
        )

    def _extract_vlm(
        self,
        images: list[Image.Image],
        schema: type[BaseModel] | None,
        start: float,
        errors: list[str],
    ) -> ExtractionResult:
        """VLM direct extraction — image → JSON (skip OCR)."""
        if schema is None:
            raise ValueError("VLM mode requires a schema")

        # Encode first page as base64
        img = images[0]
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        img_b64 = base64.b64encode(buffer.getvalue()).decode()

        data = None
        try:
            data = self.llm_provider.extract_from_image(img_b64, schema)
        except Exception as e:
            errors.append(f"VLM extraction failed: {e}")
            logger.error("VLM extraction failed: %s", e)

        validation = ValidationResult()
        if data:
            validation = self._validate(data, schema)
        else:
            data = {}

        elapsed = (time.monotonic() - start) * 1000
        schema_name = schema.__name__ if hasattr(schema, "__name__") else ""

        return ExtractionResult(
            data=data,
            validation=validation,
            schema_name=schema_name,
            mode="vlm",
            processing_time_ms=elapsed,
            errors=errors,
        )

    def _merge_ocr_results(self, results: list[OCRResult]) -> OCRResult:
        """Merge multi-page OCR results into one."""
        if len(results) == 1:
            return results[0]

        all_blocks = []
        all_tables = []
        all_text = []
        total_time = 0.0

        for i, r in enumerate(results):
            for block in r.blocks:
                block.page = i
                all_blocks.append(block)
            for table in r.tables:
                table.page = i
                all_tables.append(table)
            all_text.append(r.text)
            total_time += r.processing_time_ms

        return OCRResult(
            text="\n\n".join(all_text),
            blocks=all_blocks,
            tables=all_tables,
            engine=results[0].engine if results else "",
            processing_time_ms=total_time,
        )

    def _build_context(self, ocr: OCRResult) -> dict[str, Any]:
        """Build LLM context from OCR results."""
        context: dict[str, Any] = {}
        if ocr.tables:
            context["tables"] = [t.to_markdown() for t in ocr.tables]
        if ocr.low_confidence_blocks:
            context["low_confidence"] = [
                {"text": b.text, "confidence": b.confidence}
                for b in ocr.low_confidence_blocks[:10]
            ]
        if ocr.layout and ocr.layout.detected_languages:
            context["language"] = ", ".join(ocr.layout.detected_languages)
        return context

    def _validate(self, data: dict[str, Any], schema: type[BaseModel]) -> ValidationResult:
        """Run validation rules if schema defines them."""
        if not self.config.validation.enabled:
            return ValidationResult()

        # Check for ValidationRules inner class
        rules_class = getattr(schema, "ValidationRules", None)
        if rules_class is None:
            return ValidationResult()

        rules = getattr(rules_class, "rules", [])
        if not rules:
            return ValidationResult()

        from docpick.validation.base import Validator
        validator = Validator(rules)
        return validator.validate(data)

    def _estimate_confidence(self, data: dict[str, Any], ocr: OCRResult) -> dict[str, float]:
        """Estimate per-field confidence based on OCR confidence scores."""
        if not ocr.blocks:
            return {}

        confidence: dict[str, float] = {}
        avg_conf = ocr.avg_confidence

        for key, value in data.items():
            if value is None:
                confidence[key] = 0.0
            elif isinstance(value, str) and value:
                # Find matching OCR block
                matching = [b for b in ocr.blocks if value.lower() in b.text.lower()]
                if matching:
                    confidence[key] = max(b.confidence for b in matching)
                else:
                    confidence[key] = avg_conf * 0.8  # Slightly lower if no direct match
            else:
                confidence[key] = avg_conf

        return confidence
