const appState = {
  data: null,
  qualityState: "baseline",
  chatState: "baseline",
  chatMode: "controlled",
  isChatting: false,
};

const STATE_ORDER = ["baseline", "corrupted", "repaired"];
const STATE_COPY = {
  baseline: {
    badge: "Tham chiếu",
    caption: "Dữ liệu tham chiếu sạch",
    qualityTitle: "Sức khỏe dữ liệu gốc",
  },
  corrupted: {
    badge: "Có lỗi",
    caption: "Lỗi có kiểm soát",
    qualityTitle: "Sức khỏe dữ liệu lỗi",
  },
  repaired: {
    badge: "Phục hồi",
    caption: "Phục hồi từ dữ liệu gốc",
    qualityTitle: "Sức khỏe dữ liệu phục hồi",
  },
};

const MODE_COPY = {
  controlled: {
    label: "So sánh ổn định",
    description: "Dùng cùng một quy tắc truy xuất để đo công bằng trên ba trạng thái dữ liệu.",
  },
  agent: {
    label: "OpenAI Agent",
    description: "OpenAI quyết định gọi lookup_paper hoặc semantic_search_papers, nhận ngữ cảnh từ ChromaDB rồi tổng hợp câu trả lời.",
  },
};

const FRESHNESS_COPY = {
  fresh: "Mới",
  stale: "Quá cũ",
  unknown: "Không rõ",
};

const QUESTION_TYPE_COPY = {
  main_topic: "Chủ đề chính",
  topic: "Chủ đề",
  author: "Tác giả",
  authors: "Tác giả",
  published_date: "Ngày xuất bản",
  publication_date: "Ngày xuất bản",
  date: "Ngày xuất bản",
  summary: "Tóm tắt",
  categories: "Danh mục",
};

const CHECK_NAME_COPY = {
  minimum_row_count: "Số dòng tối thiểu",
  paper_id_complete: "Đầy đủ mã bài báo",
  paper_id_unique: "Mã bài báo không trùng",
  title_complete: "Đầy đủ tiêu đề",
  summary_complete: "Đầy đủ phần tóm tắt",
  summary_minimum_length: "Độ dài tóm tắt tối thiểu",
  embedding_text_complete: "Đầy đủ văn bản embedding",
  published_date_valid: "Ngày công bố hợp lệ",
  published_not_in_future: "Ngày công bố không ở tương lai",
  age_days_valid: "Tuổi dữ liệu hợp lệ",
  no_suspicious_noise_marker: "Không có dấu hiệu nhiễu đáng ngờ",
  all_rows_within_freshness_threshold: "Mọi dòng nằm trong ngưỡng độ mới",
};

const DIMENSION_COPY = {
  volume: "Số lượng",
  completeness: "Độ đầy đủ",
  uniqueness: "Tính duy nhất",
  validity: "Tính hợp lệ",
  freshness: "Độ mới",
};

const EXPECTATION_COPY = {
  ">= 10": "tối thiểu 10 dòng",
  "0 missing": "không có dữ liệu thiếu",
  "0 duplicated rows": "không có dòng trùng",
  "0 summaries shorter than 40 characters": "không có tóm tắt ngắn hơn 40 ký tự",
  "0 invalid": "không có giá trị không hợp lệ",
  "0 dates after the current UTC date": "không có ngày sau ngày UTC hiện tại",
  "0 suspicious corruption markers": "không có dấu hiệu dữ liệu bị chèn nhiễu",
  "0 rows older than 180 days": "không có dòng cũ hơn 180 ngày",
};

const EVENT_COPY = {
  drop_latest_records: "Loại bỏ bản ghi mới nhất",
  blank_summary: "Xóa nội dung tóm tắt",
  inject_summary_noise: "Chèn nhiễu vào tóm tắt",
  truncate_title: "Cắt ngắn tiêu đề",
  make_publication_stale: "Làm ngày công bố quá cũ",
  duplicate_row: "Nhân đôi bản ghi",
};

const ARTIFACT_GROUP_COPY = {
  raw: "Dữ liệu gốc",
  clean: "Dữ liệu sạch",
  embeddings: "Embedding",
  eval: "Bộ đánh giá",
  quality: "Chất lượng",
  results: "Kết quả",
  reports: "Báo cáo",
  gx: "Kiểm định GX",
};

const FLOW_ICONS = {
  source: '<svg viewBox="0 0 24 24"><path d="M12 3c4.4 0 8 1.3 8 3s-3.6 3-8 3-8-1.3-8-3 3.6-3 8-3Z"/><path d="M4 6v6c0 1.7 3.6 3 8 3s8-1.3 8-3V6"/></svg>',
  raw: '<svg viewBox="0 0 24 24"><path d="M6 3h9l4 4v14H6z"/><path d="M15 3v5h4M9 12h7M9 16h7"/></svg>',
  clean: '<svg viewBox="0 0 24 24"><path d="m4 15 5 5L20 6"/><path d="M4 7h7M4 11h4"/></svg>',
  embed: '<svg viewBox="0 0 24 24"><circle cx="6" cy="12" r="2"/><circle cx="18" cy="6" r="2"/><circle cx="18" cy="18" r="2"/><path d="m8 11 8-4M8 13l8 4"/></svg>',
  chroma: '<svg viewBox="0 0 24 24"><path d="M12 3c4.4 0 8 1.3 8 3s-3.6 3-8 3-8-1.3-8-3 3.6-3 8-3Z"/><path d="M4 6v6c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/></svg>',
  rag: '<svg viewBox="0 0 24 24"><path d="M5 4h14v13H9l-4 4z"/><path d="M9 9h6M9 13h4"/></svg>',
  evaluate: '<svg viewBox="0 0 24 24"><path d="M4 19V9m5 10V5m5 14v-7m5 7V3"/></svg>',
  observe: '<svg viewBox="0 0 24 24"><path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Z"/><circle cx="12" cy="12" r="2.5"/></svg>',
  recover: '<svg viewBox="0 0 24 24"><path d="M20 6v5h-5M4 18v-5h5"/><path d="M6.1 9a7 7 0 0 1 11.7-2.6L20 11M4 13l2.2 4.6A7 7 0 0 0 18 15"/></svg>',
};

const safe = (value) =>
  String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

const clamp = (value, min, max) => Math.min(Math.max(value, min), max);
const metric = (value, digits = 4) => Number(value ?? 0).toFixed(digits);

function showToast(message) {
  const toast = document.querySelector("#toast");
  toast.textContent = message;
  toast.classList.add("show");
  window.clearTimeout(showToast.timeout);
  showToast.timeout = window.setTimeout(() => toast.classList.remove("show"), 2600);
}

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.message || `Yêu cầu thất bại với mã HTTP ${response.status}`);
  }
  return payload;
}

function activateTab(tab) {
  document.querySelectorAll("[data-panel]").forEach((panel) => {
    panel.classList.toggle("active", panel.dataset.panel === tab);
  });
  document.querySelectorAll(".nav-item").forEach((button) => {
    button.classList.toggle("active", button.dataset.tab === tab);
  });
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function renderHero() {
  const baseline = appState.data.states.baseline;
  const corrupted = appState.data.states.corrupted;
  const repaired = appState.data.states.repaired;
  document.querySelector("#heroPapers").textContent = baseline.row_count;
  document.querySelector("#heroChecks").textContent = `${baseline.quality.passed_checks}/${baseline.quality.checks.length}`;
  document.querySelector("#heroSamples").textContent = baseline.metrics.samples;
  const recovered = repaired.metrics.retrieval_hit_rate - corrupted.metrics.retrieval_hit_rate;
  document.querySelector("#recoveryLabel").textContent = `+${metric(recovered * 100, 0)} điểm sau phục hồi`;

  const bars = [0.38, 0.52, baseline.metrics.retrieval_hit_rate, corrupted.metrics.retrieval_hit_rate, 0.42, repaired.metrics.retrieval_hit_rate];
  document.querySelector("#heroSpark").innerHTML = bars
    .map((value, index) => `<i class="${index === bars.length - 1 ? "hot" : ""}" style="height:${Math.max(5, value * 38)}px"></i>`)
    .join("");
}

function renderFlow() {
  const track = document.querySelector("#flowTrack");
  track.innerHTML = appState.data.flow
    .map(
      (step, index) => `
        <button class="flow-node ${safe(step.tone)} ${index === 0 ? "active" : ""}" data-flow-index="${index}">
          <span class="node-icon">${FLOW_ICONS[step.id] || FLOW_ICONS.raw}</span>
          <small>${safe(step.eyebrow)}</small>
          <strong>${safe(step.label)}</strong>
          <span>${safe(step.value)}</span>
        </button>`,
    )
    .join("");
  track.querySelectorAll(".flow-node").forEach((node) => {
    node.addEventListener("click", () => selectFlowStep(Number(node.dataset.flowIndex)));
  });
  selectFlowStep(0);
}

function selectFlowStep(index) {
  const step = appState.data.flow[index];
  document.querySelectorAll(".flow-node").forEach((node, nodeIndex) => node.classList.toggle("active", nodeIndex === index));
  const processItems = Array.isArray(step.process) ? step.process : [];
  const evidenceItems = Array.isArray(step.evidence) ? step.evidence : [];
  document.querySelector("#flowDetail").innerHTML = `
    <div class="flow-detail-header">
      <span class="flow-detail-index">${String(index + 1).padStart(2, "0")}</span>
      <div class="flow-detail-title">
        <small>${safe(step.eyebrow)}</small>
        <h3>${safe(step.label)}</h3>
        <p>${safe(step.detail)}</p>
      </div>
      <span class="flow-detail-value">${safe(step.value)}</span>
    </div>
    <div class="flow-detail-grid">
      <article class="flow-detail-card">
        <span class="detail-label">MỤC ĐÍCH</span>
        <p>${safe(step.purpose || step.detail)}</p>
      </article>
      <article class="flow-detail-card">
        <span class="detail-label">ĐẦU VÀO</span>
        <p>${safe(step.input || "—")}</p>
      </article>
      <article class="flow-detail-card">
        <span class="detail-label">ĐẦU RA</span>
        <p>${safe(step.output || step.value)}</p>
      </article>
    </div>
    <section class="flow-process-card">
      <div class="flow-process-heading">
        <span class="detail-label">CÁCH HOẠT ĐỘNG</span>
        <span>${processItems.length} thao tác chính</span>
      </div>
      <ol>${processItems.map((item) => `<li><span></span><p>${safe(item)}</p></li>`).join("")}</ol>
    </section>
    <div class="flow-detail-bottom">
      <section class="flow-evidence-card">
        <span class="detail-label">TỆP BẰNG CHỨNG</span>
        <div class="flow-evidence-list">${evidenceItems.map((item) => `<code>${safe(item)}</code>`).join("")}</div>
      </section>
      <aside class="flow-key-point">
        <span class="detail-label">ĐIỂM CẦN NHỚ</span>
        <p>${safe(step.key_point || "")}</p>
      </aside>
    </div>`;
}

function renderStateComparison() {
  const stateCards = document.querySelector("#stateCards");
  stateCards.innerHTML = STATE_ORDER.map((state) => {
    const item = appState.data.states[state];
    const quality = item.quality.overall_success ? "Chất lượng đạt" : `${item.quality.failed_checks.length} kiểm tra lỗi`;
    return `
      <article class="state-card ${state}">
        <div class="state-card-top">
          <span>${safe(item.label)}</span>
          <span class="state-badge ${state}">${safe(STATE_COPY[state].badge)}</span>
        </div>
        <div class="state-card-metric"><strong>${metric(item.metrics.retrieval_hit_rate * 100, 0)}%</strong><span>tỷ lệ truy xuất đúng</span></div>
        <div class="state-card-bottom"><span>${safe(quality)}</span><span><strong>${item.row_count}</strong> dòng</span></div>
      </article>`;
  }).join("");

  const metrics = [
    ["Tỷ lệ truy xuất đúng", "đáp án chuẩn xuất hiện trong top-k", "retrieval_hit_rate", 1],
    ["Token F1 trung bình", "mức trùng khớp từ vựng của câu trả lời", "mean_token_f1", 1],
    ["Độ chính xác đánh giá", "mức đúng theo OpenAI", "judge_accuracy", 1],
    ["Điểm đánh giá trung bình", "điểm chất lượng trên thang 5", "mean_judge_score", 5],
    ["Ragas · độ liên quan", "mức câu trả lời bám sát câu hỏi", "ragas.answer_relevancy", 1],
    ["Ragas · precision ngữ cảnh", "tỷ lệ nguồn truy xuất thực sự hữu ích", "ragas.context_precision", 1],
    ["Ragas · recall ngữ cảnh", "mức bao phủ thông tin cần thiết", "ragas.context_recall", 1],
    ["Ragas · tính trung thực", "mức câu trả lời được hỗ trợ bởi nguồn", "ragas.faithfulness", 1],
  ];
  document.querySelector("#metricChart").innerHTML = metrics.map(([label, caption, key, max]) => `
    <div class="metric-row">
      <div class="metric-label"><strong>${label}</strong><small>${caption}</small></div>
      <div class="metric-bars">
        ${STATE_ORDER.map((state) => {
          const stateMetrics = appState.data.states[state].metrics;
          const value = key.startsWith("ragas.")
            ? stateMetrics.ragas?.[key.split(".")[1]] ?? 0
            : stateMetrics[key];
          return `<div class="metric-bar-line ${state}"><span>${safe(appState.data.states[state].label)}</span><div class="bar-track"><i class="bar-fill" style="width:${clamp((value / max) * 100, 0, 100)}%"></i></div><strong>${metric(value, key === "mean_judge_score" ? 2 : 3)}</strong></div>`;
        }).join("")}
      </div>
    </div>`).join("");

  const f1Loss = appState.data.states.baseline.metrics.mean_token_f1 - appState.data.states.corrupted.metrics.mean_token_f1;
  const corruptedFaithfulness = appState.data.states.corrupted.metrics.ragas?.faithfulness ?? 0;
  const repairedFaithfulness = appState.data.states.repaired.metrics.ragas?.faithfulness ?? 0;
  document.querySelector("#takeawayText").textContent =
    `Dữ liệu lỗi kéo tỷ lệ truy xuất đúng về 0, làm token F1 giảm ${metric(f1Loss * 100, 1)} điểm và Ragas faithfulness còn ${metric(corruptedFaithfulness, 3)}; bản dựng lại từ raw đưa core metrics về baseline và faithfulness lên ${metric(repairedFaithfulness, 3)}.`;
}

function renderQuality(state) {
  appState.qualityState = state;
  document.querySelectorAll("#qualityStateSwitch button").forEach((button) => button.classList.toggle("active", button.dataset.state === state));
  const item = appState.data.states[state];
  const quality = item.quality;
  const freshness = item.freshness;
  const totalChecks = quality.checks.length;
  const ratio = quality.passed_checks / totalChecks;

  document.querySelector("#qualityTitle").textContent = STATE_COPY[state].qualityTitle;
  const stateTag = document.querySelector("#qualityStateTag");
  stateTag.textContent = item.label;
  stateTag.className = `state-tag ${state}`;
  document.querySelector("#qualityScore").textContent = `${quality.passed_checks}/${totalChecks}`;
  document.querySelector("#qualityRows").textContent = item.row_count;
  document.querySelector("#qualityUnique").textContent = item.unique_papers;
  document.querySelector("#qualityFailed").textContent = quality.failed_checks.length;
  document.querySelector("#qualityRing").style.background = `conic-gradient(${quality.overall_success ? "var(--green)" : "var(--red)"} 0deg ${ratio * 360}deg, var(--rose-100) ${ratio * 360}deg 360deg)`;

  const callout = document.querySelector("#qualityCallout");
  callout.className = `quality-callout ${quality.overall_success ? "" : "fail"}`;
  callout.innerHTML = quality.overall_success
    ? "<strong>✓</strong> Bộ dữ liệu đạt mọi điều kiện chất lượng đã cấu hình."
    : `<strong>!</strong> Không đạt: ${safe(quality.failed_checks.map((name) => CHECK_NAME_COPY[name] || name).join(", "))}`;

  const freshnessBadge = document.querySelector("#freshnessBadge");
  freshnessBadge.className = `status-dot-badge ${freshness.status}`;
  freshnessBadge.innerHTML = `<i></i>${safe(FRESHNESS_COPY[freshness.status] || freshness.status)}`;
  document.querySelector("#freshLatest").textContent = freshness.latest_published || "Không rõ";
  document.querySelector("#freshOldest").textContent = freshness.oldest_published || "Không rõ";
  document.querySelector("#freshStale").textContent = `${freshness.stale_rows}/${freshness.total_rows}`;
  const staleRatio = freshness.total_rows ? freshness.stale_rows / freshness.total_rows : 1;
  const marker = freshness.is_fresh ? 5 : 55 + staleRatio * 40;
  document.querySelector("#freshnessMarker").style.left = `${clamp(marker, 4, 95)}%`;
  document.querySelector("#freshnessMarker").style.borderColor = freshness.is_fresh ? "var(--green)" : "var(--red)";

  document.querySelector("#checkCount").textContent = `${quality.passed_checks}/${totalChecks} đạt`;
  document.querySelector("#checksList").innerHTML = quality.checks.map((check) => `
    <div class="check-row">
      <span class="check-status ${check.success ? "" : "fail"}">
        ${check.success ? '<svg viewBox="0 0 24 24"><path d="m5 12 4 4L19 6"/></svg>' : '<svg viewBox="0 0 24 24"><path d="m7 7 10 10M17 7 7 17"/></svg>'}
      </span>
      <span class="check-copy"><strong>${safe(CHECK_NAME_COPY[check.name] || check.name.replaceAll("_", " "))}</strong><span>${safe(DIMENSION_COPY[check.dimension] || check.dimension)} · ${safe(EXPECTATION_COPY[check.expectation] || check.expectation)}</span></span>
      <span class="check-observed"><strong>${safe(check.observed)}</strong> ghi nhận</span>
    </div>`).join("");
}

function renderEvents() {
  const events = appState.data.corruption.events || [];
  document.querySelector("#eventCount").textContent = `${events.length} sự kiện`;
  document.querySelector("#eventTimeline").innerHTML = events.map((event) => `
    <div class="event-item">
      <span class="event-dot"><i></i></span>
      <span class="event-copy"><strong>${safe(EVENT_COPY[event.type] || event.type.replaceAll("_", " "))}</strong><span>${safe((event.affected_paper_ids || []).slice(0, 2).join(", "))}${(event.affected_paper_ids || []).length > 2 ? "…" : ""}</span></span>
      <em>${safe(event.count)} bị ảnh hưởng</em>
    </div>`).join("");
}

function prettyBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function renderArtifacts() {
  const artifacts = appState.data.artifacts;
  document.querySelector("#artifactTotal").textContent = `${artifacts.length} tệp`;
  document.querySelector("#artifactGrid").innerHTML = artifacts.map((artifact) => `
    <article class="artifact-card" title="${safe(artifact.path)}">
      <span class="artifact-icon"><svg viewBox="0 0 24 24"><path d="M6 3h9l4 4v14H6z"/><path d="M15 3v5h4M9 12h7M9 16h7"/></svg></span>
      <span><strong>${safe(artifact.path.split("/").at(-1))}</strong><span>${safe(ARTIFACT_GROUP_COPY[artifact.group] || artifact.group)}</span></span>
      <em>${prettyBytes(artifact.bytes)}</em>
    </article>`).join("");
}

async function loadRecords() {
  const state = document.querySelector("#recordState").value;
  const query = document.querySelector("#recordQuery").value;
  const table = document.querySelector("#recordsTable");
  table.innerHTML = '<tr><td colspan="5"><span class="skeleton" style="display:block;height:44px;border-radius:8px"></span></td></tr>';
  try {
    const payload = await fetchJson(`/api/records?state=${encodeURIComponent(state)}&q=${encodeURIComponent(query)}&limit=12`);
    document.querySelector("#recordCount").textContent = `${payload.total} bản ghi phù hợp · ${STATE_COPY[state].caption}`;
    table.innerHTML = payload.records.length
      ? payload.records.map((record) => {
          const issue = Number(record.summary_chars || 0) < 40 || Number(record.age_days || 0) > 180;
          return `<tr>
            <td class="paper-cell"><strong title="${safe(record.title)}">${safe(record.title || "Không có tiêu đề")}</strong><span>${safe(record.paper_id)}</span></td>
            <td>${safe(record.published)}</td>
            <td>${safe(record.age_days)} ngày</td>
            <td>${safe(record.summary_chars)} ký tự</td>
            <td><span class="table-status ${issue ? "fail" : ""}">${issue ? "Cần kiểm tra" : "Hợp lệ"}</span></td>
          </tr>`;
        }).join("")
      : '<tr><td colspan="5">Không có bản ghi phù hợp với tìm kiếm.</td></tr>';
  } catch (error) {
    table.innerHTML = `<tr><td colspan="5">${safe(error.message)}</td></tr>`;
  }
}

function renderSuggestions() {
  document.querySelector("#suggestionList").innerHTML = appState.data.suggestions.map((item) => `
    <button class="suggestion-chip" data-question="${safe(item.question)}" title="${safe(item.question)}">${safe(QUESTION_TYPE_COPY[item.type] || item.type)} · ${safe(item.question)}</button>`).join("");
  document.querySelectorAll(".suggestion-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      document.querySelector("#chatInput").value = chip.dataset.question;
      document.querySelector("#chatInput").focus();
    });
  });
}

function selectChatState(state) {
  appState.chatState = state;
  document.querySelectorAll(".collection-option").forEach((button) => button.classList.toggle("active", button.dataset.state === state));
  const item = appState.data.states[state];
  document.querySelector("#chatCollectionLabel").textContent = item.collection;
  document.querySelector("#collectionDetail").innerHTML = `
    <span>Bộ sưu tập đang dùng</span>
    <strong>${safe(item.collection)}</strong>
    <small>Chất lượng ${item.quality.passed_checks}/${item.quality.checks.length} · ${safe(FRESHNESS_COPY[item.freshness.status] || item.freshness.status)}</small>`;
  showToast(`Đã chuyển sang bộ sưu tập ${item.label}`);
}

function selectAnswerMode(mode) {
  if (!MODE_COPY[mode]) return;
  appState.chatMode = mode;
  document.querySelectorAll("#answerModeSwitch button").forEach((button) => {
    button.classList.toggle("active", button.dataset.mode === mode);
  });
  document.querySelector("#answerModeDescription").textContent = MODE_COPY[mode].description;
  document.querySelector("#chatModeLabel").textContent = MODE_COPY[mode].label;
  showToast(`Đã chọn ${MODE_COPY[mode].label}`);
}

function addUserMessage(question) {
  const messages = document.querySelector("#chatMessages");
  messages.insertAdjacentHTML("beforeend", `
    <div class="message user-message">
      <div class="message-avatar">B</div>
      <div class="message-body"><span class="message-author">Bạn</span><div class="message-bubble">${safe(question)}</div></div>
    </div>`);
  messages.scrollTop = messages.scrollHeight;
}

function addLoadingMessage() {
  const messages = document.querySelector("#chatMessages");
  const id = `loading-${Date.now()}`;
  messages.insertAdjacentHTML("beforeend", `
    <div class="message assistant-message" id="${id}">
      <div class="message-avatar">P</div>
      <div class="message-body"><span class="message-author">Princess · ${appState.chatMode === "agent" ? "OpenAI Agent đang chọn công cụ" : "đang truy xuất"}</span><div class="message-bubble typing"><i></i><i></i><i></i></div></div>
    </div>`);
  messages.scrollTop = messages.scrollHeight;
  return id;
}

function addAssistantResult(payload) {
  const messages = document.querySelector("#chatMessages");
  const sourceId = `sources-${Date.now()}`;
  const evidence = payload.evaluation_evidence;
  messages.insertAdjacentHTML("beforeend", `
    <div class="message assistant-message">
      <div class="message-avatar">P</div>
      <div class="message-body">
        <span class="message-author">Princess · ${safe(payload.mode_label)} · ${safe(payload.state_label)}</span>
        <div class="message-bubble">${safe(payload.answer)}</div>
        <div class="message-meta">
          <span><svg viewBox="0 0 24 24"><path d="M12 3v9l6 3"/><circle cx="12" cy="12" r="9"/></svg>${safe(payload.duration_ms)} ms</span>
          <span>${safe(payload.route)}</span>
          <span>${payload.sources.length} nguồn</span>
        </div>
        ${evidence ? `<div class="evidence-strip"><span>truy xuất đúng <strong>${evidence.retrieval_hit ? "có" : "không"}</strong></span><span>token F1 <strong>${metric(evidence.token_f1, 3)}</strong></span><span>điểm đánh giá <strong>${safe(evidence.judge.score)}/5</strong></span></div>` : ""}
        ${payload.tool_calls?.length ? `<div class="tool-trace"><span>Công cụ Agent đã gọi</span><div class="tool-call-list">${payload.tool_calls.map((call) => {
          const args = Object.entries(call.args || {}).map(([key, value]) => `${key}: ${typeof value === "string" ? value : JSON.stringify(value)}`).join(" · ");
          return `<div class="tool-call"><strong>${safe(call.name)}</strong>${args ? ` · ${safe(args.slice(0, 180))}` : ""}</div>`;
        }).join("")}</div></div>` : ""}
        <button class="sources-toggle" data-sources="${sourceId}">Hiện các nguồn đã truy xuất ↓</button>
        <div class="sources-panel" id="${sourceId}">
          ${payload.sources.map((source, index) => `
            <article class="source-card">
              <div class="source-card-head"><strong>${index + 1}. ${safe(source.title)}</strong><span class="source-score">${metric(source.score, 3)}</span></div>
              <span>${safe(source.paper_id)}${source.published ? ` · ${safe(source.published)}` : ""}</span>
              <p>${safe(source.content)}</p>
            </article>`).join("")}
        </div>
      </div>
    </div>`);
  const toggle = messages.querySelector(`[data-sources="${sourceId}"]`);
  toggle.addEventListener("click", () => {
    const panel = document.querySelector(`#${sourceId}`);
    panel.classList.toggle("open");
    toggle.textContent = panel.classList.contains("open") ? "Ẩn các nguồn đã truy xuất ↑" : "Hiện các nguồn đã truy xuất ↓";
  });
  messages.scrollTop = messages.scrollHeight;
}

function addAssistantError(message) {
  document.querySelector("#chatMessages").insertAdjacentHTML("beforeend", `
    <div class="message assistant-message">
      <div class="message-avatar">!</div>
      <div class="message-body"><span class="message-author">Lỗi trình diễn</span><div class="message-bubble">${safe(message)}</div></div>
    </div>`);
}

async function submitChat(question) {
  if (!question.trim() || appState.isChatting) return;
  appState.isChatting = true;
  const button = document.querySelector("#sendButton");
  button.disabled = true;
  addUserMessage(question.trim());
  document.querySelector("#chatInput").value = "";
  const loadingId = addLoadingMessage();
  try {
    const payload = await fetchJson("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ state: appState.chatState, mode: appState.chatMode, question: question.trim(), top_k: 4 }),
    });
    document.querySelector(`#${loadingId}`)?.remove();
    addAssistantResult(payload);
  } catch (error) {
    document.querySelector(`#${loadingId}`)?.remove();
    addAssistantError(error.message);
  } finally {
    appState.isChatting = false;
    button.disabled = false;
    document.querySelector("#chatInput").focus();
  }
}

function bindEvents() {
  document.querySelectorAll(".nav-item").forEach((button) => button.addEventListener("click", () => activateTab(button.dataset.tab)));
  document.querySelectorAll("[data-go]").forEach((button) => button.addEventListener("click", () => activateTab(button.dataset.go)));
  document.querySelector("#refreshButton").addEventListener("click", loadDashboard);
  document.querySelectorAll("#qualityStateSwitch button").forEach((button) => button.addEventListener("click", () => renderQuality(button.dataset.state)));
  document.querySelector("#recordSearchForm").addEventListener("submit", (event) => { event.preventDefault(); loadRecords(); });
  document.querySelector("#recordState").addEventListener("change", loadRecords);
  document.querySelectorAll(".collection-option").forEach((button) => button.addEventListener("click", () => selectChatState(button.dataset.state)));
  document.querySelectorAll("#answerModeSwitch button").forEach((button) => button.addEventListener("click", () => selectAnswerMode(button.dataset.mode)));
  document.querySelector("#chatForm").addEventListener("submit", (event) => { event.preventDefault(); submitChat(document.querySelector("#chatInput").value); });
  document.querySelector("#chatInput").addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      document.querySelector("#chatForm").requestSubmit();
    }
  });
  document.querySelector("#chatInput").addEventListener("input", (event) => {
    event.target.style.height = "auto";
    event.target.style.height = `${Math.min(event.target.scrollHeight, 100)}px`;
  });
  document.querySelector("#clearChat").addEventListener("click", () => {
    document.querySelector("#chatMessages").innerHTML = `
      <div class="message assistant-message"><div class="message-avatar">P</div><div class="message-body"><span class="message-author">Princess</span><div class="message-bubble">Đã xóa cuộc trò chuyện. Hãy chọn trạng thái dữ liệu, chế độ trả lời và đặt câu hỏi mới.</div></div></div>`;
  });
}

async function loadDashboard() {
  const live = document.querySelector(".live-pill");
  document.querySelector("#liveLabel").textContent = "Đang tải tệp bằng chứng";
  live.classList.remove("connected");
  try {
    appState.data = await fetchJson("/api/overview");
    renderHero();
    renderFlow();
    renderStateComparison();
    renderQuality(appState.qualityState);
    renderEvents();
    renderArtifacts();
    renderSuggestions();
    selectChatState(appState.chatState);
    selectAnswerMode(appState.chatMode);
    await loadRecords();
    live.classList.add("connected");
    document.querySelector("#liveLabel").textContent = "Tệp bằng chứng trực tiếp";
  } catch (error) {
    document.querySelector("#liveLabel").textContent = "Không thể tải dữ liệu";
    showToast(error.message);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  bindEvents();
  loadDashboard();
});
