"""Tests for DocumentLoader."""

import tempfile
from pathlib import Path

import pytest
from PIL import Image

from docpick.core.document import DocumentLoader, SUPPORTED_FORMATS


@pytest.fixture
def loader():
    return DocumentLoader()


@pytest.fixture
def sample_image(tmp_path):
    img = Image.new("RGB", (100, 100), color="white")
    path = tmp_path / "test.png"
    img.save(path)
    return path


def test_is_supported():
    assert DocumentLoader.is_supported("test.pdf")
    assert DocumentLoader.is_supported("test.png")
    assert DocumentLoader.is_supported("test.jpg")
    assert DocumentLoader.is_supported("test.jpeg")
    assert DocumentLoader.is_supported("test.tiff")
    assert not DocumentLoader.is_supported("test.doc")
    assert not DocumentLoader.is_supported("test.txt")


def test_detect_type():
    assert DocumentLoader.detect_type("test.pdf") == "pdf"
    assert DocumentLoader.detect_type("test.png") == "image"
    assert DocumentLoader.detect_type("test.jpg") == "image"


def test_detect_type_unsupported():
    with pytest.raises(ValueError, match="Unsupported format"):
        DocumentLoader.detect_type("test.doc")


def test_load_image(loader, sample_image):
    pages = loader.load(sample_image)
    assert len(pages) == 1
    assert isinstance(pages[0], Image.Image)
    assert pages[0].size == (100, 100)


def test_load_nonexistent(loader):
    with pytest.raises(FileNotFoundError):
        loader.load("/tmp/nonexistent_file_xyz.png")


def test_load_unsupported_format(loader, tmp_path):
    path = tmp_path / "test.doc"
    path.write_text("content")
    with pytest.raises(ValueError, match="Unsupported format"):
        loader.load(path)
