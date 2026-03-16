"""LLM provider abstract base class."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class LLMProvider(ABC):
    """Abstract base class for LLM-based field extraction."""

    @abstractmethod
    def extract_fields(
        self,
        text: str,
        schema: type[BaseModel],
        context: dict[str, Any] | None = None,
        max_retries: int = 1,
    ) -> dict[str, Any]:
        """Extract structured fields from OCR text using LLM.

        Args:
            text: OCR-extracted text from the document.
            schema: Pydantic model defining expected fields.
            context: Additional context (bounding boxes, confidence, tables).
            max_retries: Number of retries on JSON parse failure.

        Returns:
            Dict matching the schema fields.
        """
        ...

    @abstractmethod
    def extract_from_image(
        self,
        image_base64: str,
        schema: type[BaseModel],
        max_retries: int = 1,
    ) -> dict[str, Any]:
        """Extract fields directly from image using VLM.

        Args:
            image_base64: Base64-encoded image.
            schema: Pydantic model defining expected fields.
            max_retries: Number of retries on JSON parse failure.

        Returns:
            Dict matching the schema fields.
        """
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the LLM provider is reachable."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier."""
        ...
