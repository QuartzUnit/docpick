"""Document loading and preprocessing."""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

from PIL import Image


SUPPORTED_IMAGE_FORMATS = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp"}
SUPPORTED_PDF_FORMATS = {".pdf"}
SUPPORTED_FORMATS = SUPPORTED_IMAGE_FORMATS | SUPPORTED_PDF_FORMATS


class DocumentLoader:
    """Load documents (PDF/images) and yield pages as PIL Images."""

    def __init__(self, dpi: int = 300) -> None:
        self.dpi = dpi

    def load(self, path: str | Path) -> list[Image.Image]:
        """Load a document and return list of page images."""
        return list(self.iter_pages(path))

    def iter_pages(self, path: str | Path) -> Iterator[Image.Image]:
        """Iterate over document pages as PIL Images."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Document not found: {path}")

        suffix = path.suffix.lower()
        if suffix in SUPPORTED_IMAGE_FORMATS:
            yield Image.open(path).convert("RGB")
        elif suffix in SUPPORTED_PDF_FORMATS:
            yield from self._load_pdf(path)
        else:
            raise ValueError(f"Unsupported format: {suffix}. Supported: {SUPPORTED_FORMATS}")

    def _load_pdf(self, path: Path) -> Iterator[Image.Image]:
        """Convert PDF pages to images using pypdfium2."""
        try:
            import pypdfium2 as pdfium
        except ImportError as e:
            raise ImportError(
                "pypdfium2 is required for PDF support. Install with: pip install pypdfium2"
            ) from e

        pdf = pdfium.PdfDocument(str(path))
        try:
            for i in range(len(pdf)):
                page = pdf[i]
                bitmap = page.render(scale=self.dpi / 72)
                image = bitmap.to_pil().convert("RGB")
                yield image
        finally:
            pdf.close()

    @staticmethod
    def is_supported(path: str | Path) -> bool:
        """Check if the file format is supported."""
        return Path(path).suffix.lower() in SUPPORTED_FORMATS

    @staticmethod
    def detect_type(path: str | Path) -> str:
        """Detect document type: 'image' or 'pdf'."""
        suffix = Path(path).suffix.lower()
        if suffix in SUPPORTED_IMAGE_FORMATS:
            return "image"
        if suffix in SUPPORTED_PDF_FORMATS:
            return "pdf"
        raise ValueError(f"Unsupported format: {suffix}")
