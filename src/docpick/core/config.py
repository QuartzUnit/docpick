"""Docpick configuration management."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class OCRConfig(BaseSettings):
    engine: Literal["auto", "paddle", "easyocr", "got", "vlm"] = "auto"
    languages: list[str] = Field(default_factory=lambda: ["ko", "en"])
    gpu: Literal["auto", "true", "false"] = "auto"
    confidence_threshold: float = 0.7

    model_config = SettingsConfigDict(env_prefix="DOCPICK_OCR_")


class LLMConfig(BaseSettings):
    provider: Literal["vllm", "ollama", "openai"] = "vllm"
    base_url: str = "http://localhost:30000/v1"
    model: str = "Qwen/Qwen3.5-32B-AWQ"
    temperature: float = 0.0
    max_tokens: int = 4096
    timeout: int = 30

    model_config = SettingsConfigDict(env_prefix="DOCPICK_LLM_")


class VLMConfig(BaseSettings):
    enabled: bool = False
    base_url: str = "http://localhost:8081/v1"
    model: str = "Qwen/Qwen3-VL-4B"

    model_config = SettingsConfigDict(env_prefix="DOCPICK_VLM_")


class OutputConfig(BaseSettings):
    format: Literal["json", "csv", "markdown"] = "json"
    include_confidence: bool = True
    include_bbox: bool = False
    pretty_print: bool = True

    model_config = SettingsConfigDict(env_prefix="DOCPICK_OUTPUT_")


class ValidationConfig(BaseSettings):
    enabled: bool = True
    strict: bool = False

    model_config = SettingsConfigDict(env_prefix="DOCPICK_VALIDATION_")


CONFIG_DIR = Path.home() / ".docpick"
CONFIG_FILE = CONFIG_DIR / "config.yaml"


class DocpickConfig(BaseSettings):
    ocr: OCRConfig = Field(default_factory=OCRConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    vlm: VLMConfig = Field(default_factory=VLMConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    validation: ValidationConfig = Field(default_factory=ValidationConfig)

    model_config = SettingsConfigDict(env_prefix="DOCPICK_")

    @classmethod
    def load(cls, config_path: Path | None = None) -> DocpickConfig:
        """Load config from yaml file, then override with env vars."""
        path = config_path or CONFIG_FILE
        if path.exists():
            with open(path) as f:
                data = yaml.safe_load(f) or {}
            return cls(**data)
        return cls()

    def save(self, config_path: Path | None = None) -> None:
        """Save current config to yaml file."""
        path = config_path or CONFIG_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            yaml.dump(self.model_dump(), f, default_flow_style=False, allow_unicode=True)
