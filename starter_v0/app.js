const traceTools = [
  {
    name: "decompose_query",
    params: 'query="RAG vs fine-tuning…" · years=2024–2025',
    status: "ok",
    duration: "1.2s",
    result: `{
  "subtasks": ["benchmark quality", "update cost", "citation faithfulness"],
  "evidence_threshold": 0.82
}`,
  },
  {
    name: "search_papers",
    params: 'index="arXiv" · top_k=20',
    status: "retry",
    duration: "1.8s",
    result: `{
  "error": "429 rate limited",
  "backoff_ms": 640,
  "retry": 1,
  "final_status": "ok",
  "results": 16
}`,
  },
  {
    name: "search_papers",
    params: 'index="PubMed" · top_k=20',
    status: "ok",
    duration: "0.7s",
    result: `{
  "results": 12,
  "date_range": ["2024-01-01", "2025-12-31"]
}`,
  },
  {
    name: "search_papers",
    params: 'index="Semantic Scholar" · top_k=20',
    status: "ok",
    duration: "0.6s",
    result: `{
  "results": 10,
  "after_deduplication": 7
}`,
  },
  {
    name: "read_paper",
    params: 'paper="BioRAG" · sections=Results,Table 2',
    status: "ok",
    duration: "2.1s",
    result: `{
  "biorag_bioasq12_em": 71.4,
  "gain_vs_finetuning_points": 8.2,
  "location": "Table 2, p.7"
}`,
  },
  {
    name: "read_paper",
    params: 'paper="Domain Adaptation Cost" · table=4',
    status: "ok",
    duration: "1.4s",
    result: `{
  "retraining_cost_vs_reindex": "5–7x",
  "location": "Table 4, p.9"
}`,
  },
  {
    name: "read_paper",
    params: 'paper="Citation Faithfulness" · section=Errors',
    status: "ok",
    duration: "1.3s",
    result: `{
  "remaining_errors_attribution_pct": 42,
  "location": "§5.2, p.8"
}`,
  },
  {
    name: "read_paper",
    params: 'paper="RAG Survey" · section=Discussion',
    status: "skip",
    duration: "0.1s",
    result: `{
  "status": "skip",
  "reason": "Nội dung trùng với đoạn đã đọc; giữ provenance hiện có."
}`,
  },
  {
    name: "synthesize",
    params: "claims=6 · citations=4 · language=vi",
    status: "ok",
    duration: "2.7s",
    result: `{
  "claims": 6,
  "citations": 4,
  "confidence": 0.91,
  "consistency_check": "passed"
}`,
  },
];

const citations = [
  {
    number: 1,
    claim: "RAG y sinh phù hợp với tri thức thay đổi nhanh và cho phép truy vết nguồn ở mức đoạn.",
    quote:
      "Retrieval-augmented systems are particularly suitable for biomedical domains where evidence changes faster than model update cycles.",
    meta: "Nguyen+ 2024 · Discussion, p.14 · từ bước 3 · read_paper · tin cậy 0.89",
  },
  {
    number: 2,
    claim: "Fine-tune lại theo chu kỳ tốn gấp 5–7 lần cập nhật index và embedding.",
    quote:
      "Across quarterly update scenarios, repeated domain fine-tuning cost between 5.1 and 7.0 times more than retrieval-index refresh.",
    meta: "Patel+ 2024 · Table 4, p.9 · từ bước 3 · read_paper · tin cậy 0.92",
  },
  {
    number: 3,
    claim: "BioRAG đạt 71.4 EM trên BioASQ-12, cao hơn fine-tuning thuần 8.2 điểm.",
    quote:
      "BioRAG reaches 71.4 exact match on BioASQ-12, an 8.2-point improvement over the fine-tuned backbone.",
    meta: "Lin+ 2025 · Table 2, p.7 · từ bước 3 · read_paper · tin cậy 0.94",
  },
  {
    number: 4,
    claim: "42% lỗi còn lại là lỗi attribution giữa mệnh đề và nguồn được dẫn.",
    quote:
      "Attribution failures account for 42% of residual errors, despite many answers remaining semantically plausible.",
    meta: "Rossi+ 2025 · §5.2, p.8 · từ bước 3 · read_paper · tin cậy 0.91",
  },
];

const progressPhases = [
  {
    title: "Lập kế hoạch",
    tool: "model",
    log: "Đang phân tích câu hỏi và lập kế hoạch nghiên cứu…",
  },
  {
    title: "Tìm kiếm",
    tool: "papers · lookup",
    log: "Đang tìm các nguồn phù hợp…",
  },
  {
    title: "Đọc & trích xuất",
    tool: "paper_text · fetch",
    log: "Đang đọc và đối chiếu kết quả tool…",
  },
  {
    title: "Tổng hợp",
    tool: "model",
    log: "Đang soạn câu trả lời từ bằng chứng đã thu thập…",
  },
];

const searchTools = new Set(["papers", "lookup", "social_search", "timeline"]);
const readingTools = new Set(["paper_text", "paper_rank", "citation_audit", "fetch", "policy"]);

const conversation = document.querySelector("#conversation");
const dynamicTurns = document.querySelector("#dynamic-turns");
const input = document.querySelector("#question-input");
const sendButton = document.querySelector("#send-button");
const drawerLayer = document.querySelector("#drawer-layer");
const drawerClose = document.querySelector("#drawer-close");
const drawerBackdrop = document.querySelector("#drawer-backdrop");
const reasoningToggle = document.querySelector("#reasoning-toggle");
const speedSelect = document.querySelector("#speed-select");
const runStatus = document.querySelector("#run-status");
const toast = document.querySelector("#toast");
const indexStatus = document.querySelector(".index-status");
const indexStatusLabel = document.querySelector("#index-status-label");
let isRunning = false;
let toastTimer;
let sessionId = getOrCreateSessionId();

function escapeHtml(value) {
  return String(value ?? "").replace(
    /[&<>"']/g,
    (character) =>
      ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;",
      })[character],
  );
}

function formatJson(value) {
  if (typeof value === "string") return value;
  return JSON.stringify(value ?? {}, null, 2);
}

function getOrCreateSessionId() {
  try {
    const stored = window.localStorage.getItem("research-scout-session");
    if (stored) return stored;
    const id = `session_${crypto.randomUUID().replaceAll("-", "").slice(0, 12)}`;
    window.localStorage.setItem("research-scout-session", id);
    return id;
  } catch {
    return `session_${Date.now().toString(36)}`;
  }
}

function renderToolData(toolData = traceTools) {
  const list = document.querySelector("#tool-list");
  if (!toolData.length) {
    list.innerHTML = `<p class="citation-intro trace-empty">Chưa có tool call trong lượt chạy này.</p>`;
    return;
  }
  list.innerHTML = toolData
    .map(
      (tool) => `
        <article class="tool-item">
          <button class="tool-row" type="button" aria-expanded="false">
            <span class="tool-status-dot ${tool.status}"></span>
            <span class="tool-name">${escapeHtml(tool.name)}</span>
            <span class="tool-param">${escapeHtml(tool.params)}</span>
            <span class="status-pill ${tool.status}">${tool.status}</span>
            <span class="tool-duration">${escapeHtml(tool.duration)}</span>
          </button>
          <pre class="tool-result">${escapeHtml(formatJson(tool.result))}</pre>
        </article>
      `,
    )
    .join("");
  bindExpandableRows(list);
}

function renderCitationData(citationData = citations) {
  const list = document.querySelector("#citation-list");
  if (!citationData.length) {
    list.innerHTML = `
      <p class="citation-intro trace-empty">
        Lượt chạy này chưa trả về nguồn có URL và nội dung trích xuất đủ để tạo thẻ trích dẫn có cấu trúc.
      </p>
    `;
    document.querySelector("#citations-count").textContent = "0";
    return;
  }

  list.innerHTML = citationData
    .map(
      (citation) => `
        <article class="citation-card" data-citation-card="${citation.number}">
          <div class="citation-card-head">
            <span class="citation-number">${String(citation.number).padStart(2, "0")}</span>
            <p class="citation-claim">${escapeHtml(citation.claim)}</p>
          </div>
          <blockquote class="citation-quote">“${escapeHtml(citation.quote)}”</blockquote>
          <div class="citation-meta">${escapeHtml(citation.meta)}</div>
        </article>
      `,
    )
    .join("");
  document.querySelector("#citations-count").textContent = String(citationData.length);
}

function renderTraceData() {
  renderToolData(traceTools);
  renderCitationData(citations);
}

function bindExpandableRows(scope) {
  scope.querySelectorAll(".step-card-head, .tool-row").forEach((header) => {
    if (header.dataset.bound === "true") return;
    header.dataset.bound = "true";
    header.addEventListener("click", () => {
      const item = header.closest(".timeline-item, .tool-item");
      const shouldOpen = !item.classList.contains("open");
      item.classList.toggle("open", shouldOpen);
      header.setAttribute("aria-expanded", String(shouldOpen));
      const chevron = header.querySelector(".chevron");
      if (chevron) chevron.textContent = shouldOpen ? "▾" : "▸";
    });
  });
}

function setTab(tabName) {
  document.querySelectorAll(".drawer-tab").forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.tab === tabName);
  });
  document.querySelectorAll(".tab-panel").forEach((panel) => {
    panel.classList.toggle("active", panel.dataset.panel === tabName);
  });
}

function openDrawer(tabName = "steps", citationNumber = null) {
  setTab(tabName);
  drawerLayer.classList.add("open");
  drawerLayer.setAttribute("aria-hidden", "false");
  document.body.classList.add("drawer-open");

  if (citationNumber) {
    window.setTimeout(() => {
      const card = document.querySelector(`[data-citation-card="${citationNumber}"]`);
      if (!card) return;
      document.querySelectorAll(".citation-card").forEach((item) => item.classList.remove("highlighted"));
      card.classList.add("highlighted");
      card.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 230);
  }

  drawerClose.focus({ preventScroll: true });
}

function closeDrawer() {
  drawerLayer.classList.remove("open");
  drawerLayer.setAttribute("aria-hidden", "true");
  document.body.classList.remove("drawer-open");
}

function showToast(message) {
  window.clearTimeout(toastTimer);
  toast.textContent = message;
  toast.classList.add("show");
  toastTimer = window.setTimeout(() => toast.classList.remove("show"), 2200);
}

function autoGrow() {
  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, 120)}px`;
}

function scrollConversation() {
  conversation.scrollTo({
    top: conversation.scrollHeight,
    behavior: "smooth",
  });
}

function wait(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function createUserTurn(question) {
  const userMessage = document.createElement("article");
  userMessage.className = "message message--user";
  userMessage.innerHTML = `<div class="user-bubble">${escapeHtml(question)}</div>`;
  dynamicTurns.appendChild(userMessage);
}

function createWorkingTurn() {
  const turn = document.createElement("article");
  turn.className = "message message--agent working-turn";
  turn.innerHTML = `
    <div class="agent-avatar is-working" aria-label="Research Scout đang làm việc">
      <span class="scout-eye" aria-hidden="true"><i></i></span>
    </div>
    <div class="agent-content">
      <div class="working-card">
        <div class="working-header">
          <span class="working-state">AGENT ĐANG LÀM VIỆC</span>
          <span class="working-timer">0.0s</span>
          <button class="follow-trace" type="button">theo dõi trace →</button>
        </div>
        <ol class="progress-steps">
          ${progressPhases
            .map(
              (phase) => `
                <li class="progress-step">
                  <div class="step-line">
                    <strong>${phase.title}</strong>
                    <span class="step-tool">${phase.tool}</span>
                    <span class="step-meta">chờ</span>
                  </div>
                  <div class="step-active-content"></div>
                </li>
              `,
            )
            .join("")}
        </ol>
        <div class="streaming-block">
          <p><span class="stream-text"></span><span class="stream-caret"></span></p>
        </div>
      </div>
    </div>
  `;
  dynamicTurns.appendChild(turn);
  turn.querySelector(".follow-trace").addEventListener("click", () => openDrawer("steps"));
  return turn;
}

function finishPhase(stepElement) {
  if (!stepElement || stepElement.classList.contains("done")) return;
  const startedAt = Number(stepElement.dataset.startedAt || performance.now());
  const duration = Math.max(0, (performance.now() - startedAt) / 1000);
  stepElement.classList.remove("active");
  stepElement.classList.add("done");
  stepElement.querySelector(".step-meta").textContent = `✓ ${duration.toFixed(1)}s`;
  stepElement.querySelector(".step-active-content").innerHTML = "";
}

function activatePhase(turn, phaseIndex, logText, toolName = null) {
  const steps = [...turn.querySelectorAll(".progress-step")];
  steps.forEach((step, index) => {
    if (index < phaseIndex) finishPhase(step);
  });

  const step = steps[phaseIndex];
  if (!step) return;
  steps.forEach((item, index) => {
    if (index !== phaseIndex) item.classList.remove("active");
  });
  step.classList.remove("done");
  step.classList.add("active");
  if (!step.dataset.startedAt) step.dataset.startedAt = String(performance.now());
  step.querySelector(".step-meta").textContent = "đang chạy";
  if (toolName) step.querySelector(".step-tool").textContent = toolName;
  step.querySelector(".step-active-content").innerHTML = `
    <p class="live-log">${escapeHtml(logText || progressPhases[phaseIndex].log)}</p>
    <div class="step-progress"><span class="step-progress-fill" style="width:68%"></span></div>
  `;
}

function finishAllPhases(turn) {
  turn.querySelectorAll(".progress-step").forEach(finishPhase);
}

function phaseForTool(toolName) {
  if (searchTools.has(toolName)) return 1;
  if (readingTools.has(toolName)) return 2;
  if (toolName === "format" || toolName === "send") return 3;
  return 2;
}

function showStreamingBlock(turn) {
  const block = turn.querySelector(".streaming-block");
  block.classList.add("visible");
  return block.querySelector(".stream-text");
}

async function consumeSse(response, onEvent) {
  if (!response.ok) {
    let message = `Backend trả lỗi HTTP ${response.status}.`;
    try {
      const body = await response.json();
      message = body.detail || message;
    } catch {
      // Keep the HTTP fallback message.
    }
    throw new Error(message);
  }

  if (!response.body) throw new Error("Trình duyệt không hỗ trợ streaming response.");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
    const frames = buffer.split(/\r?\n\r?\n/);
    buffer = frames.pop() || "";

    for (const frame of frames) {
      let eventName = "message";
      const dataLines = [];
      frame.split(/\r?\n/).forEach((line) => {
        if (line.startsWith("event:")) eventName = line.slice(6).trim();
        if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
      });
      if (!dataLines.length) continue;
      await onEvent(eventName, JSON.parse(dataLines.join("\n")));
    }

    if (done) break;
  }
}

function summarizeArgs(args) {
  const text = Object.entries(args || {})
    .map(([key, value]) => `${key}=${JSON.stringify(value)}`)
    .join(" · ");
  return text || "không có tham số";
}

function updateDrawerHeader(run) {
  const duration = run.metrics?.duration_ms ? `${(run.metrics.duration_ms / 1000).toFixed(1)}s` : "đang chạy";
  const toolCount = run.toolEvents.length;
  const errorCount = run.toolEvents.filter((tool) => tool.status === "error").length;
  document.querySelector("#run-meta").textContent =
    `${run.runId || "run_pending"} · ${run.model || "model mặc định"} · ${run.provider || "backend"} · ${new Date().toLocaleString("vi-VN")}`;
  document.querySelector("#metric-duration").textContent = duration;
  document.querySelector("#metric-tools").textContent = String(toolCount);
  document.querySelector("#metric-rounds").textContent = String(run.rounds?.length || run.roundCount || 0);
  document.querySelector("#metric-errors").textContent = String(errorCount);
  document.querySelector("#tools-count").textContent = String(toolCount);
}

function renderLiveTools(run) {
  const rows = run.toolEvents.map((tool) => ({
    name: tool.name,
    params: summarizeArgs(tool.args),
    status: tool.status === "error" ? "retry" : "ok",
    duration: `${((tool.duration_ms || 0) / 1000).toFixed(2)}s`,
    result: tool.result,
  }));
  renderToolData(rows);
  updateDrawerHeader(run);
}

function renderRunningTimeline(run) {
  const roundCount = Math.max(1, run.roundCount || 0);
  const panel = document.querySelector("#panel-steps");
  const rounds = Array.from({ length: roundCount }, (_value, index) => index + 1);
  panel.innerHTML = `
    <div class="timeline">
      ${rounds
        .map((roundNumber) => {
          const completed = run.toolEvents.filter((tool) => tool.round === roundNumber);
          const pending = run.pendingTools.filter((tool) => tool.round === roundNumber);
          const tools = [...completed, ...pending];
          const isLatest = roundNumber === roundCount;
          const toolNames = tools.map((tool) => tool.name).join(", ") || "model";
          return `
            <article class="timeline-item ${isLatest ? "open" : ""}">
              <span class="timeline-dot"></span>
              <button class="step-card-head" type="button" aria-expanded="${isLatest}">
                <span class="step-index">${String(roundNumber).padStart(2, "0")}</span>
                <strong>Vòng agent ${roundNumber}</strong>
                <span class="tool-badge">${escapeHtml(toolNames)}</span>
                <span class="step-stats">${completed.length}/${tools.length} xong</span>
                <span class="chevron">${isLatest ? "▾" : "▸"}</span>
              </button>
              <div class="step-card-body">
                <p>${pending.length ? `Đang chờ ${pending.length} tool hoàn tất.` : tools.length ? "Các tool trong vòng này đã trả kết quả." : "Model đang quyết định bước tiếp theo."}</p>
                <blockquote class="reasoning-block">Trace trực tiếp chỉ hiển thị sự kiện có thể quan sát từ agent và tool.</blockquote>
                <div class="json-block json-block--output">
                  <span>SỰ KIỆN HIỆN TẠI</span>
                  <pre>${escapeHtml(formatJson(tools))}</pre>
                </div>
              </div>
            </article>
          `;
        })
        .join("")}
    </div>
  `;
  document.querySelector("#steps-count").textContent = String(roundCount);
  bindExpandableRows(panel);
}

function renderRoundTimeline(run) {
  const rounds = run.rounds || [];
  const panel = document.querySelector("#panel-steps");
  if (!rounds.length) {
    panel.innerHTML = `<p class="citation-intro trace-empty">Backend chưa trả dữ liệu vòng agent cho lượt chạy này.</p>`;
    document.querySelector("#steps-count").textContent = "0";
    return;
  }

  panel.innerHTML = `
    <div class="timeline">
      ${rounds
        .map((round, index) => {
          const calls = round.tool_calls || [];
          const results = round.tool_results || [];
          const toolNames = calls.map((call) => call.name).join(", ") || "model";
          const isOpen = index === 0;
          return `
            <article class="timeline-item ${isOpen ? "open" : ""}">
              <span class="timeline-dot"></span>
              <button class="step-card-head" type="button" aria-expanded="${isOpen}">
                <span class="step-index">${String(index + 1).padStart(2, "0")}</span>
                <strong>Vòng agent ${round.round}</strong>
                <span class="tool-badge">${escapeHtml(toolNames)}</span>
                <span class="step-stats">${calls.length} tool</span>
                <span class="chevron">${isOpen ? "▾" : "▸"}</span>
              </button>
              <div class="step-card-body">
                <p>${calls.length ? `Agent đã yêu cầu ${calls.length} tool trước khi tiếp tục tổng hợp.` : "Agent đã hoàn tất câu trả lời mà không cần gọi thêm tool."}</p>
                <blockquote class="reasoning-block">Bản ghi này chỉ hiển thị quyết định gọi tool và kết quả quan sát được, không hiển thị suy luận ẩn của mô hình.</blockquote>
                <div class="json-block json-block--input">
                  <span>TOOL CALLS</span>
                  <pre>${escapeHtml(formatJson(calls))}</pre>
                </div>
                <div class="json-block json-block--output">
                  <span>TOOL RESULTS</span>
                  <pre>${escapeHtml(formatJson(results))}</pre>
                </div>
              </div>
            </article>
          `;
        })
        .join("")}
    </div>
  `;
  document.querySelector("#steps-count").textContent = String(rounds.length);
  bindExpandableRows(panel);
}

function collectSourceCandidates(value, toolName, output, seen, depth = 0) {
  if (depth > 6 || value == null) return;
  if (Array.isArray(value)) {
    value.forEach((item) => collectSourceCandidates(item, toolName, output, seen, depth + 1));
    return;
  }
  if (typeof value !== "object") return;

  const url = value.url || value.arxiv_url || value.pdf_url || value.link;
  if (url && !seen.has(url)) {
    seen.add(url);
    const quote = value.summary || value.abstract || value.snippet || value.text || value.content || "Nguồn đã được tool trả về nhưng không có đoạn trích ngắn.";
    output.push({
      number: output.length + 1,
      claim: value.title || value.name || `Nguồn từ ${toolName}`,
      quote: String(quote).replace(/\s+/g, " ").slice(0, 420),
      meta: `${value.source || value.authors || "nguồn web"} · ${toolName} · ${url}`,
    });
  }

  Object.values(value).forEach((child) => {
    collectSourceCandidates(child, toolName, output, seen, depth + 1);
  });
}

function citationsFromRun(run) {
  const output = [];
  const seen = new Set();
  (run.toolEvents || []).forEach((tool) => {
    collectSourceCandidates(tool.result, tool.name, output, seen);
  });
  return output.slice(0, 12);
}

function renderCompletedTrace(run) {
  renderRoundTimeline(run);
  renderLiveTools(run);
  run.citations = citationsFromRun(run);
  renderCitationData(run.citations);
  updateDrawerHeader(run);
}

function formatAnswerHtml(answer, citationCount) {
  const escaped = escapeHtml(answer);
  const withCitationButtons = escaped.replace(/\[(\d{1,2})\]/g, (match, number) => {
    const citation = Number(number);
    if (citation < 1 || citation > citationCount) return match;
    return `<button class="citation-chip" type="button" data-citation="${citation}">${citation}</button>`;
  });
  return withCitationButtons
    .split(/\n{2,}/)
    .filter(Boolean)
    .map((paragraph) => `<p>${paragraph.replaceAll("\n", "<br>")}</p>`)
    .join("");
}

function finalizeTurn(turn, run) {
  turn.querySelector(".agent-avatar").classList.remove("is-working");
  const card = turn.querySelector(".working-card");
  const completed = document.createElement("div");
  completed.className = "completed-answer";
  const duration = run.metrics?.duration_ms ? `${(run.metrics.duration_ms / 1000).toFixed(1)}s` : "—";
  const rounds = run.rounds?.length || 0;
  const toolCalls = run.toolEvents.length;
  completed.innerHTML = `
    <button class="trace-summary" type="button" data-open-trace="steps">
      <span class="trace-step-dots" aria-hidden="true"><i></i><i></i><i></i><i></i></span>
      <span>${rounds} vòng · ${toolCalls} tool calls · ${duration} · ${escapeHtml(run.model || run.provider || "backend")}</span>
      <span class="trace-link">xem trace →</span>
    </button>
    <div class="answer-copy">
      <p class="section-label">KẾT QUẢ TỪ AGENT</p>
      <div class="live-answer">${formatAnswerHtml(run.answer, run.citations?.length || 0)}</div>
    </div>
  `;
  card.replaceWith(completed);
  completed.querySelector(".trace-summary").addEventListener("click", () => openDrawer("steps"));
  completed.querySelectorAll(".citation-chip").forEach((chip) => {
    chip.addEventListener("click", () => openDrawer("citations", chip.dataset.citation));
  });
}

function renderRunFailure(turn, message) {
  turn.querySelector(".agent-avatar").classList.remove("is-working");
  const card = turn.querySelector(".working-card");
  const failed = document.createElement("div");
  failed.className = "completed-answer completed-answer--error";
  failed.innerHTML = `
    <p class="section-label">KHÔNG THỂ HOÀN TẤT LƯỢT CHẠY</p>
    <p>${escapeHtml(message)}</p>
    <p class="backend-help">Kiểm tra server và API key, sau đó gửi lại câu hỏi.</p>
  `;
  card.replaceWith(failed);
}

async function handleBackendEvent(eventName, payload, turn, run) {
  const speed = Number(speedSelect.value);
  if (eventName === "run_started") {
    run.runId = payload.run_id;
    run.provider = payload.provider;
    run.model = payload.model;
    sessionId = payload.session_id || sessionId;
    try {
      window.localStorage.setItem("research-scout-session", sessionId);
    } catch {
      // Session persistence is optional.
    }
    activatePhase(turn, 0, "Backend đã nhận câu hỏi · đang lập kế hoạch…", payload.model);
    renderLiveTools(run);
    renderCitationData([]);
    renderRunningTimeline(run);
  } else if (eventName === "round_started") {
    run.roundCount = Math.max(run.roundCount, payload.round || 0);
    activatePhase(turn, 0, `Đang gọi model — vòng ${payload.round}…`, run.model);
    renderRunningTimeline(run);
  } else if (eventName === "model_completed") {
    if (payload.tool_call_count > 0) {
      activatePhase(turn, 1, `Model yêu cầu ${payload.tool_call_count} tool · đang thực thi…`);
    } else {
      activatePhase(turn, 3, "Không cần thêm tool · đang soạn câu trả lời…", run.model);
    }
    renderRunningTimeline(run);
  } else if (eventName === "tool_started") {
    const phase = phaseForTool(payload.name);
    run.pendingTools.push(payload);
    activatePhase(turn, phase, `Đang chạy ${payload.name}(${summarizeArgs(payload.args)})…`, payload.name);
    renderRunningTimeline(run);
  } else if (eventName === "tool_completed") {
    run.pendingTools = run.pendingTools.filter((tool) => tool.call_index !== payload.call_index);
    run.toolEvents.push(payload);
    const phase = phaseForTool(payload.name);
    activatePhase(
      turn,
      phase,
      `${payload.name} ${payload.status === "ok" ? "đã trả kết quả" : "gặp lỗi"} sau ${((payload.duration_ms || 0) / 1000).toFixed(2)}s…`,
      payload.name,
    );
    renderLiveTools(run);
    renderRunningTimeline(run);
  } else if (eventName === "answer_started") {
    turn.querySelector(".working-state").textContent = "ĐANG SOẠN CÂU TRẢ LỜI";
    activatePhase(turn, 3, "Đang truyền câu trả lời từ backend…", run.model);
    showStreamingBlock(turn);
  } else if (eventName === "token") {
    const textNode = showStreamingBlock(turn);
    textNode.textContent += payload.text || "";
    if (textNode.textContent.length % 84 < 12) scrollConversation();
    await wait(26 / speed);
  } else if (eventName === "run_completed") {
    run.answer = payload.assistant_text || "";
    run.rounds = payload.rounds || [];
    run.metrics = payload.metrics || {};
    run.status = payload.status;
    finishAllPhases(turn);
    renderCompletedTrace(run);
  } else if (eventName === "run_failed") {
    run.failed = payload.message || "Backend không thể hoàn tất lượt chạy.";
  }
}

async function submitQuestion(question) {
  const cleanQuestion = question.trim();
  if (!cleanQuestion || isRunning) return;

  isRunning = true;
  input.disabled = true;
  sendButton.disabled = true;
  document.querySelectorAll(".suggestion-chip").forEach((chip) => (chip.disabled = true));
  runStatus.classList.remove("failed");
  runStatus.classList.add("running");
  runStatus.innerHTML = "<i></i> đang chạy";

  createUserTurn(cleanQuestion);
  const turn = createWorkingTurn();
  input.value = "";
  autoGrow();
  document.querySelector("#turn-count").textContent = "3 lượt";
  scrollConversation();

  const speed = Number(speedSelect.value);
  const timer = turn.querySelector(".working-timer");
  const state = turn.querySelector(".working-state");
  const started = performance.now();
  const timerInterval = window.setInterval(() => {
    const elapsed = (performance.now() - started) / 1000;
    timer.textContent = `${elapsed.toFixed(1)}s`;
  }, 100);

  const run = {
    runId: null,
    provider: null,
    model: null,
    toolEvents: [],
    pendingTools: [],
    rounds: [],
    roundCount: 0,
    metrics: null,
    answer: "",
    citations: [],
    failed: null,
  };
  activatePhase(turn, 0, progressPhases[0].log);

  try {
    const response = await fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: cleanQuestion,
        session_id: sessionId,
      }),
    });
    await consumeSse(response, (eventName, payload) =>
      handleBackendEvent(eventName, payload, turn, run),
    );
    if (run.failed) throw new Error(run.failed);
    if (!run.answer) throw new Error("Backend kết thúc nhưng không trả nội dung câu trả lời.");

    state.textContent = "HOÀN TẤT";
    timer.textContent = `${((run.metrics?.duration_ms || performance.now() - started) / 1000).toFixed(1)}s`;
    turn.querySelector(".agent-avatar").classList.remove("is-working");
    await wait(300 / speed);
    finalizeTurn(turn, run);
    runStatus.classList.remove("running", "failed");
    runStatus.innerHTML = "<i></i> thành công";
  } catch (error) {
    run.failed = error instanceof Error ? error.message : String(error);
    renderRunFailure(turn, run.failed);
    runStatus.classList.remove("running");
    runStatus.classList.add("failed");
    runStatus.innerHTML = "<i></i> thất bại";
  } finally {
    window.clearInterval(timerInterval);
    isRunning = false;
    input.disabled = false;
    sendButton.disabled = false;
    document.querySelectorAll(".suggestion-chip").forEach((chip) => (chip.disabled = false));
    input.focus();
    scrollConversation();
  }
}

renderTraceData();
bindExpandableRows(document);

document.querySelector("#header-trace-button").addEventListener("click", () => openDrawer("steps"));
drawerClose.addEventListener("click", closeDrawer);
drawerBackdrop.addEventListener("click", closeDrawer);

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && drawerLayer.classList.contains("open")) closeDrawer();
});

document.querySelectorAll(".drawer-tab").forEach((tab) => {
  tab.addEventListener("click", () => setTab(tab.dataset.tab));
});

document.querySelectorAll("[data-open-trace]").forEach((element) => {
  element.addEventListener("click", () => {
    openDrawer(element.dataset.openTrace, element.dataset.citation || null);
  });
});

document.querySelectorAll(".citation-chip").forEach((chip) => {
  chip.addEventListener("click", () => openDrawer("citations", chip.dataset.citation));
});

reasoningToggle.addEventListener("change", () => {
  document.body.classList.toggle("hide-reasoning", !reasoningToggle.checked);
  showToast(reasoningToggle.checked ? "Đã hiện reasoning" : "Đã ẩn reasoning");
});

speedSelect.addEventListener("change", () => {
  showToast(`Tốc độ mô phỏng: ${speedSelect.value}×`);
});

input.addEventListener("input", autoGrow);
input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    submitQuestion(input.value);
  }
});
sendButton.addEventListener("click", () => submitQuestion(input.value));

document.querySelectorAll(".suggestion-chip").forEach((chip) => {
  chip.addEventListener("click", () => submitQuestion(chip.textContent));
});

document.querySelectorAll(".nav-pill").forEach((pill) => {
  pill.addEventListener("click", () => {
    if (!pill.classList.contains("active")) showToast(`${pill.textContent.trim()} đang được hoàn thiện`);
  });
});

async function checkBackend() {
  try {
    const response = await fetch("/api/health", { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const health = await response.json();
    indexStatus.classList.toggle("offline", !health.provider_configured);
    indexStatusLabel.textContent = health.provider_configured
      ? `${health.provider} · ${health.model} · backend sẵn sàng`
      : `${health.provider} · thiếu API key`;
  } catch {
    indexStatus.classList.add("offline");
    indexStatusLabel.textContent = "backend chưa chạy · dùng python web_server.py";
  }
}

checkBackend();
