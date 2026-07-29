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


class OpenAIProvider:
    """OpenAI Chat Completions provider with normalized tool_calls output."""

    def __init__(
        self,
        *,
        api_key_env: str = "OPENAI_API_KEY",
        base_url: str | None = None,
        default_model: str = "gpt-4o-mini",
    ) -> None:
        self.api_key_env = api_key_env
        self.base_url = base_url
        self.default_model = default_model

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
            raise RuntimeError("Install live provider dependency first: pip install openai") from exc

        api_key = os.getenv(self.api_key_env)
        if not api_key:
            raise RuntimeError(f"Missing API key env var: {self.api_key_env}")

        client = OpenAI(api_key=api_key, base_url=self.base_url)
        kwargs: dict[str, Any] = {
            "model": model or self.default_model,
            "messages": messages,
            "temperature": temperature,
        }
        if tools:
            kwargs["tools"] = tools
        if tool_choice is not None:
            kwargs["tool_choice"] = tool_choice

        resp = client.chat.completions.create(**kwargs)
        msg = resp.choices[0].message
        calls: list[ToolCall] = []
        for call in getattr(msg, "tool_calls", None) or []:
            args = json.loads(call.function.arguments or "{}")
            calls.append(ToolCall(name=call.function.name, args=args))
        return ModelResponse(text=_coerce_text(getattr(msg, "content", None)), tool_calls=calls, raw=resp)
