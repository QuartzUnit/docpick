"""Batch document processing."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel

from docpick.core.config import DocpickConfig
from docpick.core.pipeline import DocpickPipeline
from docpick.core.result import ExtractionResult

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp"}


@dataclass
class BatchResult:
    """Result of batch processing."""

    total: int = 0
    succeeded: int = 0
    failed: int = 0
    results: dict[str, ExtractionResult] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)
    processing_time_ms: float = 0.0

    @property
    def summary(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "processing_time_ms": self.processing_time_ms,
            "errors": self.errors,
        }


class BatchProcessor:
    """Process multiple documents in parallel."""

    def __init__(
        self,
        config: DocpickConfig | None = None,
        concurrency: int = 4,
    ) -> None:
        self.config = config or DocpickConfig.load()
        self.concurrency = concurrency

    def process_directory(
        self,
        directory: str | Path,
        schema: type[BaseModel] | None = None,
        mode: str = "auto",
        languages: list[str] | None = None,
        recursive: bool = False,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> BatchResult:
        """Process all supported documents in a directory.

        Args:
            directory: Path to directory containing documents.
            schema: Pydantic model for extraction. None = OCR only.
            mode: Extraction mode.
            languages: OCR languages.
            recursive: Search subdirectories.
            on_progress: Callback(completed, total) for progress updates.

        Returns:
            BatchResult with per-file results and summary.
        """
        return asyncio.run(self._process_async(
            directory, schema, mode, languages, recursive, on_progress
        ))

    async def _process_async(
        self,
        directory: str | Path,
        schema: type[BaseModel] | None,
        mode: str,
        languages: list[str] | None,
        recursive: bool,
        on_progress: Callable[[int, int], None] | None,
    ) -> BatchResult:
        directory = Path(directory)
        files = self._find_files(directory, recursive)
        result = BatchResult(total=len(files))
        start = time.monotonic()

        if not files:
            return result

        semaphore = asyncio.Semaphore(self.concurrency)
        pipeline = DocpickPipeline(self.config)

        async def process_one(file_path: Path) -> None:
            async with semaphore:
                try:
                    loop = asyncio.get_event_loop()
                    extraction = await loop.run_in_executor(
                        None,
                        lambda fp=file_path: pipeline.extract(
                            fp, schema=schema, mode=mode, languages=languages
                        ),
                    )
                    result.results[str(file_path)] = extraction
                    if extraction.errors:
                        result.failed += 1
                        result.errors[str(file_path)] = "; ".join(extraction.errors)
                    else:
                        result.succeeded += 1
                except Exception as e:
                    result.errors[str(file_path)] = str(e)
                    result.failed += 1
                    logger.error("Failed to process %s: %s", file_path, e)
                finally:
                    if on_progress:
                        on_progress(result.succeeded + result.failed, result.total)

        tasks = [process_one(f) for f in files]
        await asyncio.gather(*tasks)

        result.processing_time_ms = (time.monotonic() - start) * 1000
        return result

    @staticmethod
    def _find_files(directory: Path, recursive: bool) -> list[Path]:
        """Find all supported document files."""
        if recursive:
            files = [f for f in directory.rglob("*") if f.suffix.lower() in SUPPORTED_EXTENSIONS]
        else:
            files = [f for f in directory.iterdir() if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS]
        return sorted(files)
