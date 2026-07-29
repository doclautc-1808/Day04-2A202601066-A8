# Research Scout

Giao diện web tĩnh mô phỏng trợ lý nghiên cứu và log traces.

## Chạy frontend + backend

Từ thư mục dự án:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Điền API key của provider đã chọn trong .env
python web_server.py
```

Sau đó mở `http://127.0.0.1:8000`.

Mặc định backend dùng OpenRouter. Có thể đổi provider/model bằng:

```dotenv
RESEARCH_SCOUT_PROVIDER=openrouter
RESEARCH_SCOUT_MODEL=openai/gpt-4o-mini
```

Frontend gọi `POST /api/chat/stream` và nhận SSE theo thời gian thực. Các vòng
agent, tool arguments, tool results và câu trả lời trong drawer đều đến từ
`run_model_tool_loop()`; API key không được gửi xuống trình duyệt.
