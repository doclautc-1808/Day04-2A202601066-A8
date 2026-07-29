# 📖 SỔ TAY PHÂN CÔNG & CHECKLIST THỰC HÀNH (ZERO-CONFLICT WORKFLOW)

**Đề tài 03:** Research Paper Scout | **Repository:** `starter_v0/`

## 1. BẢNG PHÂN VAI & FILE ĐẢM NHẬN

| Vai trò (Role) | File/Folder đảm nhận | Nhiệm vụ chính | Thành viên đảm nhận |
| :--- | :--- | :--- | :--- |
| **TV1: Trưởng nhóm – tích hợp** | `.env` cục bộ, `artifacts/version_log.csv`, kiểm tra toàn project | Setup môi trường, chọn provider/model, quản lý v0–v3, tích hợp code và kiểm tra bài nộp | **Đào Chí Hiển** *(2A202601066)* |
| **TV2: Prompt & Tool Routing** | `artifacts/system_prompt.md`, `artifacts/tools.yaml` | Phân tích lỗi routing, cải tiến prompt và mô tả/schema tool qua từng version | **Nguyễn Việt Anh** *(2A202601144)* |
| **TV3: Tool Developer** | `tools/<tool_moi>/tool.py`, `tools/<tool_moi>/TOOL.md`, `tools/__init__.py` | Thiết kế và lập trình ít nhất 1 tool mới, viết tài liệu và smoke test | **Nguyễn Bùi Anh Tuấn** *(2A202601208)* |
| **TV4: Eval & Data Analyst** | `data/eval_group.json`, `runs/*.json`, `analysis/*.csv`, phần B của `REPORT.md` | Viết 10 eval case, chạy eval, đọc log, lập bảng metric và failure analysis | **Nguyễn Ngọc Chi** *(2A202602024)* |
| **TV5: UI, Demo & Documentation** | `app.py`, `requirements.txt`, `transcripts/*.json`, phần A của `REPORT.md` | Xây UI, hiển thị tool trace, chuẩn bị kịch bản demo, transcript và phần giới thiệu | **Trần Thanh Bình** *(2A202601174)* |