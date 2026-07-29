from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from env_loader import load_lab_env
from providers import make_provider
from tools import load_tool_declarations, to_openai_tools
from versioning import artifact_version_dict, build_artifact_version

try:
    import streamlit as st
except Exception:  # pragma: no cover - streamlit may be unavailable in some environments
    st = None

from chat import ARTIFACTS_DIR, run_model_tool_loop, write_transcript


ROOT = Path(__file__).resolve().parent
load_lab_env(ROOT)

DEFAULT_SCENARIO = (
    "So sánh RAG và fine-tuning cho hỏi đáp y sinh dựa trên các nghiên cứu 2024–2025. "
    "Ưu tiên kết quả định lượng, chi phí và độ tin cậy của trích dẫn."
)
DEFAULT_VERSIONS = ["v0", "v1", "v2", "v3"]


def _has_api_key(env_var: str) -> bool:
    return bool((os.getenv(env_var) or "").strip())


def _resolve_runtime_provider(requested_provider: str, requested_model: str | None = None) -> tuple[Any, str, str | None]:
    if requested_provider == "ollama":
        provider = make_provider("ollama")
        return provider, "ollama", requested_model or os.getenv("OLLAMA_MODEL") or getattr(provider, "default_model", None)

    provider_key_map = {
        "openai": "OPENAI_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "gemini": "GEMINI_API_KEY",
    }

    if requested_provider in provider_key_map:
        if _has_api_key(provider_key_map[requested_provider]):
            provider = make_provider(requested_provider)
            return provider, requested_provider, requested_model

        fallback_provider = make_provider("ollama")
        fallback_model = requested_model or os.getenv("OLLAMA_MODEL") or getattr(fallback_provider, "default_model", None)
        return fallback_provider, "ollama", fallback_model

    provider = make_provider(requested_provider)
    return provider, requested_provider, requested_model


def _resolve_path(path_value: str | os.PathLike[str] | Path, *, base_dir: Path | None = None) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    if base_dir is not None:
        return base_dir / path
    return ROOT / path


def _safe_provider_name(provider: Any) -> str:
    name = getattr(provider, "name", None) or getattr(provider, "provider_name", None)
    if name:
        return str(name)
    return provider.__class__.__name__ if hasattr(provider, "__class__") else "provider"


def run_scenario(
    *,
    provider: Any,
    request_text: str,
    version: str,
    system_prompt_path: str | os.PathLike[str] | Path,
    tools_path: str | os.PathLike[str] | Path,
    transcripts_dir: str | os.PathLike[str] | Path,
    history_window: int = 5,
    max_tool_rounds: int = 4,
    model: str | None = None,
) -> dict[str, Any]:
    request_text = request_text.strip()
    if not request_text:
        raise ValueError("Request không được để trống.")

    resolved_prompt_path = _resolve_path(system_prompt_path, base_dir=ROOT)
    resolved_tools_path = _resolve_path(tools_path, base_dir=ROOT)
    resolved_transcripts_dir = _resolve_path(transcripts_dir, base_dir=ROOT)
    resolved_transcripts_dir.mkdir(parents=True, exist_ok=True)

    system_prompt = resolved_prompt_path.read_text(encoding="utf-8")
    tool_declarations = load_tool_declarations(resolved_tools_path)
    openai_tools = to_openai_tools(tool_declarations)
    artifact_version = build_artifact_version(version, resolved_prompt_path, resolved_tools_path)

    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S%f")
    transcript_id = "_".join([version.replace(".", "_"), _safe_provider_name(provider).replace(".", "_"), timestamp])
    transcript_path = resolved_transcripts_dir / f"{transcript_id}.transcript.json"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": request_text},
    ]
    result = run_model_tool_loop(
        provider=provider,
        messages=messages,
        tools=openai_tools,
        model=model,
        max_tool_rounds=max_tool_rounds,
    )

    transcript: dict[str, Any] = {
        "transcript_id": transcript_id,
        **artifact_version_dict(artifact_version),
        "provider": _safe_provider_name(provider),
        "model": model or getattr(provider, "default_model", None),
        "system_prompt": str(resolved_prompt_path),
        "tools": str(resolved_tools_path),
        "history_window": history_window,
        "max_tool_rounds": max_tool_rounds,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "request": request_text,
        "status": result.get("status", "answered"),
        "assistant_text": result.get("assistant_text", ""),
        "rounds": result.get("rounds", []),
        "tool_events": result.get("tool_events", []),
    }
    write_transcript(transcript_path, transcript)

    summary = {
        "version": version,
        "artifact_version": artifact_version.artifact_version,
        "status": result.get("status", "answered"),
        "tool_call_count": sum(len(round_data.get("tool_calls", [])) for round_data in result.get("rounds", [])),
        "round_count": len(result.get("rounds", [])),
        "response_preview": (result.get("assistant_text") or "").strip()[:220],
    }

    return {
        "request": request_text,
        "response": result.get("assistant_text", ""),
        "artifact_version": artifact_version.artifact_version,
        "transcript_path": str(transcript_path),
        "transcript": transcript,
        "summary": summary,
        "result": result,
    }


def _render_results(results: list[dict[str, Any]]) -> None:
    if st is None:
        for item in results:
            print(f"Version: {item['summary']['version']}")
            print(f"Artifact: {item['artifact_version']}")
            print(f"Request: {item['request']}")
            print(f"Response: {item['response']}")
            print(f"Transcript: {item['transcript_path']}")
            print("-" * 80)
        return

    st.subheader("Kết quả chạy")
    for payload in results:
        with st.expander(
            f"{payload['summary']['version']} · {payload['artifact_version']} · {payload['summary']['status']}",
            expanded=True,
        ):
            st.markdown("**Request**")
            st.write(payload["request"])
            st.markdown("**Final response**")
            st.write(payload["response"])
            st.markdown("**Artifact version / transcript**")
            st.write(payload["artifact_version"])
            st.write(payload["transcript_path"])
            st.markdown("**Summary**")
            st.write(payload["summary"])

            for round_data in payload["result"].get("rounds", []):
                round_title = f"Round {round_data.get('round', '?')}"
                with st.expander(round_title, expanded=False):
                    st.write("Assistant text:")
                    st.write(round_data.get("assistant_text") or "")
                    for tool_call in round_data.get("tool_calls", []):
                        st.write(f"Tool: {tool_call.get('name')}\nArgs: {json.dumps(tool_call.get('args', {}), ensure_ascii=False, indent=2)}")
                    for tool_result in round_data.get("tool_results", []):
                        status = "ok" if not isinstance(tool_result.get("result", {}), dict) or not tool_result.get("result", {}).get("error") else "error"
                        st.write(f"Status: {status}")
                        st.code(json.dumps(tool_result, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a research agent scenario and render a trace-rich UI.")
    parser.add_argument("--request", default=DEFAULT_SCENARIO)
    parser.add_argument("--version", default="v0")
    parser.add_argument("--versions", nargs="*", default=DEFAULT_VERSIONS)
    parser.add_argument("--provider", default=os.getenv("RESEARCH_SCOUT_PROVIDER", "openrouter"))
    parser.add_argument("--model", default=os.getenv("RESEARCH_SCOUT_MODEL") or None)
    parser.add_argument("--system-prompt", default=str(ARTIFACTS_DIR / "system_prompt.md"))
    parser.add_argument("--tools", default=str(ARTIFACTS_DIR / "tools.yaml"))
    parser.add_argument("--transcripts-dir", default=str(ROOT / "transcripts"))
    parser.add_argument("--max-tool-rounds", type=int, default=4)
    args = parser.parse_args()

    provider, runtime_provider_name, resolved_model = _resolve_runtime_provider(args.provider, args.model)
    if runtime_provider_name != args.provider:
        print(f"[app.py] Không tìm thấy API key cho {args.provider}; chuyển sang Ollama local ({resolved_model})")

    if st is None:
        payload = run_scenario(
            provider=provider,
            request_text=args.request,
            version=args.version,
            system_prompt_path=args.system_prompt,
            tools_path=args.tools,
            transcripts_dir=args.transcripts_dir,
            max_tool_rounds=args.max_tool_rounds,
            model=resolved_model,
        )
        print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
        return

    st.set_page_config(page_title="Research Scout App", page_icon="🔎", layout="wide")
    st.title("Research Scout — trace-driven comparison")
    st.caption("Một scenario duy nhất chạy qua nhiều version để thấy cải thiện rõ ràng hơn.")

    request_text = st.text_area("Request", value=args.request, height=160)
    selected_versions = st.multiselect("Chọn các version để so sánh", DEFAULT_VERSIONS, default=args.versions[:1])
    if st.button("Chạy scenario"):
        provider, runtime_provider_name, resolved_model = _resolve_runtime_provider(args.provider, args.model)
        if runtime_provider_name != args.provider:
            st.info(f"Không tìm thấy API key cho {args.provider}; chuyển sang Ollama local ({resolved_model})")

        results: list[dict[str, Any]] = []
        for version in selected_versions:
            results.append(
                run_scenario(
                    provider=provider,
                    request_text=request_text,
                    version=version,
                    system_prompt_path=args.system_prompt,
                    tools_path=args.tools,
                    transcripts_dir=args.transcripts_dir,
                    max_tool_rounds=args.max_tool_rounds,
                    model=resolved_model,
                )
            )
        _render_results(results)


if __name__ == "__main__":
    main()
