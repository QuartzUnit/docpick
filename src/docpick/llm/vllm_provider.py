"""vLLM provider — OpenAI-compatible local LLM."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx
from pydantic import BaseModel

from docpick.llm.base import LLMProvider
from docpick.llm.prompt import build_extraction_prompt, build_retry_messages, build_vlm_extraction_prompt, parse_llm_json

logger = logging.getLogger(__name__)


class VLLMProvider(LLMProvider):
    """vLLM provider using OpenAI-compatible API."""

    def __init__(
        self,
        base_url: str = "http://localhost:30000/v1",
        model: str = "Qwen/Qwen3.5-32B-AWQ",
        temperature: float = 0.0,
        max_tokens: int = 4096,
        timeout: int = 30,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout

    def _call_chat(self, messages: list[dict[str, Any]]) -> str:
        """Call the chat completion API."""
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "chat_template_kwargs": {"enable_thinking": False},
        }

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(f"{self.base_url}/chat/completions", json=payload)
            resp.raise_for_status()
            data = resp.json()

        return data["choices"][0]["message"]["content"]

    def extract_fields(
        self,
        text: str,
        schema: type[BaseModel],
        context: dict[str, Any] | None = None,
        max_retries: int = 1,
    ) -> dict[str, Any]:
        messages = build_extraction_prompt(text, schema, context)
        for attempt in range(max_retries + 1):
            response = self._call_chat(messages)
            try:
                return parse_llm_json(response)
            except json.JSONDecodeError:
                if attempt < max_retries:
                    logger.warning("JSON parse failed, retrying with correction prompt (attempt %d)", attempt + 1)
                    messages.extend(build_retry_messages(response))
                    continue
                raise

    def extract_from_image(
        self,
        image_base64: str,
        schema: type[BaseModel],
        max_retries: int = 1,
    ) -> dict[str, Any]:
        messages = build_vlm_extraction_prompt(schema)
        messages[-1] = {
            "role": "user",
            "content": [
                {"type": "text", "text": messages[-1]["content"]},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{image_base64}"},
                },
            ],
        }
        for attempt in range(max_retries + 1):
            response = self._call_chat(messages)
            try:
                return parse_llm_json(response)
            except json.JSONDecodeError:
                if attempt < max_retries:
                    logger.warning("VLM JSON parse failed, retrying (attempt %d)", attempt + 1)
                    messages.extend(build_retry_messages(response))
                    continue
                raise

    def is_available(self) -> bool:
        try:
            with httpx.Client(timeout=5) as client:
                resp = client.get(f"{self.base_url}/models")
                return resp.status_code == 200
        except Exception:
            return False

    @property
    def name(self) -> str:
        return "vllm"


class OllamaProvider(LLMProvider):
    """Ollama provider using OpenAI-compatible API."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "qwen3.5:7b",
        temperature: float = 0.0,
        max_tokens: int = 4096,
        timeout: int = 60,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout

    def _call_chat(self, messages: list[dict[str, Any]]) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
            },
            "stream": False,
        }

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(f"{self.base_url}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()

        return data["message"]["content"]

    def extract_fields(
        self,
        text: str,
        schema: type[BaseModel],
        context: dict[str, Any] | None = None,
        max_retries: int = 1,
    ) -> dict[str, Any]:
        messages = build_extraction_prompt(text, schema, context)
        for attempt in range(max_retries + 1):
            response = self._call_chat(messages)
            try:
                return parse_llm_json(response)
            except json.JSONDecodeError:
                if attempt < max_retries:
                    logger.warning("JSON parse failed, retrying with correction prompt (attempt %d)", attempt + 1)
                    messages.extend(build_retry_messages(response))
                    continue
                raise

    def extract_from_image(
        self,
        image_base64: str,
        schema: type[BaseModel],
        max_retries: int = 1,
    ) -> dict[str, Any]:
        messages = build_vlm_extraction_prompt(schema)
        messages[-1] = {
            "role": "user",
            "content": messages[-1]["content"],
            "images": [image_base64],
        }
        for attempt in range(max_retries + 1):
            response = self._call_chat(messages)
            try:
                return parse_llm_json(response)
            except json.JSONDecodeError:
                if attempt < max_retries:
                    logger.warning("VLM JSON parse failed, retrying (attempt %d)", attempt + 1)
                    messages.extend(build_retry_messages(response))
                    continue
                raise

    def is_available(self) -> bool:
        try:
            with httpx.Client(timeout=5) as client:
                resp = client.get(f"{self.base_url}/api/tags")
                return resp.status_code == 200
        except Exception:
            return False

    @property
    def name(self) -> str:
        return "ollama"


def get_provider(
    provider_name: str = "vllm",
    **kwargs,
) -> LLMProvider:
    """Get an LLM provider by name."""
    if provider_name == "vllm":
        return VLLMProvider(**kwargs)
    if provider_name == "ollama":
        return OllamaProvider(**kwargs)
    raise ValueError(f"Unknown LLM provider: {provider_name}. Available: vllm, ollama")
