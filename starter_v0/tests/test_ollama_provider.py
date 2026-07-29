from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import patch

from providers.ollama_provider import OllamaProvider


class FakeMessage:
    def __init__(self, content):
        self.content = content
        self.tool_calls = []


class FakeChoice:
    def __init__(self, content):
        self.message = FakeMessage(content)


class FakeResponse:
    def __init__(self, content):
        self.choices = [FakeChoice(content)]


class FakeOpenAIClient:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        return FakeResponse([
            {"type": "text", "text": "Đây là"},
            {"type": "text", "text": "câu trả lời cuối"},
        ])


class OllamaProviderTests(unittest.TestCase):
    def test_extracts_text_from_structured_content_parts(self) -> None:
        fake_openai_module = types.SimpleNamespace(OpenAI=FakeOpenAIClient)
        with patch.dict(sys.modules, {"openai": fake_openai_module}):
            provider = OllamaProvider(base_url="http://example.test", default_model="test-model")
            response = provider.complete(messages=[{"role": "user", "content": "Hello"}], tools=None)

        self.assertEqual(response.text, "Đây là\ncâu trả lời cuối")


if __name__ == "__main__":
    unittest.main()
