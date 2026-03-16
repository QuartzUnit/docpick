"""GOT-OCR2.0 backend — end-to-end transformer OCR (580M params)."""

from __future__ import annotations

import time

from PIL import Image

from docpick.core.result import LayoutInfo, OCRResult, TextBlock
from docpick.ocr.base import OCREngine


class GOTOCREngine(OCREngine):
    """GOT-OCR2.0 backend using HuggingFace transformers.

    End-to-end vision-language OCR model that directly produces
    formatted text output from document images. Supports fine-grained
    and plain text modes.

    Requires: pip install docpick[got]
    """

    def __init__(
        self,
        model_name: str = "stepfun-ai/GOT-OCR-2.0-hf",
        device: str = "auto",
        ocr_type: str = "ocr",
    ) -> None:
        self._model_name = model_name
        self._device = device
        self._ocr_type = ocr_type  # "ocr" (plain) or "format" (markdown/latex)
        self._model = None
        self._processor = None

    def _load_model(self):
        """Lazy-load the GOT-OCR2.0 model."""
        if self._model is not None:
            return

        try:
            from transformers import AutoModel, AutoTokenizer
        except ImportError as e:
            raise ImportError(
                "GOT-OCR2.0 requires transformers and torch. "
                "Install with: pip install docpick[got]"
            ) from e

        import torch

        device = self._device
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"

        self._processor = AutoTokenizer.from_pretrained(self._model_name, trust_remote_code=True)
        self._model = AutoModel.from_pretrained(
            self._model_name,
            trust_remote_code=True,
            torch_dtype=torch.float16 if device != "cpu" else torch.float32,
            device_map=device if device != "cpu" else None,
        )
        if device == "cpu":
            self._model = self._model.to("cpu")
        self._model.eval()

    def recognize(self, image: Image.Image, languages: list[str] | None = None) -> OCRResult:
        start = time.monotonic()
        self._load_model()

        # GOT-OCR2.0 processes image directly
        result_text = self._model.chat(self._processor, image, ocr_type=self._ocr_type)

        # Parse result into blocks (GOT returns plain text or formatted)
        blocks: list[TextBlock] = []
        lines = result_text.strip().split("\n") if result_text else []
        for i, line in enumerate(lines):
            if line.strip():
                # Approximate vertical position based on line index
                y_pos = i / max(len(lines), 1)
                blocks.append(TextBlock(
                    text=line.strip(),
                    bbox=(0.0, y_pos, 1.0, y_pos + 1 / max(len(lines), 1)),
                    confidence=0.9,  # GOT doesn't provide per-line confidence
                    block_type="text",
                ))

        elapsed = (time.monotonic() - start) * 1000

        return OCRResult(
            text=result_text.strip() if result_text else "",
            blocks=blocks,
            layout=LayoutInfo(
                page_count=1,
                detected_languages=languages or [],
            ),
            engine="got",
            processing_time_ms=elapsed,
            metadata={"model": self._model_name, "ocr_type": self._ocr_type},
        )

    def is_available(self) -> bool:
        try:
            import transformers  # noqa: F401
            import torch  # noqa: F401
            return True
        except ImportError:
            return False

    @property
    def name(self) -> str:
        return "got"

    @property
    def requires_gpu(self) -> bool:
        return True  # Practical use requires GPU

    @property
    def supported_languages(self) -> list[str]:
        # GOT-OCR2.0 supports multilingual but doesn't need language specification
        return ["en", "zh", "ko", "ja", "fr", "de", "es", "pt", "it", "ru", "ar"]
