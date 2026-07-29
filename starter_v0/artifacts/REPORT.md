# Day 04 Lab v2 Report — Research Agent

> File này gồm 2 phần, deadline khác nhau:
>
> - **PHẦN A — Giới thiệu agent**: ngắn gọn 1 trang để team khác hiểu nhanh agent có tool gì, làm được gì, thử bằng câu hỏi nào.
> - **PHẦN B — Chi tiết / Bằng chứng**: bảng đầy đủ (v0–v3, failure, eval, chat) dựa trên log thật. Những mục chưa có dữ liệu đủ chắc chắn sẽ để trống hoặc ghi “—”.

## Team

- Team: Research Paper Scout
- Members: Đào Chí Hiển, Nguyễn Việt Anh, Nguyễn Bùi Anh Tuấn, Nguyễn Ngọc Chi, Trần Thanh Bình (Chi tiết phân công công việc trong file PHAN_CONG_CONG_VIEC.md)
- Provider/model: Ollama / qwen3.5:4b (runs v0–v3);

# PHẦN A — Giới thiệu agent

## A1. Agent này làm được gì

Agent này hỗ trợ tìm kiếm thông tin nghiên cứu và web, đọc nội dung URL/PDF, tra cứu policy nội bộ và trình bày kết quả thành digest ngắn gọn. Khi thông tin chưa đủ, agent có thể hỏi lại thay vì tự suy đoán.

**Link dùng thử (truy cập được trong showdown):**

> URL: http://127.0.0.1:8000 (local demo)

## A2. Tool agent có

| Tên tool     | Làm được gì                                                                                    | Tool mới nhóm thêm? |
| ------------- | --------------------------------------------------------------------------------------------------- | ---------------------- |
| clarify       | hỏi lại người dùng khi thiếu thông tin hoặc cần xác nhận trước hành động nhạy cảm | không                 |
| timeline      | lấy bài đăng gần đây của một tài khoản                                                   | không                 |
| social_search | tìm bài đăng theo chủ đề trên mạng xã hội                                                | không                 |
| lookup        | tìm thông tin/tin tức trên web                                                                  | không                 |
| fetch         | đọc nội dung của một URL cụ thể                                                              | không                 |
| format        | trình bày kết quả thành digest/brief                                                           | không                 |
| policy        | tra cứu chính sách nội bộ                                                                      | không                 |
| papers        | tìm paper/preprint trên arXiv                                                                     | có                    |
| paper_text    | đọc và trích text nội dung paper arXiv                                                         | có                    |

## A3. Câu hỏi mẫu để thử

1. Tìm 3 bài báo mới nhất về chủ đề RAG.
2. Đọc nội dung chi tiết của bài báo arXiv ID 2301.00001.
3. Tra cứu chính sách nội bộ về trích dẫn nguồn trong AI research.
4. Tìm bài báo về Direct Preference Optimization rồi tóm tắt phương pháp nghiên cứu.
5. Tìm bài báo về Agentic Workflow năm 2024 và định dạng thành brief.

## A4. Kịch bản demo đã rehearse

| Scenario                             | Tool trace cần thấy | Câu chuyện cải thiện version                                            | Fallback run/transcript                           |
| ------------------------------------ | --------------------- | --------------------------------------------------------------------------- | ------------------------------------------------- |
| Tìm paper về RAG                   | papers → format      | Version v2/v3 làm rõ cách gọi tool đúng tên và tham số             | runs/v2_B_group_ollama_20260729T175329168398.json |
| Đọc paper arXiv cụ thể           | paper_text            | Vấn đề sai tham số đã được giảm ở các version sau               | runs/v3_B_base_ollama_20260729T174149159851.json  |
| Cần hỏi lại khi thiếu thông tin | clarify               | Prompt mới làm rõ boundary hỏi lại trước khi dùng tool hành động | runs/v1_B_base_ollama_20260729T171944242900.json  |

---

# PHẦN B — Chi tiết / Bằng chứng

> Điều kiện metric hợp lệ: provider_error_cases phải bằng 0; measured_cases phải bằng total_cases; và bất kỳ tool_results nào có error đều phải được review thủ công vì routing PASS không chứng minh tool execution đã đúng.

## B1. Version evidence

| Version | Prompt/tool change | Hypothesis                                                                                    | Metric name           | Before | After | Run File                                         |
| ------- | ------------------ | --------------------------------------------------------------------------------------------- | --------------------- | -----: | ----: | ------------------------------------------------ |
| v0      | baseline           | Baseline dùng routing cơ bản, chưa có boundary rõ cho clarify và tool selection        | tool_routing_accuracy |     — |  0.90 | runs/v0_B_base_ollama_20260729T171200425019.json |
| v1      | system_prompt.md   | Rõ ràng hơn về boundary clarify và routing conventions sẽ cải thiện việc chọn tool  | tool_routing_accuracy |   0.90 |  0.85 | runs/v1_B_base_ollama_20260729T171944242900.json |
| v2      | tools.yaml         | Mô tả tool và argument conventions rõ hơn sẽ giảm lỗi chọn tool sai và sai tham số | tool_routing_accuracy |   0.85 |  0.90 | runs/v2_B_base_ollama_20260729T172639580436.json |
| v3      | system_prompt.md   | Quy tắc intent/correction multi-turn sẽ giúp agent bám đúng tool ở lượt sau          | tool_routing_accuracy |   0.90 |  0.85 | runs/v3_B_base_ollama_20260729T174149159851.json |

## B2. Failure analysis

| Case ID                 | Failure Type      | Actual Tool Calls | What Failed                                                                                                     | Fix                                                                                   |
| ----------------------- | ----------------- | ----------------- | --------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| R01_user_tweets_routing | wrong_arg_value   | timeline          | Sai tham số screenname: expected “sama”, nhưng agent dùng “samaltman” hoặc “@SamAltman”               | Chuẩn hóa handle đầu vào và bổ sung ví dụ rõ trong tools.yaml/system_prompt |
| R10_missing_handle      | missing_info      | timeline          | Agent bỏ qua missing info khi chưa có handle và gọi timeline thay vì clarify                              | Dùng clarify trước khi gọi timeline khi thiếu thông tin                         |
| R12_confirm_before_send | wrong_boundary    | clarify           | response_type được truyền sai (choice/text thay vì yes_no)                                                 | Rõ hơn boundary confirm-before-send trong prompt và schema clarify                 |
| G01                     | wrong_arg_value   | papers            | Query quá dài “RAG Retrieval-Augmented Generation” thay vì query chuẩn “RAG”                            | Rõ hơn convention về query ngắn gọn và tối ưu tham số                        |
| G06/G07                 | missing_tool_call | papers/clarify    | Multi-turn không giữ đúng intent từ lượt trước, dẫn đến thiếu tool cần thiết hoặc gọi tool sai | Thêm quy tắc carry-over intent và correction trong prompt                          |

## B3. Team eval cases

| Case ID | What It Tests                                                             | Expected Tool/Behavior                                 | Result                                                                                                    |
| ------- | ------------------------------------------------------------------------- | ------------------------------------------------------ | --------------------------------------------------------------------------------------------------------- |
| G01     | Single-turn: tìm 3 bài báo về RAG                                     | papers với query=RAG, max_results=3                   | Fail – sai argument: query được truyền dài hơn mong đợi (“RAG Retrieval-Augmented Generation”) |
| G02     | Single-turn: đọc nội dung chi tiết paper 2301.00001                   | paper_text với arxiv_url=2301.00001                   | Pass                                                                                                      |
| G03     | Single-turn: tóm tắt phương pháp nghiên cứu của 2301.00001        | paper_text với focus_area=methodology                 | Fail – thiếu đúng focus_area/methodology                                                              |
| G04     | Single-turn: trích xuất kết quả chính từ 2402.12345                 | paper_text với focus_area=results                     | Fail – thiếu đúng focus_area/results                                                                  |
| G05     | Single-turn: tra cứu policy về trích dẫn nguồn                       | policy với query và policy_area=source_citation      | Pass                                                                                                      |
| G06     | Multi-turn: tìm paper rồi tóm tắt phương pháp ở lượt sau        | paper_text với focus_area=methodology ở lượt cuối | Fail – thiếu tool paper_text hoặc gọi sai tool                                                        |
| G07     | Multi-turn: tìm 2 paper rồi đọc bài đầu tiên và trích kết quả | paper_text với focus_area=results ở lượt cuối     | Fail – thiếu tool paper_text                                                                            |
| G08     | Multi-turn: tìm paper rồi định dạng thành brief                     | format với template=brief                             | Pass                                                                                                      |
| G09     | Multi-turn: đọc paper rồi tóm tắt limitations                        | paper_text với focus_area=limitations                 | Fail – thiếu đúng focus_area/limitations                                                              |
| G10     | Multi-turn: người dùng không cần thêm thông tin nữa               | không gọi tool thừa                                 | Pass                                                                                                      |

## B4. Live chat evidence

| Scenario/Turn                                                              | Version | Tool Calls + Args                                                                | Transcript/Run                                              | Outcome                                                                 |
| -------------------------------------------------------------------------- | ------- | -------------------------------------------------------------------------------- | ----------------------------------------------------------- | ----------------------------------------------------------------------- |
| Turn 1: “Kiếm cho tôi bài báo liên quan đến YOLO bản mới nhất” | v3      | papers(query="YOLO object detection", max_results=10, sort_by="lastUpdatedDate") | transcripts/v3_ollama_20260729T191157033690.transcript.json | Agent đã gọi papers và trả lời bằng summary từ kết quả arXiv. |

## B5. Tool capability evidence

| Category                         | Evidence File                                          | What Worked                                                                       | Risk / Guardrail                                                        |
| -------------------------------- | ------------------------------------------------------ | --------------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| Must-have: tool mới đầu tiên | tools/papers/TOOL.md, tools/paper_text/TOOL.md         | Agent có thể tìm paper trên arXiv và đọc text nội dung paper              | Cần kiểm tra mạng/độ ổn định của arXiv và xử lý PDF parsing |
| Optional built-in                | artifacts/tools.yaml, tools/policy/tool.py             | policy và lookup hoạt động như built-in routing path cho tra cứu thông tin | Không nên dùng policy thay thế cho web search tổng quát           |
| Bonus: tool mới thứ 4 trở đi | tools/paper_rank/tool.py, tools/citation_audit/tool.py | Có thể rank và audit paper/evidence ở mức cục bộ                           | Chỉ nên dùng cho workflow nghiên cứu nâng cao, tránh overuse     |

## B6. Reflection

- Which fixes belonged in system_prompt.md? Các quy tắc về clarify boundary, intent carry-over ở multi-turn, và hướng dẫn agent chọn tool đúng khi người dùng sửa lại yêu cầu.
- Which fixes belonged in tools.yaml? Mô tả rõ tool nào dùng cho chủ đề nào, giá trị tham số như query/topic/search_type, và convention về argument ngắn gọn/đúng kiểu.
- Which failure needed manual review instead of automatic grading? Các case có tool_results lỗi hoặc provider_error (ví dụ quota exhausted) không nên chấm bằng routing PASS đơn thuần; cần review thủ công vì tool execution chưa thật sự thành công.
- What would you improve next? Cải thiện memory multi-turn, tăng độ rõ ràng cho schema tham số, và giảm phụ thuộc vào provider có quota hạn chế bằng cách chạy local/backup provider.
