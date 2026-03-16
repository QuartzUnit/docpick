"""Tests for batch processing."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from docpick.batch import BatchProcessor, BatchResult, SUPPORTED_EXTENSIONS
from docpick.core.config import DocpickConfig
from docpick.core.result import ExtractionResult


# === BatchResult ===

def test_batch_result_defaults():
    result = BatchResult()
    assert result.total == 0
    assert result.succeeded == 0
    assert result.failed == 0
    assert result.results == {}
    assert result.errors == {}


def test_batch_result_summary():
    result = BatchResult(total=10, succeeded=8, failed=2, processing_time_ms=5000.0)
    summary = result.summary
    assert summary["total"] == 10
    assert summary["succeeded"] == 8
    assert summary["failed"] == 2
    assert summary["processing_time_ms"] == 5000.0


# === SUPPORTED_EXTENSIONS ===

def test_supported_extensions():
    assert ".pdf" in SUPPORTED_EXTENSIONS
    assert ".png" in SUPPORTED_EXTENSIONS
    assert ".jpg" in SUPPORTED_EXTENSIONS
    assert ".jpeg" in SUPPORTED_EXTENSIONS
    assert ".tiff" in SUPPORTED_EXTENSIONS
    assert ".bmp" in SUPPORTED_EXTENSIONS
    assert ".webp" in SUPPORTED_EXTENSIONS
    assert ".txt" not in SUPPORTED_EXTENSIONS
    assert ".doc" not in SUPPORTED_EXTENSIONS


# === _find_files ===

def test_find_files_non_recursive(tmp_path):
    (tmp_path / "a.pdf").touch()
    (tmp_path / "b.png").touch()
    (tmp_path / "c.txt").touch()
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "d.jpg").touch()

    files = BatchProcessor._find_files(tmp_path, recursive=False)
    names = [f.name for f in files]
    assert "a.pdf" in names
    assert "b.png" in names
    assert "c.txt" not in names
    assert "d.jpg" not in names


def test_find_files_recursive(tmp_path):
    (tmp_path / "a.pdf").touch()
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.jpg").touch()
    (tmp_path / "sub" / "deep").mkdir()
    (tmp_path / "sub" / "deep" / "c.tiff").touch()

    files = BatchProcessor._find_files(tmp_path, recursive=True)
    names = [f.name for f in files]
    assert "a.pdf" in names
    assert "b.jpg" in names
    assert "c.tiff" in names


def test_find_files_empty_directory(tmp_path):
    files = BatchProcessor._find_files(tmp_path, recursive=False)
    assert files == []


def test_find_files_sorted(tmp_path):
    (tmp_path / "c.png").touch()
    (tmp_path / "a.pdf").touch()
    (tmp_path / "b.jpg").touch()

    files = BatchProcessor._find_files(tmp_path, recursive=False)
    names = [f.name for f in files]
    assert names == ["a.pdf", "b.jpg", "c.png"]


# === BatchProcessor.process_directory ===

def test_batch_process_empty_directory(tmp_path):
    processor = BatchProcessor()
    result = processor.process_directory(tmp_path)
    assert result.total == 0
    assert result.succeeded == 0
    assert result.failed == 0


def test_batch_process_with_mock_pipeline(tmp_path):
    """Process files with mocked pipeline."""
    (tmp_path / "test1.png").write_bytes(b"fake image data")
    (tmp_path / "test2.png").write_bytes(b"fake image data")

    mock_extraction = ExtractionResult(
        data={"field": "value"},
        text="extracted text",
        mode="ocr+llm",
    )

    with patch("docpick.batch.DocpickPipeline") as MockPipeline:
        mock_instance = MockPipeline.return_value
        mock_instance.extract.return_value = mock_extraction

        processor = BatchProcessor()
        result = processor.process_directory(tmp_path)

    assert result.total == 2
    assert result.succeeded == 2
    assert result.failed == 0
    assert len(result.results) == 2


def test_batch_process_with_failures(tmp_path):
    """Files that fail are tracked in errors."""
    (tmp_path / "good.png").write_bytes(b"fake")
    (tmp_path / "bad.jpg").write_bytes(b"fake")

    def mock_extract(source, **kwargs):
        if "bad" in str(source):
            raise RuntimeError("Processing failed")
        return ExtractionResult(data={"ok": True}, mode="ocr_only")

    with patch("docpick.batch.DocpickPipeline") as MockPipeline:
        mock_instance = MockPipeline.return_value
        mock_instance.extract.side_effect = mock_extract

        processor = BatchProcessor()
        result = processor.process_directory(tmp_path)

    assert result.total == 2
    assert result.succeeded == 1
    assert result.failed == 1
    assert len(result.errors) == 1


def test_batch_process_with_pipeline_errors(tmp_path):
    """Files with pipeline errors (non-exception) tracked as failed."""
    (tmp_path / "warn.png").write_bytes(b"fake")

    mock_extraction = ExtractionResult(
        data={},
        mode="ocr+llm",
        errors=["OCR engine 'paddle' failed: crash"],
    )

    with patch("docpick.batch.DocpickPipeline") as MockPipeline:
        mock_instance = MockPipeline.return_value
        mock_instance.extract.return_value = mock_extraction

        processor = BatchProcessor()
        result = processor.process_directory(tmp_path)

    assert result.total == 1
    assert result.failed == 1
    assert result.succeeded == 0


def test_batch_progress_callback(tmp_path):
    """Progress callback is invoked."""
    (tmp_path / "a.pdf").write_bytes(b"fake")
    (tmp_path / "b.pdf").write_bytes(b"fake")

    progress_calls = []

    def on_progress(completed, total):
        progress_calls.append((completed, total))

    mock_extraction = ExtractionResult(data={"ok": True}, mode="ocr_only")

    with patch("docpick.batch.DocpickPipeline") as MockPipeline:
        mock_instance = MockPipeline.return_value
        mock_instance.extract.return_value = mock_extraction

        processor = BatchProcessor()
        processor.process_directory(tmp_path, on_progress=on_progress)

    assert len(progress_calls) == 2
    # Last call should show all done
    assert progress_calls[-1][0] == 2
    assert progress_calls[-1][1] == 2


def test_batch_concurrency_setting():
    processor = BatchProcessor(concurrency=8)
    assert processor.concurrency == 8


def test_batch_recursive_processing(tmp_path):
    """Recursive flag processes subdirectories."""
    (tmp_path / "a.png").write_bytes(b"fake")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.png").write_bytes(b"fake")

    mock_extraction = ExtractionResult(data={"ok": True}, mode="ocr_only")

    with patch("docpick.batch.DocpickPipeline") as MockPipeline:
        mock_instance = MockPipeline.return_value
        mock_instance.extract.return_value = mock_extraction

        processor = BatchProcessor()
        result = processor.process_directory(tmp_path, recursive=True)

    assert result.total == 2
    assert result.succeeded == 2
