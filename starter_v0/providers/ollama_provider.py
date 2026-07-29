from __future__ import annotations

import json
import os
from typing import Any

from providers.base import ModelResponse, ToolCall


def _coerce_text(content: Any) -> str | None:
    if content is None:
        return None
    if isinstance(content, str):
        return content
    if isinstance(content, (list, tuple)):
        parts: list[str] = []
        for item in content:
            text = _coerce_text(item)
            if text:
                parts.append(text)
        return "\n".join(part for part in parts if part) or None
    if isinstance(content, dict):
        if isinstance(content.get("text"), str):
            return content["text"]
        if "content" in content:
            return _coerce_text(content["content"])
        return None
    text = getattr(content, "text", None)
    if isinstance(text, str):
        return text
    return None


class OllamaProvider:
    """Local Ollama provider through its OpenAI-compatible API."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        default_model: str | None = None,
    ) -> None:
        self.base_url = base_url or os.getenv(
            "OLLAMA_BASE_URL",
            "http://localhost:11434/v1",
        )
        self.default_model = default_model or os.getenv(
            "OLLAMA_MODEL",
            "qwen3:8b",
        )

    def complete(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        *,
        model: str | None = None,
        temperature: float = 0.0,
        tool_choice: Any | None = None,
    ) -> ModelResponse:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                "Install the OpenAI SDK first: pip install openai"
            ) from exc

        client = OpenAI(
            base_url=self.base_url,
            # The SDK requires a non-empty value, but local Ollama does not
            # authenticate this OpenAI-compatible endpoint.
            api_key="ollama",
        )
        kwargs: dict[str, Any] = {
            "model": model or self.default_model,
            "messages": messages,
            "temperature": temperature,
        }
        if tools:
            kwargs["tools"] = tools
        if tool_choice is not None:
            kwargs["tool_choice"] = tool_choice

        response = client.chat.completions.create(**kwargs)
        message = response.choices[0].message
        calls: list[ToolCall] = []
        for call in message.tool_calls or []:
            try:
                args = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    f"Ollama returned invalid tool arguments for {call.function.name}: "
                    f"{call.function.arguments!r}"
                ) from exc
            calls.append(ToolCall(name=call.function.name, args=args))

        return ModelResponse(text=_coerce_text(getattr(message, "content", None)), tool_calls=calls, raw=response)
