from __future__ import annotations

import json
import os
import unittest
from collections.abc import Callable
from unittest.mock import patch

from fastapi.testclient import TestClient

import chat
import web_server
from providers.base import ModelResponse, ToolCall


class SequenceProvider:
    default_model = "test-model"

    def __init__(self, responses: list[ModelResponse]) -> None:
        self.responses = list(responses)

    def complete(self, *_args, **_kwargs) -> ModelResponse:
        return self.responses.pop(0)


class AgentEventTests(unittest.TestCase):
    def test_model_tool_loop_emits_observable_events(self) -> None:
        provider = SequenceProvider(
            [
                ModelResponse(tool_calls=[ToolCall(name="papers", args={"query": "biomedical RAG"})]),
                ModelResponse(text="Kết quả đã được tổng hợp."),
            ]
        )
        observed: list[tuple[str, dict]] = []

        with patch.object(
            chat,
            "execute_tool_call",
            return_value={
                "tool": "papers",
                "args": {"query": "biomedical RAG"},
                "result": {"items": [{"title": "Paper", "url": "https://example.test/paper"}]},
            },
        ):
            result = chat.run_model_tool_loop(
                provider=provider,
                messages=[{"role": "user", "content": "Tìm paper"}],
                tools=[],
                model=None,
                max_tool_rounds=3,
                event_handler=lambda name, payload: observed.append((name, payload)),
            )

        event_names = [name for name, _payload in observed]
        self.assertEqual(result["status"], "answered")
        self.assertEqual(result["assistant_text"], "Kết quả đã được tổng hợp.")
        self.assertEqual(event_names.count("round_started"), 2)
        self.assertIn("tool_started", event_names)
        self.assertIn("tool_completed", event_names)
        tool_completed = next(payload for name, payload in observed if name == "tool_completed")
        self.assertEqual(tool_completed["status"], "ok")
        self.assertEqual(tool_completed["name"], "papers")


class WebApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(web_server.app)

    @staticmethod
    def fake_loop(
        *,
        event_handler: Callable[[str, dict], None],
        **_kwargs,
    ) -> dict:
        event_handler("round_started", {"round": 1})
        event_handler(
            "model_completed",
            {"round": 1, "duration_ms": 12, "has_text": False, "tool_call_count": 1},
        )
        event_handler(
            "tool_started",
            {
                "round": 1,
                "call_index": 1,
                "name": "papers",
                "args": {"query": "RAG y sinh"},
            },
        )
        tool_event = {
            "round": 1,
            "call_index": 1,
            "name": "papers",
            "args": {"query": "RAG y sinh"},
            "result": {
                "items": [
                    {
                        "title": "Biomedical RAG",
                        "url": "https://example.test/biomedical-rag",
                        "summary": "A test source.",
                    }
                ]
            },
            "status": "ok",
            "duration_ms": 8,
        }
        event_handler("tool_completed", tool_event)
        event_handler("round_started", {"round": 2})
        event_handler(
            "model_completed",
            {"round": 2, "duration_ms": 10, "has_text": True, "tool_call_count": 0},
        )
        return {
            "status": "answered",
            "assistant_text": "RAG phù hợp với tri thức cần cập nhật [1].",
            "rounds": [
                {
                    "round": 1,
                    "assistant_text": None,
                    "tool_calls": [{"name": "papers", "args": {"query": "RAG y sinh"}}],
                    "tool_results": [
                        {
                            "tool": "papers",
                            "args": {"query": "RAG y sinh"},
                            "result": tool_event["result"],
                        }
                    ],
                },
                {
                    "round": 2,
                    "assistant_text": "RAG phù hợp với tri thức cần cập nhật [1].",
                    "tool_calls": [],
                    "tool_results": [],
                },
            ],
            "tool_events": [
                {
                    "tool": "papers",
                    "args": {"query": "RAG y sinh"},
                    "result": tool_event["result"],
                }
            ],
        }

    def test_frontend_is_served_from_backend(self) -> None:
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Research Scout", response.text)

    def test_stream_endpoint_returns_trace_and_answer_events(self) -> None:
        class StubProvider:
            default_model = "test-model"
            api_key_env = "TEST_PROVIDER_KEY"

        with (
            patch.object(web_server, "make_provider", return_value=StubProvider()),
            patch.object(web_server, "load_agent_assets", return_value=("system", [])),
            patch.object(web_server, "run_model_tool_loop", side_effect=self.fake_loop),
        ):
            response = self.client.post(
                "/api/chat/stream",
                json={"message": "So sánh RAG và fine-tuning", "session_id": "session_test"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"].split(";")[0], "text/event-stream")
        self.assertIn("event: run_started", response.text)
        self.assertIn("event: tool_started", response.text)
        self.assertIn("event: tool_completed", response.text)
        self.assertIn("event: answer_started", response.text)
        self.assertIn("event: token", response.text)
        self.assertIn("event: run_completed", response.text)

        completed_frame = next(
            frame for frame in response.text.split("\n\n") if frame.startswith("event: run_completed")
        )
        data_line = next(line for line in completed_frame.splitlines() if line.startswith("data: "))
        payload = json.loads(data_line.removeprefix("data: "))
        self.assertEqual(payload["status"], "answered")
        self.assertEqual(payload["metrics"]["tool_calls"], 1)
        self.assertEqual(payload["metrics"]["rounds"], 2)

    def test_empty_message_is_rejected(self) -> None:
        response = self.client.post("/api/chat/stream", json={"message": ""})
        self.assertEqual(response.status_code, 422)

    def test_health_reports_provider_configuration(self) -> None:
        class StubProvider:
            default_model = "test-model"
            api_key_env = "TEST_PROVIDER_KEY"

        with (
            patch.dict(os.environ, {"TEST_PROVIDER_KEY": "configured"}, clear=False),
            patch.object(web_server, "make_provider", return_value=StubProvider()),
        ):
            response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["provider_configured"])


if __name__ == "__main__":
    unittest.main()
