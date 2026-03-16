"""Auto engine selection — pick the best available OCR engine with confidence-based fallback."""

from __future__ import annotations

import logging

from PIL import Image

from docpick.core.result import OCRResult
from docpick.ocr.base import OCREngine

logger = logging.getLogger(__name__)

# Tier 1 (CPU, lightweight): paddle > easyocr
# Tier 2 (GPU, heavyweight): got > vlm
_TIER1_PRIORITY = ["paddle", "easyocr"]
_TIER2_PRIORITY = ["got", "vlm"]


def _try_import_engine(name: str, **kwargs) -> OCREngine | None:
    """Try to import and instantiate an engine by name."""
    try:
        if name == "paddle":
            from docpick.ocr.paddle import PaddleOCREngine
            engine = PaddleOCREngine(**kwargs)
            if engine.is_available():
                return engine
        elif name == "easyocr":
            from docpick.ocr.easyocr_engine import EasyOCREngine
            engine = EasyOCREngine(**kwargs)
            if engine.is_available():
                return engine
        elif name == "got":
            from docpick.ocr.got import GOTOCREngine
            engine = GOTOCREngine(**kwargs)
            if engine.is_available():
                return engine
        elif name == "vlm":
            from docpick.ocr.vlm import VLMOCREngine
            engine = VLMOCREngine(**kwargs)
            if engine.is_available():
                return engine
    except Exception as e:
        logger.debug("Failed to load engine %s: %s", name, e)
    return None


class AutoEngine(OCREngine):
    """Automatically select the best available OCR engine.

    Supports confidence-based Tier 2 fallback:
    1. Run Tier 1 (lightweight CPU OCR)
    2. If avg confidence < threshold, re-run with Tier 2 (GPU VLM/GOT)
    """

    def __init__(
        self,
        confidence_threshold: float = 0.7,
        enable_fallback: bool = True,
    ) -> None:
        self._tier1: OCREngine | None = None
        self._tier2: OCREngine | None = None
        self._confidence_threshold = confidence_threshold
        self._enable_fallback = enable_fallback

    def _resolve_tier1(self) -> OCREngine:
        if self._tier1 is not None:
            return self._tier1

        for name in _TIER1_PRIORITY:
            engine = _try_import_engine(name)
            if engine is not None:
                logger.info("Tier 1 OCR engine: %s", name)
                self._tier1 = engine
                return engine

        raise RuntimeError(
            "No Tier 1 OCR engine available. Install one:\n"
            "  pip install docpick[paddle]   # PaddleOCR (recommended)\n"
            "  pip install docpick[easyocr]  # EasyOCR"
        )

    def _resolve_tier2(self) -> OCREngine | None:
        if self._tier2 is not None:
            return self._tier2

        for name in _TIER2_PRIORITY:
            engine = _try_import_engine(name)
            if engine is not None:
                logger.info("Tier 2 OCR engine: %s", name)
                self._tier2 = engine
                return engine

        logger.debug("No Tier 2 engine available for fallback")
        return None

    def recognize(self, image: Image.Image, languages: list[str] | None = None) -> OCRResult:
        # Step 1: Tier 1 (lightweight OCR)
        tier1 = self._resolve_tier1()
        result = tier1.recognize(image, languages)

        # Step 2: Check confidence — fallback to Tier 2 if low
        if (
            self._enable_fallback
            and result.avg_confidence < self._confidence_threshold
            and result.blocks  # Only fallback if there were results
        ):
            tier2 = self._resolve_tier2()
            if tier2 is not None:
                logger.info(
                    "Tier 1 avg confidence %.2f < %.2f, falling back to Tier 2 (%s)",
                    result.avg_confidence,
                    self._confidence_threshold,
                    tier2.name,
                )
                tier2_result = tier2.recognize(image, languages)
                # Use Tier 2 result if it produced text
                if tier2_result.text.strip():
                    tier2_result.metadata["fallback_from"] = tier1.name
                    tier2_result.metadata["tier1_confidence"] = result.avg_confidence
                    return tier2_result

        return result

    def is_available(self) -> bool:
        try:
            self._resolve_tier1()
            return True
        except RuntimeError:
            return False

    @property
    def name(self) -> str:
        try:
            return self._resolve_tier1().name
        except RuntimeError:
            return "auto(none)"

    @property
    def requires_gpu(self) -> bool:
        try:
            return self._resolve_tier1().requires_gpu
        except RuntimeError:
            return False

    @property
    def supported_languages(self) -> list[str]:
        try:
            return self._resolve_tier1().supported_languages
        except RuntimeError:
            return []


def estimate_complexity(image: Image.Image) -> float:
    """Estimate document complexity (0.0=simple, 1.0=complex).

    Heuristic based on image properties. Higher complexity suggests
    using Tier 2 (VLM/GOT) over Tier 1 (lightweight OCR).
    """
    w, h = image.size
    aspect_ratio = max(w, h) / min(w, h) if min(w, h) > 0 else 1.0

    score = 0.0

    # Large images tend to have more complex layouts
    if w * h > 4_000_000:  # >4MP
        score += 0.2

    # Unusual aspect ratios suggest multi-column or complex layouts
    if aspect_ratio > 2.0:
        score += 0.2

    # Check for color complexity (grayscale vs color)
    if image.mode == "RGB":
        import numpy as np
        arr = np.array(image)
        # High std dev in color channels suggests photos/complex docs
        color_std = arr.std()
        if color_std > 60:
            score += 0.3

    return min(score, 1.0)


def get_engine(name: str = "auto", **kwargs) -> OCREngine:
    """Get an OCR engine by name.

    Args:
        name: Engine name ('auto', 'paddle', 'easyocr', 'got', 'vlm').

    Returns:
        Instantiated OCR engine.
    """
    if name == "auto":
        return AutoEngine(**{k: v for k, v in kwargs.items() if k in ("confidence_threshold", "enable_fallback")})
    if name == "paddle":
        from docpick.ocr.paddle import PaddleOCREngine
        return PaddleOCREngine(**kwargs)
    if name == "easyocr":
        from docpick.ocr.easyocr_engine import EasyOCREngine
        return EasyOCREngine(**kwargs)
    if name == "got":
        from docpick.ocr.got import GOTOCREngine
        return GOTOCREngine(**kwargs)
    if name == "vlm":
        from docpick.ocr.vlm import VLMOCREngine
        return VLMOCREngine(**kwargs)
    raise ValueError(f"Unknown OCR engine: {name}. Available: auto, paddle, easyocr, got, vlm")
