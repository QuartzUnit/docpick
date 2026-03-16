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

    def __init__(self, use_gpu: bool | None = None, use_structure: bool = True) -> None:
        self._ocr = None
        self._use_gpu = use_gpu
        self._use_structure = use_structure

    def _get_ocr(self, languages: list[str] | None = None):
        """Lazy-init PaddleOCR instance."""
        if self._ocr is not None:
            return self._ocr

        try:
            from paddleocr import PaddleOCR
        except ImportError as e:
            raise ImportError(
                "PaddleOCR is required. Install with: pip install docpick[paddle]"
            ) from e

        lang = _map_lang(languages[0]) if languages else "korean"
        use_gpu = self._use_gpu
        if use_gpu is None:
            try:
                import paddle
                use_gpu = paddle.device.is_compiled_with_cuda()
            except Exception:
                use_gpu = False

        self._ocr = PaddleOCR(
            use_angle_cls=True,
            lang=lang,
            use_gpu=use_gpu,
            show_log=False,
        )
        return self._ocr

    def recognize(self, image: Image.Image, languages: list[str] | None = None) -> OCRResult:
        import numpy as np

        start = time.monotonic()
        ocr = self._get_ocr(languages)

        img_array = np.array(image)
        raw = ocr.ocr(img_array, cls=True)

        blocks: list[TextBlock] = []
        full_text_parts: list[str] = []
        h, w = img_array.shape[:2]

        if raw and raw[0]:
            for line in raw[0]:
                box, (text, conf) = line[0], line[1]
                # Normalize bbox to 0~1
                x_coords = [p[0] for p in box]
                y_coords = [p[1] for p in box]
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
