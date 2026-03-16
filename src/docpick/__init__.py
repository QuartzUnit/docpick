"""Docpick — Schema-driven document extraction with local OCR + LLM.

Document in, Structured JSON out. Locally. With your schema.
"""

__version__ = "0.1.0"

from docpick.core.pipeline import DocpickPipeline
from docpick.core.config import DocpickConfig
from docpick.core.result import ExtractionResult, OCRResult

__all__ = [
    "DocpickPipeline",
    "DocpickConfig",
    "ExtractionResult",
    "OCRResult",
]
