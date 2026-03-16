"""OCR engine abstract base class."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from PIL import Image

from docpick.core.result import OCRResult


class OCREngine(ABC):
    """Abstract base class for OCR backends."""

    @abstractmethod
    def recognize(self, image: Image.Image, languages: list[str] | None = None) -> OCRResult:
        """Run OCR on a single image and return structured result.

        Args:
            image: PIL Image to process.
            languages: Language codes (e.g., ["ko", "en"]). None = use default.

        Returns:
            OCRResult with text, blocks, tables, and layout info.
        """
        ...

    def recognize_file(self, path: str | Path, languages: list[str] | None = None) -> OCRResult:
        """Run OCR on an image file."""
        image = Image.open(path).convert("RGB")
        return self.recognize(image, languages)

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this engine is installed and usable."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Engine identifier (e.g., 'paddle', 'easyocr')."""
        ...

    @property
    @abstractmethod
    def requires_gpu(self) -> bool:
        """Whether this engine requires GPU."""
        ...

    @property
    @abstractmethod
    def supported_languages(self) -> list[str]:
        """List of supported language codes."""
        ...
