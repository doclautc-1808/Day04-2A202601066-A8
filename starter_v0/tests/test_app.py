from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app


class DummyProvider:
    default_model = "test-model"


class AppScenarioTests(unittest.TestCase):
    def test_run_scenario_builds_artifact_version_and_transcript(self) -> None:
        fake_result = {
            "status": "answered",
            "assistant_text": "Kết quả đã sẵn sàng.",
            "rounds": [
                {
                    "round": 1,
                    "assistant_text": None,
                    "tool_calls": [{"name": "papers", "args": {"query": "RAG"}}],
                    "tool_results": [
                        {
                            "tool": "papers",
                            "args": {"query": "RAG"},
                            "result": {"items": [{"title": "Paper"}]},
                        }
                    ],
                }
            ],
            "tool_events": [
                {
                    "tool": "papers",
                    "args": {"query": "RAG"},
                    "result": {"items": [{"title": "Paper"}]},
                }
            ],
        }

        with (
            patch.object(app, "run_model_tool_loop", return_value=fake_result),
            patch.object(app, "load_tool_declarations", return_value=[]),
            patch.object(app, "to_openai_tools", return_value=[]),
            tempfile.TemporaryDirectory() as tmpdir,
        ):
            payload = app.run_scenario(
                provider=DummyProvider(),
                request_text="So sánh RAG và fine-tuning",
                version="v1",
                system_prompt_path=Path("artifacts/system_prompt.md"),
                tools_path=Path("artifacts/tools.yaml"),
                transcripts_dir=Path(tmpdir),
                history_window=2,
                max_tool_rounds=2,
                model=None,
            )

        self.assertEqual(payload["request"], "So sánh RAG và fine-tuning")
        self.assertEqual(payload["response"], "Kết quả đã sẵn sàng.")
        self.assertEqual(payload["artifact_version"].startswith("v1+"), True)
        self.assertEqual(payload["transcript"]["artifact_version"].startswith("v1+"), True)
        self.assertEqual(payload["summary"]["tool_call_count"], 1)
        self.assertTrue(payload["transcript_path"].endswith(".transcript.json"))


if __name__ == "__main__":
    unittest.main()
