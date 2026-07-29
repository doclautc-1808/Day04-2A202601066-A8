from __future__ import annotations

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


def _to_anthropic_tools(tools: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    converted: list[dict[str, Any]] = []
    for item in tools or []:
        function = item.get("function", item)
        converted.append({
            "name": function["name"],
            "description": function.get("description", ""),
            "input_schema": function.get("parameters", {"type": "object", "properties": {}}),
        })
    return converted


def _split_system(messages: list[dict[str, str]]) -> tuple[str | None, list[dict[str, str]]]:
    system_parts: list[str] = []
    chat_messages: list[dict[str, str]] = []
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content", "")
        if role == "system":
            system_parts.append(content)
        elif role in {"user", "assistant"}:
            chat_messages.append({"role": role, "content": content})
    return ("\n\n".join(system_parts) if system_parts else None), chat_messages


class AnthropicProvider:
    """Anthropic Messages provider with normalized tool_calls output."""

    def __init__(
        self,
        *,
        api_key_env: str = "ANTHROPIC_API_KEY",
        default_model: str = "claude-haiku-4-5-20251001",
    ) -> None:
        self.api_key_env = api_key_env
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
            from anthropic import Anthropic
        except ImportError as exc:
            raise RuntimeError("Install live provider dependency first: pip install anthropic") from exc

        api_key = os.getenv(self.api_key_env)
        if not api_key:
            raise RuntimeError(f"Missing API key env var: {self.api_key_env}")

        system, chat_messages = _split_system(messages)
        kwargs: dict[str, Any] = {
            "model": model or self.default_model,
            "messages": chat_messages,
            "max_tokens": 1024,
            "temperature": temperature,
        }
        if system:
            kwargs["system"] = system
        anthropic_tools = _to_anthropic_tools(tools)
        if anthropic_tools:
            kwargs["tools"] = anthropic_tools
            if tool_choice == "required":
                kwargs["tool_choice"] = {"type": "any"}

        resp = Anthropic(api_key=api_key).messages.create(**kwargs)
        text_parts: list[str] = []
        calls: list[ToolCall] = []
        for block in getattr(resp, "content", []) or []:
            block_type = getattr(block, "type", None)
            if block_type == "text":
                text_parts.append(getattr(block, "text", ""))
            elif block_type == "tool_use":
                calls.append(ToolCall(name=getattr(block, "name"), args=dict(getattr(block, "input", {}) or {})))
        text = _coerce_text(text_parts) or "\n".join(part for part in text_parts if part)
        return ModelResponse(text=text or None, tool_calls=calls, raw=resp)
