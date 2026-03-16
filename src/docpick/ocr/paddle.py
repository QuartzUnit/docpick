"""PaddleOCR backend — default OCR engine."""

from __future__ import annotations

import time

from PIL import Image

from docpick.core.result import LayoutInfo, OCRResult, Table, TableCell, TextBlock
from docpick.ocr.base import OCREngine

# PaddleOCR language code mapping
_LANG_MAP = {
    "ko": "korean",
    "en": "en",
    "ja": "japan",
    "zh": "ch",
    "zh-cn": "ch",
    "zh-tw": "chinese_cht",
    "fr": "french",
    "de": "german",
    "es": "es",
    "pt": "pt",
    "it": "it",
    "ru": "ru",
    "ar": "ar",
}


def _map_lang(lang: str) -> str:
    return _LANG_MAP.get(lang, lang)


class PaddleOCREngine(OCREngine):
    """PaddleOCR v5 backend (Apache 2.0, 111 languages)."""

    def __init__(self) -> None:
        self._ocr: dict[str, object] = {}

    def _get_ocr(self, languages: list[str] | None = None):
        """Lazy-init PaddleOCR instance per language."""
        try:
            from paddleocr import PaddleOCR
        except ImportError as e:
            raise ImportError(
                "PaddleOCR is required. Install with: pip install docpick[paddle]"
            ) from e

        lang = _map_lang(languages[0]) if languages else "korean"
        if lang not in self._ocr:
            self._ocr[lang] = PaddleOCR(lang=lang)
        return self._ocr[lang]

    def recognize(self, image: Image.Image, languages: list[str] | None = None) -> OCRResult:
        import numpy as np
        import os

        os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
        start = time.monotonic()
        ocr = self._get_ocr(languages)

        # Save image to temp file (PaddleOCR v3.4+ predict() expects file path)
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            image.save(f, format="PNG")
            tmp_path = f.name

        try:
            results = list(ocr.predict(tmp_path))
        finally:
            os.unlink(tmp_path)

        blocks: list[TextBlock] = []
        full_text_parts: list[str] = []
        w, h = image.size

        if results:
            r = results[0]
            texts = r.get("rec_texts", [])
            scores = r.get("rec_scores", [])
            polys = r.get("dt_polys", [])

            for i, text in enumerate(texts):
                conf = scores[i] if i < len(scores) else 0.0
                if i < len(polys):
                    poly = polys[i]
                    x_coords = [p[0] for p in poly]
                    y_coords = [p[1] for p in poly]
                    bbox = (
                        min(x_coords) / w,
                        min(y_coords) / h,
                        max(x_coords) / w,
                        max(y_coords) / h,
                    )
                else:
                    bbox = (0.0, 0.0, 1.0, 1.0)
                blocks.append(TextBlock(text=text, bbox=bbox, confidence=conf))
                full_text_parts.append(text)

        elapsed = (time.monotonic() - start) * 1000

        return OCRResult(
            text="\n".join(full_text_parts),
            blocks=blocks,
            layout=LayoutInfo(page_count=1, detected_languages=languages or ["ko", "en"]),
            engine="paddle",
            processing_time_ms=elapsed,
        )

    def is_available(self) -> bool:
        try:
            import paddleocr  # noqa: F401
            return True
        except ImportError:
            return False

    @property
    def name(self) -> str:
        return "paddle"

    @property
    def requires_gpu(self) -> bool:
        return False  # CPU OK, GPU optional

    @property
    def supported_languages(self) -> list[str]:
        return list(_LANG_MAP.keys())
