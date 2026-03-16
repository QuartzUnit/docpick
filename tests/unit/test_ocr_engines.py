"""Tests for OCR engine implementations (mocked — no real OCR libraries required)."""

from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from docpick.core.result import LayoutInfo, OCRResult, TextBlock
from docpick.ocr.auto import AutoEngine, get_engine, estimate_complexity, _try_import_engine
from docpick.ocr.base import OCREngine


# === Helper: create a fake OCR engine ===

class FakeEngine(OCREngine):
    """Fake OCR engine for testing."""

    def __init__(self, engine_name: str = "fake", confidence: float = 0.9):
        self._name = engine_name
        self._confidence = confidence

    def recognize(self, image: Image.Image, languages: list[str] | None = None) -> OCRResult:
        return OCRResult(
            text="Hello World",
            blocks=[
                TextBlock(text="Hello", bbox=(0.0, 0.0, 0.5, 0.1), confidence=self._confidence),
                TextBlock(text="World", bbox=(0.5, 0.0, 1.0, 0.1), confidence=self._confidence),
            ],
            layout=LayoutInfo(page_count=1, detected_languages=languages or ["en"]),
            engine=self._name,
            processing_time_ms=10.0,
        )

    def is_available(self) -> bool:
        return True

    @property
    def name(self) -> str:
        return self._name

    @property
    def requires_gpu(self) -> bool:
        return False

    @property
    def supported_languages(self) -> list[str]:
        return ["en", "ko"]


# === OCREngine ABC ===

def test_ocr_engine_abc():
    """Cannot instantiate abstract OCREngine."""
    with pytest.raises(TypeError):
        OCREngine()


def test_ocr_engine_recognize_file():
    """recognize_file loads image and delegates to recognize."""
    engine = FakeEngine()
    # Create a small test image
    img = Image.new("RGB", (100, 50), color="white")
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        img.save(f, format="PNG")
        result = engine.recognize_file(f.name)
    assert result.text == "Hello World"
    assert result.engine == "fake"


# === get_engine factory ===

def test_get_engine_auto():
    engine = get_engine("auto")
    assert isinstance(engine, AutoEngine)


def test_get_engine_unknown():
    with pytest.raises(ValueError, match="Unknown OCR engine"):
        get_engine("nonexistent")


def test_get_engine_paddle():
    """get_engine('paddle') imports PaddleOCREngine."""
    with patch("docpick.ocr.paddle.PaddleOCREngine", FakeEngine):
        engine = get_engine("paddle")
        assert engine.name == "fake"


def test_get_engine_easyocr():
    with patch("docpick.ocr.easyocr_engine.EasyOCREngine", FakeEngine):
        engine = get_engine("easyocr")
        assert engine.name == "fake"


def test_get_engine_got():
    with patch("docpick.ocr.got.GOTOCREngine", FakeEngine):
        engine = get_engine("got")
        assert engine.name == "fake"


def test_get_engine_vlm():
    with patch("docpick.ocr.vlm.VLMOCREngine", FakeEngine):
        engine = get_engine("vlm")
        assert engine.name == "fake"


# === AutoEngine ===

def test_auto_engine_selects_tier1():
    """AutoEngine picks first available Tier 1 engine."""
    auto = AutoEngine()
    auto._tier1 = FakeEngine("paddle", confidence=0.95)
    img = Image.new("RGB", (100, 50))
    result = auto.recognize(img)
    assert result.engine == "paddle"
    assert result.text == "Hello World"


def test_auto_engine_fallback_on_low_confidence():
    """AutoEngine falls back to Tier 2 when Tier 1 confidence is low."""
    auto = AutoEngine(confidence_threshold=0.8, enable_fallback=True)
    auto._tier1 = FakeEngine("paddle", confidence=0.5)  # Low confidence
    auto._tier2 = FakeEngine("got", confidence=0.95)     # High confidence

    img = Image.new("RGB", (100, 50))
    result = auto.recognize(img)
    assert result.engine == "got"
    assert result.metadata.get("fallback_from") == "paddle"
    assert result.metadata.get("tier1_confidence") == 0.5


def test_auto_engine_no_fallback_on_high_confidence():
    """AutoEngine does NOT fall back when Tier 1 confidence is fine."""
    auto = AutoEngine(confidence_threshold=0.7, enable_fallback=True)
    auto._tier1 = FakeEngine("paddle", confidence=0.9)
    auto._tier2 = FakeEngine("got", confidence=0.95)

    img = Image.new("RGB", (100, 50))
    result = auto.recognize(img)
    assert result.engine == "paddle"


def test_auto_engine_fallback_disabled():
    """AutoEngine does NOT fall back when fallback is disabled."""
    auto = AutoEngine(confidence_threshold=0.8, enable_fallback=False)
    auto._tier1 = FakeEngine("paddle", confidence=0.5)
    auto._tier2 = FakeEngine("got", confidence=0.95)

    img = Image.new("RGB", (100, 50))
    result = auto.recognize(img)
    assert result.engine == "paddle"  # No fallback


def test_auto_engine_no_tier2_available():
    """AutoEngine gracefully handles missing Tier 2."""
    auto = AutoEngine(confidence_threshold=0.8, enable_fallback=True)
    auto._tier1 = FakeEngine("paddle", confidence=0.5)

    # Mock _try_import_engine to always return None (no Tier 2 available)
    with patch("docpick.ocr.auto._try_import_engine", return_value=None):
        img = Image.new("RGB", (100, 50))
        result = auto.recognize(img)
    assert result.engine == "paddle"  # Falls back to Tier 1 result


def test_auto_engine_is_available():
    auto = AutoEngine()
    auto._tier1 = FakeEngine()
    assert auto.is_available() is True


def test_auto_engine_not_available():
    auto = AutoEngine()
    # Don't set any engine, and mock _try_import to return None
    with patch("docpick.ocr.auto._try_import_engine", return_value=None):
        assert auto.is_available() is False


def test_auto_engine_name():
    auto = AutoEngine()
    auto._tier1 = FakeEngine("paddle")
    assert auto.name == "paddle"


def test_auto_engine_supported_languages():
    auto = AutoEngine()
    auto._tier1 = FakeEngine()
    assert "en" in auto.supported_languages
    assert "ko" in auto.supported_languages


# === _try_import_engine ===

def test_try_import_unknown_engine():
    result = _try_import_engine("nonexistent")
    assert result is None


# === estimate_complexity ===

def test_estimate_complexity_simple():
    """Small, simple image → low complexity."""
    img = Image.new("L", (500, 700), color=200)  # Grayscale, small
    score = estimate_complexity(img)
    assert score < 0.5


def test_estimate_complexity_large():
    """Large RGB image → higher complexity."""
    import numpy as np
    # Create a noisy color image (high std dev)
    arr = np.random.randint(0, 255, (2500, 2000, 3), dtype=np.uint8)
    img = Image.fromarray(arr, "RGB")
    score = estimate_complexity(img)
    assert score > 0.0  # Should detect some complexity


def test_estimate_complexity_wide_aspect():
    """Wide aspect ratio → some complexity."""
    img = Image.new("L", (3000, 500), color=200)
    score = estimate_complexity(img)
    assert score >= 0.2  # Unusual aspect ratio


# === GOTOCREngine (import check) ===

def test_got_engine_not_available():
    """GOTOCREngine reports not available when transformers not installed."""
    from docpick.ocr.got import GOTOCREngine
    engine = GOTOCREngine()
    # transformers may or may not be installed — just test the method exists
    assert isinstance(engine.is_available(), bool)


def test_got_engine_properties():
    from docpick.ocr.got import GOTOCREngine
    engine = GOTOCREngine()
    assert engine.name == "got"
    assert engine.requires_gpu is True
    assert "en" in engine.supported_languages
    assert "ko" in engine.supported_languages


# === VLMOCREngine ===

def test_vlm_engine_properties():
    from docpick.ocr.vlm import VLMOCREngine
    engine = VLMOCREngine()
    assert engine.name == "vlm"
    assert engine.requires_gpu is True
    assert "en" in engine.supported_languages
    assert "ko" in engine.supported_languages


def test_vlm_engine_not_available():
    """VLMOCREngine reports not available when endpoint is unreachable."""
    from docpick.ocr.vlm import VLMOCREngine
    engine = VLMOCREngine(base_url="http://localhost:99999/v1")
    assert engine.is_available() is False


def test_vlm_engine_recognize_mock():
    """VLMOCREngine.recognize with mocked HTTP call."""
    from docpick.ocr.vlm import VLMOCREngine
    engine = VLMOCREngine()

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Invoice No: INV-001\nDate: 2026-03-12\nTotal: $1,000"}}]
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        img = Image.new("RGB", (100, 50))
        result = engine.recognize(img, languages=["en"])

    assert "INV-001" in result.text
    assert result.engine == "vlm"
    assert len(result.blocks) == 3


def test_vlm_engine_image_to_base64():
    """Test base64 encoding of images."""
    from docpick.ocr.vlm import VLMOCREngine
    engine = VLMOCREngine()
    img = Image.new("RGB", (10, 10), color="red")
    b64 = engine._image_to_base64(img)
    assert isinstance(b64, str)
    assert len(b64) > 0

    # Verify it's valid base64
    import base64
    decoded = base64.b64decode(b64)
    assert len(decoded) > 0


# === GOTOCREngine recognize (mocked) ===

def test_got_engine_recognize_mock():
    """GOTOCREngine.recognize with mocked model."""
    from docpick.ocr.got import GOTOCREngine
    engine = GOTOCREngine()

    # Mock the model and processor
    mock_processor = MagicMock()
    mock_model = MagicMock()
    mock_model.chat.return_value = "Receipt\nItem 1: $10.00\nItem 2: $20.00\nTotal: $30.00"

    engine._model = mock_model
    engine._processor = mock_processor

    img = Image.new("RGB", (100, 50))
    result = engine.recognize(img, languages=["en"])

    assert "Receipt" in result.text
    assert result.engine == "got"
    assert len(result.blocks) == 4
    mock_model.chat.assert_called_once()


# === PaddleOCR engine properties ===

def test_paddle_engine_properties():
    from docpick.ocr.paddle import PaddleOCREngine
    engine = PaddleOCREngine()
    assert engine.name == "paddle"
    assert engine.requires_gpu is False
    assert "ko" in engine.supported_languages
    assert "en" in engine.supported_languages


# === EasyOCR engine properties ===

def test_easyocr_engine_properties():
    from docpick.ocr.easyocr_engine import EasyOCREngine
    engine = EasyOCREngine()
    assert engine.name == "easyocr"
    assert engine.requires_gpu is False
    assert "ko" in engine.supported_languages
