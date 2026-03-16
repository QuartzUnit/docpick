"""VLM-based OCR backend — use vision-language models for OCR via OpenAI-compatible API."""

from __future__ import annotations

import base64
import io
import time
from typing import Any

import httpx
from PIL import Image

from docpick.core.result import LayoutInfo, OCRResult, TextBlock
from docpick.ocr.base import OCREngine

_SYSTEM_PROMPT = (
    "You are a document OCR assistant. Extract ALL text from the provided document image.\n"
    "Output the text exactly as it appears in the document, preserving the layout.\n"
    "For tables, use markdown table format.\n"
    "Do not add any explanations or formatting beyond the document content."
)


class VLMOCREngine(OCREngine):
    """VLM-based OCR using OpenAI-compatible vision API.

    Sends document images to a VLM endpoint and gets structured text back.
    Works with any OpenAI-compatible VLM: PaddleOCR-VL, Qwen-VL, InternVL, etc.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8081/v1",
        model: str = "Qwen/Qwen3-VL-4B",
        temperature: float = 0.0,
        max_tokens: int = 4096,
        timeout: int = 60,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout

    def _image_to_base64(self, image: Image.Image) -> str:
        """Convert PIL Image to base64 string."""
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode()

    def _call_vlm(self, image_b64: str, prompt: str) -> str:
        """Call VLM endpoint with image."""
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                        },
                    ],
                },
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(f"{self.base_url}/chat/completions", json=payload)
            resp.raise_for_status()
            data = resp.json()

        return data["choices"][0]["message"]["content"]

    def recognize(self, image: Image.Image, languages: list[str] | None = None) -> OCRResult:
        start = time.monotonic()

        image_b64 = self._image_to_base64(image)
        lang_hint = ""
        if languages:
            lang_hint = f" The document may contain text in: {', '.join(languages)}."

        prompt = f"Extract all text from this document image.{lang_hint}"
        result_text = self._call_vlm(image_b64, prompt)

        # Parse VLM response into text blocks
        blocks: list[TextBlock] = []
        lines = result_text.strip().split("\n") if result_text else []
        for i, line in enumerate(lines):
            if line.strip():
                y_pos = i / max(len(lines), 1)
                blocks.append(TextBlock(
                    text=line.strip(),
                    bbox=(0.0, y_pos, 1.0, y_pos + 1 / max(len(lines), 1)),
                    confidence=0.85,  # VLM confidence estimate
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
            engine="vlm",
            processing_time_ms=elapsed,
            metadata={"model": self.model, "base_url": self.base_url},
        )

    def is_available(self) -> bool:
        try:
            with httpx.Client(timeout=5) as client:
                resp = client.get(f"{self.base_url}/models")
                return resp.status_code == 200
        except Exception:
            return False

    @property
    def name(self) -> str:
        return "vlm"

    @property
    def requires_gpu(self) -> bool:
        return True  # VLM inference requires GPU

    @property
    def supported_languages(self) -> list[str]:
        # VLMs are typically multilingual
        return ["ko", "en", "ja", "zh", "fr", "de", "es", "pt", "it", "ru", "ar"]
