"""Tests for DocpickConfig."""

import tempfile
from pathlib import Path

from docpick.core.config import DocpickConfig


def test_default_config():
    cfg = DocpickConfig()
    assert cfg.ocr.engine == "auto"
    assert cfg.ocr.languages == ["ko", "en"]
    assert cfg.llm.provider == "vllm"
    assert cfg.llm.temperature == 0.0
    assert cfg.validation.enabled is True


def test_config_save_load():
    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
        path = Path(f.name)

    cfg = DocpickConfig()
    cfg.ocr.engine = "paddle"
    cfg.llm.model = "test-model"
    cfg.save(path)

    loaded = DocpickConfig.load(path)
    assert loaded.ocr.engine == "paddle"
    assert loaded.llm.model == "test-model"

    path.unlink()


def test_config_nonexistent_file():
    cfg = DocpickConfig.load(Path("/tmp/nonexistent_docpick_config.yaml"))
    assert cfg.ocr.engine == "auto"
