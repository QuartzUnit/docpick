"""Schema-to-prompt conversion for LLM extraction."""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel


SYSTEM_PROMPT = """You are a document data extraction assistant.
Your task is to extract structured data from OCR text according to the provided JSON schema.

Rules:
1. Output ONLY valid JSON. No explanations, no markdown code blocks.
2. If a field is not found in the text, use null.
3. For numeric fields, extract the number only (no currency symbols or units).
4. For date fields, use ISO 8601 format (YYYY-MM-DD) when possible.
5. For arrays, include all matching items found.
6. Be precise — extract exactly what is in the document, do not infer or guess."""


def build_extraction_prompt(
    text: str,
    schema: type[BaseModel],
    context: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    """Build chat messages for LLM extraction.

    Returns:
        List of message dicts with 'role' and 'content' keys.
    """
    schema_json = json.dumps(schema.model_json_schema(), indent=2, ensure_ascii=False)

    user_parts = [
        "## JSON Schema",
        f"```json\n{schema_json}\n```",
        "",
        "## Document Text",
        text,
    ]

    if context:
        if context.get("tables"):
            user_parts.extend(["", "## Detected Tables", str(context["tables"])])
        if context.get("language"):
            user_parts.extend(["", f"## Document Language: {context['language']}"])
        if context.get("low_confidence"):
            user_parts.extend([
                "",
                "## Low Confidence Regions (may need correction)",
                str(context["low_confidence"]),
            ])

    user_parts.extend(["", "Extract the data and output valid JSON:"])

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "\n".join(user_parts)},
    ]


def build_vlm_extraction_prompt(
    schema: type[BaseModel],
) -> list[dict[str, Any]]:
    """Build chat messages for VLM direct image extraction.

    Returns:
        List of message dicts. Image content should be appended by the caller.
    """
    schema_json = json.dumps(schema.model_json_schema(), indent=2, ensure_ascii=False)

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Look at the document image and extract structured data.\n\n"
                f"## JSON Schema\n```json\n{schema_json}\n```\n\n"
                "Extract the data and output valid JSON:"
            ),
        },
    ]


def parse_llm_json(response: str) -> dict[str, Any]:
    """Parse JSON from LLM response, handling common formatting issues."""
    text = response.strip()

    # Strip markdown code blocks
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```json or ```)
        lines = lines[1:]
        # Remove last line (```)
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)

    # Strip leading/trailing whitespace
    text = text.strip()

    # Strategy 1: Direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strategy 2: Find JSON object boundaries
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass

    # Strategy 3: Fix trailing commas (common LLM mistake)
    cleaned = re.sub(r",\s*([}\]])", r"\1", text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Strategy 4: Extract + clean
    if start >= 0 and end > start:
        portion = text[start:end]
        cleaned = re.sub(r",\s*([}\]])", r"\1", portion)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

    raise json.JSONDecodeError("Failed to parse JSON from LLM response", text, 0)


RETRY_MESSAGE = "Your response was not valid JSON. Please output ONLY a valid JSON object with no explanations or markdown formatting."


def build_retry_messages(failed_response: str) -> list[dict[str, str]]:
    """Build messages to append for retrying failed JSON extraction."""
    return [
        {"role": "assistant", "content": failed_response},
        {"role": "user", "content": RETRY_MESSAGE},
    ]
