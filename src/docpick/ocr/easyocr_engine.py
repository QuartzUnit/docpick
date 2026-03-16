"""EasyOCR backend — Korean-optimized fallback."""

from __future__ import annotations

import time

import numpy as np
from PIL import Image

from docpick.core.result import LayoutInfo, OCRResult, TextBlock
from docpick.ocr.base import OCREngine


class EasyOCREngine(OCREngine):
    """EasyOCR backend (Apache 2.0, 80+ languages, Korean-optimized)."""

    def __init__(self, use_gpu: bool = False) -> None:
        self._reader = None
        self._use_gpu = use_gpu
        self._current_langs: list[str] | None = None

    def _get_reader(self, languages: list[str] | None = None):
        langs = languages or ["ko", "en"]
        if self._reader is not None and self._current_langs == langs:
            return self._reader

        try:
            import easyocr
        except ImportError as e:
            raise ImportError(
                "EasyOCR is required. Install with: pip install docpick[easyocr]"
            ) from e

        self._reader = easyocr.Reader(langs, gpu=self._use_gpu)
        self._current_langs = langs
        return self._reader

    def recognize(self, image: Image.Image, languages: list[str] | None = None) -> OCRResult:
        start = time.monotonic()
        reader = self._get_reader(languages)

        img_array = np.array(image)
        raw = reader.readtext(img_array)

        blocks: list[TextBlock] = []
        full_text_parts: list[str] = []
        h, w = img_array.shape[:2]

        for bbox_raw, text, conf in raw:
            x_coords = [p[0] for p in bbox_raw]
            y_coords = [p[1] for p in bbox_raw]
            bbox = (
                min(x_coords) / w,
                min(y_coords) / h,
                max(x_coords) / w,
                max(y_coords) / h,
            )
            blocks.append(TextBlock(text=text, bbox=bbox, confidence=conf))
            full_text_parts.append(text)

        elapsed = (time.monotonic() - start) * 1000

        return OCRResult(
            text="\n".join(full_text_parts),
            blocks=blocks,
            layout=LayoutInfo(page_count=1, detected_languages=languages or ["ko", "en"]),
            engine="easyocr",
            processing_time_ms=elapsed,
        )

    def is_available(self) -> bool:
        try:
            import easyocr  # noqa: F401
            return True
        except ImportError:
            return False

    @property
    def name(self) -> str:
        return "easyocr"

    @property
    def requires_gpu(self) -> bool:
        return False

    @property
    def supported_languages(self) -> list[str]:
        return ["ko", "en", "ja", "zh", "fr", "de", "es", "pt", "it", "ru", "ar"]
