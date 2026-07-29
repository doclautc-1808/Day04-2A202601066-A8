from __future__ import annotations

import asyncio
import json
import os
import threading
import time
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from chat import ARTIFACTS_DIR, run_model_tool_loop, trim_history
from env_loader import load_lab_env
from providers import make_provider
from tools import load_tool_declarations, to_openai_tools


ROOT = Path(__file__).resolve().parent
load_lab_env(ROOT)

WEB_SYSTEM_APPENDIX = """
Bạn đang trả lời trong giao diện Research Scout.
Luôn trả lời bằng tiếng Việt, rõ ràng và có cấu trúc dễ đọc.
Khi tool cung cấp URL hoặc nguồn, hãy dẫn nguồn ngay cạnh luận điểm tương ứng.
Không bịa tên paper, số liệu, trích dẫn hoặc kết quả tool.
Nếu bằng chứng chưa đủ, nói rõ giới hạn thay vì suy đoán.
""".strip()


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=12_000)
    session_id: str | None = Field(default=None, max_length=128)


class SessionStore:
    def __init__(self) -> None:
        self._histories: dict[str, list[dict[str, str]]] = {}
        self._lock = threading.Lock()

    def get(self, session_id: str, window: int) -> list[dict[str, str]]:
        with self._lock:
            return trim_history(list(self._histories.get(session_id, [])), window)

    def append(self, session_id: str, user_text: str, assistant_text: str) -> None:
        with self._lock:
            history = self._histories.setdefault(session_id, [])
            history.extend(
                [
                    {"role": "user", "content": user_text},
                    {"role": "assistant", "content": assistant_text},
                ]
            )
            if len(history) > 40:
                del history[:-40]


session_store = SessionStore()
app = FastAPI(
    title="Research Scout API",
    description="HTTP/SSE adapter for the existing research agent.",
    version="1.0.0",
)


def get_runtime_config() -> dict[str, Any]:
    provider_name = os.getenv("RESEARCH_SCOUT_PROVIDER", "openrouter").strip().lower()
    return {
        "provider": provider_name,
        "model": os.getenv("RESEARCH_SCOUT_MODEL") or None,
        "history_window": max(0, int(os.getenv("RESEARCH_SCOUT_HISTORY_WINDOW", "5"))),
        "max_tool_rounds": max(1, int(os.getenv("RESEARCH_SCOUT_MAX_TOOL_ROUNDS", "4"))),
    }


def load_agent_assets() -> tuple[str, list[dict[str, Any]]]:
    system_prompt_path = Path(
        os.getenv("RESEARCH_SCOUT_SYSTEM_PROMPT", ARTIFACTS_DIR / "system_prompt.md")
    )
    tools_path = Path(os.getenv("RESEARCH_SCOUT_TOOLS", ARTIFACTS_DIR / "tools.yaml"))
    system_prompt = system_prompt_path.read_text(encoding="utf-8")
    declarations = load_tool_declarations(tools_path)
    return f"{system_prompt}\n\n{WEB_SYSTEM_APPENDIX}", to_openai_tools(declarations)


def sse_message(event_name: str, payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, default=str)
    return f"event: {event_name}\ndata: {encoded}\n\n"


def public_runtime_config() -> dict[str, Any]:
    config = get_runtime_config()
    provider = make_provider(config["provider"])
    return {
        "provider": config["provider"],
        "model": config["model"] or getattr(provider, "default_model", None),
        "history_window": config["history_window"],
        "max_tool_rounds": config["max_tool_rounds"],
    }


@app.get("/api/health")
def health() -> dict[str, Any]:
    config = public_runtime_config()
    provider = make_provider(config["provider"])
    api_key_env = getattr(provider, "api_key_env", None)
    return {
        "status": "ok",
        **config,
        "provider_configured": bool(api_key_env and os.getenv(api_key_env)),
    }


@app.get("/api/config")
def config() -> dict[str, Any]:
    return public_runtime_config()


@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    user_text = request.message.strip()
    if not user_text:
        raise HTTPException(status_code=422, detail="Câu hỏi không được để trống.")

    runtime = get_runtime_config()
    try:
        system_prompt, tools = load_agent_assets()
        provider = make_provider(runtime["provider"])
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    session_id = request.session_id or f"session_{uuid.uuid4().hex[:12]}"
    run_id = f"run_{uuid.uuid4().hex[:10]}"
    history = session_store.get(session_id, runtime["history_window"])
    messages = [
        {"role": "system", "content": system_prompt},
        *history,
        {"role": "user", "content": user_text},
    ]

    async def event_stream() -> AsyncIterator[str]:
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[tuple[str, dict[str, Any]] | None] = asyncio.Queue()
        started_at = time.perf_counter()

        def on_agent_event(event_name: str, payload: dict[str, Any]) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, (event_name, payload))

        def run_agent() -> None:
            try:
                result = run_model_tool_loop(
                    provider=provider,
                    messages=messages,
                    tools=tools,
                    model=runtime["model"],
                    max_tool_rounds=runtime["max_tool_rounds"],
                    event_handler=on_agent_event,
                )
                assistant_text = result.get("assistant_text") or ""
                duration_ms = round((time.perf_counter() - started_at) * 1000)
                tool_events = result.get("tool_events", [])
                session_store.append(session_id, user_text, assistant_text)

                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    (
                        "answer_started",
                        {
                            "run_id": run_id,
                            "character_count": len(assistant_text),
                        },
                    ),
                )
                for offset in range(0, len(assistant_text), 12):
                    loop.call_soon_threadsafe(
                        queue.put_nowait,
                        (
                            "token",
                            {
                                "text": assistant_text[offset : offset + 12],
                            },
                        ),
                    )
                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    (
                        "run_completed",
                        {
                            "run_id": run_id,
                            "session_id": session_id,
                            "status": result.get("status", "answered"),
                            "assistant_text": assistant_text,
                            "rounds": result.get("rounds", []),
                            "tool_events": tool_events,
                            "metrics": {
                                "duration_ms": duration_ms,
                                "tool_calls": len(tool_events),
                                "rounds": len(result.get("rounds", [])),
                            },
                        },
                    ),
                )
            except Exception as exc:
                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    (
                        "run_failed",
                        {
                            "run_id": run_id,
                            "error": type(exc).__name__,
                            "message": str(exc),
                        },
                    ),
                )
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        worker = asyncio.create_task(asyncio.to_thread(run_agent))
        yield sse_message(
            "run_started",
            {
                "run_id": run_id,
                "session_id": session_id,
                "provider": runtime["provider"],
                "model": runtime["model"] or getattr(provider, "default_model", None),
            },
        )

        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                event_name, payload = item
                yield sse_message(event_name, payload)
        finally:
            await worker

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.get("/")
def frontend() -> FileResponse:
    return FileResponse(ROOT / "index.html")


@app.get("/styles.css")
def frontend_styles() -> FileResponse:
    return FileResponse(ROOT / "styles.css", media_type="text/css")


@app.get("/app.js")
def frontend_script() -> FileResponse:
    return FileResponse(ROOT / "app.js", media_type="application/javascript")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "web_server:app",
        host=os.getenv("RESEARCH_SCOUT_HOST", "127.0.0.1"),
        port=int(os.getenv("RESEARCH_SCOUT_PORT", "8000")),
        reload=os.getenv("RESEARCH_SCOUT_RELOAD", "0") == "1",
    )
