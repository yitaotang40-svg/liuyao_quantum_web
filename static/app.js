const castButton = document.querySelector("#castButton");
const backendSelect = document.querySelector("#backendSelect");
const modeButtons = document.querySelectorAll("[data-mode]");
const modePanels = document.querySelectorAll("[data-mode-panel]");
const manualDateTime = document.querySelector("#manualDateTime");
const manualSubmitButton = document.querySelector("#manualSubmitButton");
const manualYaoSelects = document.querySelectorAll("[data-manual-yao]");
const statusText = document.querySelector("#statusText");
const backendText = document.querySelector("#backendText");
const jobText = document.querySelector("#jobText");
const yaoList = document.querySelector("#yaoList");
const resultTitleText = document.querySelector(".result-title span");
const panelTitle = document.querySelector("#panelTitle");
const liveDot = document.querySelector("#liveDot");
const resultPanel = document.querySelector(".result-panel");
const waitHint = document.querySelector("#waitHint");
const toast = document.querySelector("#toast");
const confirmModal = document.querySelector("#confirmModal");
const confirmCancel = document.querySelector("#confirmCancel");
const confirmSubmit = document.querySelector("#confirmSubmit");

const configuredApiBase = (window.LIUYAO_API_BASE || "").replace(/\/$/, "");
const pageIsLocalBackend =
  window.location.hostname === "localhost" ||
  window.location.hostname === "127.0.0.1" ||
  window.location.hostname === "::1";
const pageNeedsLocalBackend =
  window.location.protocol === "file:" ||
  window.location.hostname.endsWith("github.io");
const apiBase = pageIsLocalBackend ? "" : configuredApiBase || (pageNeedsLocalBackend ? "http://127.0.0.1:8765" : "");
const backendUnavailableMessage =
  "后端没有连接。请先启动本地 Python 后端，或在 static/config.js 配置云端 API 地址。";
let pollTimer = null;
let currentRunId = null;
let isRunning = false;
let toastTimer = null;
const yaoNames = ["初爻", "二爻", "三爻", "四爻", "五爻", "上爻"];

function pad2(value) {
  return String(value).padStart(2, "0");
}

function formatDateTimeLocal(date) {
  return `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}T${pad2(
    date.getHours(),
  )}:${pad2(date.getMinutes())}`;
}

function setStatus(job) {
  statusText.textContent = job.status_label || job.status || "等待中";
  backendText.textContent = job.backend || "-";
  jobText.textContent = job.job_id || "-";
  panelTitle.textContent = job.status === "DONE" ? "已完成" : job.status === "ERROR" ? "需要重试" : "运行中";
  liveDot.className = `live-dot ${
    job.status === "DONE" ? "done" : job.status === "ERROR" ? "error" : "busy"
  }`;
}

function renderWaiting() {
  resultPanel.classList.add("is-waiting");
  waitHint.hidden = false;
  resultTitleText.textContent = "等待量子结果：";
  yaoList.classList.remove("chart-mode");
  yaoList.innerHTML = "";
  yaoNames.forEach((name) => {
    const item = document.createElement("li");
    item.className = "waiting-row";
    item.innerHTML = `<span class="yao-label">${name}：</span><span class="waiting-pill"></span>`;
    yaoList.appendChild(item);
  });
}

function renderError(job) {
  resultPanel.classList.remove("is-waiting");
  waitHint.hidden = true;
  resultTitleText.textContent = "运行结果：";
  yaoList.classList.remove("chart-mode");
  yaoList.innerHTML = "";
  const item = document.createElement("li");
  item.className = "empty";
  item.textContent = job.error || "起卦失败";
  yaoList.appendChild(item);
}

function escapeHtml(value = "") {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function lineMarkup(kind) {
  if (kind === "yang") {
    return `<span class="hex-line yang" aria-label="阳爻"><i></i></span>`;
  }
  return `<span class="hex-line yin" aria-label="阴爻"><i></i><i></i></span>`;
}

function rowMarkup(row) {
  const hidden = row.hidden_spirit || "";
  const pos = row.position_label ? `<span class="position-tag">${escapeHtml(row.position_label)}</span>` : "";
  const change = row.change_mark ? `<span class="change-mark">${escapeHtml(row.change_mark)}</span>` : "";
  const quantum = row.quantum || {};
  return `
    <div class="chart-row">
      <div class="spirit-cell">${escapeHtml(row.six_spirit)}</div>
      <div class="hidden-cell">${escapeHtml(hidden)}</div>
      <div class="hex-cell">
        <span class="line-text">${escapeHtml(row.ben.text)}</span>
        ${lineMarkup(row.ben.line)}
      </div>
      <div class="mark-cell">${pos}${change}</div>
      <div class="hex-cell">
        <span class="line-text">${escapeHtml(row.bian.text)}</span>
        ${lineMarkup(row.bian.line)}
      </div>
      <div class="quantum-cell">
        <strong>${escapeHtml(quantum.bits || "-")}</strong>
        <span>${escapeHtml(quantum.faces || "")}</span>
        <em>${escapeHtml(quantum.yao_type || "")}</em>
      </div>
    </div>`;
}

function renderChart(result) {
  const chart = result.chart;
  const item = document.createElement("li");
  item.className = "reading-card";
  const pillars = chart.time.pillars;
  const shensha = chart.time.shensha;
  const parts = chart.time.date_parts || {};
  const hasDateParts = Number.isInteger(parts.year);
  const dateLabel = hasDateParts
    ? `<span>${escapeHtml(chart.time.solar_term)}：</span><strong>${parts.year}年${pad2(parts.month)}月${pad2(
        parts.day,
      )}日${pad2(parts.hour)}时${pad2(parts.minute)}分</strong>`
    : `<strong>${escapeHtml(chart.time.date_label)}</strong>`;
  const resultHead = result.backend === "手动排盘" ? "手动输入" : "量子结果";
  item.innerHTML = `
    <div class="time-board">
      <div class="date-line">${dateLabel}</div>
      <div>
        <span>干支：</span>${escapeHtml(pillars.year)}年
        <span>${escapeHtml(pillars.month)}月</span>
        <span>${escapeHtml(pillars.day)}日</span>
        <span>${escapeHtml(pillars.hour)}时</span>
        <b>（日空：${escapeHtml(chart.time.xunkong)}）</b>
      </div>
      <div>
        <span>神煞：</span>驿马-${escapeHtml(shensha.yima)}
        <span>桃花-${escapeHtml(shensha.taohua)}</span>
        <span>日禄-${escapeHtml(shensha.rilu)}</span>
        <span>贵人-${escapeHtml(shensha.guiren)}</span>
      </div>
    </div>

    <div class="gua-heading">
      <span>${escapeHtml(chart.ben.palace)}宫：${escapeHtml(chart.ben.name)}</span>
      <span>${escapeHtml(chart.bian.palace)}宫：${escapeHtml(chart.bian.name)}</span>
    </div>

    <div class="chart-grid" role="table" aria-label="六爻排盘">
      <div class="chart-head">六神</div>
      <div class="chart-head">伏神</div>
      <div class="chart-head">本卦</div>
      <div class="chart-head">动</div>
      <div class="chart-head">变卦</div>
      <div class="chart-head">${escapeHtml(resultHead)}</div>
      ${chart.rows_top_to_bottom.map(rowMarkup).join("")}
    </div>`;
  yaoList.appendChild(item);
}

function renderResult(result) {
  resultPanel.classList.remove("is-waiting");
  waitHint.hidden = true;
  yaoList.innerHTML = "";
  resultTitleText.textContent = "装卦结果：";
  if (result.chart) {
    yaoList.classList.add("chart-mode");
    renderChart(result);
    return;
  }
  yaoList.classList.remove("chart-mode");
  result.yao_records.forEach((record) => {
    const item = document.createElement("li");
    item.className = "yao-row";

    const label = document.createElement("span");
    label.className = "yao-label";
    label.textContent = `${record.yao_name}：`;

    const pill = document.createElement("span");
    pill.className = `yao-pill${record.moving ? " moving" : ""}`;
    pill.textContent = record.yao_type;

    item.append(label, pill);
    if (record.moving) {
      const marker = document.createElement("span");
      marker.className = "moving-tag";
      marker.textContent = "动爻";
      item.appendChild(marker);
    }
    yaoList.appendChild(item);
  });
}

function setRunningControls(running, label = "起卦中") {
  castButton.disabled = false;
  castButton.classList.toggle("is-busy", running);
  castButton.setAttribute("aria-disabled", String(running));
  backendSelect.disabled = running;
  castButton.innerHTML = `<span class="button-mark" aria-hidden="true"></span><span>${label}</span>`;
}

function setManualControls(busy) {
  manualSubmitButton.disabled = busy;
  manualSubmitButton.classList.toggle("is-busy", busy);
  manualDateTime.disabled = busy;
  manualYaoSelects.forEach((select) => {
    select.disabled = busy;
  });
  manualSubmitButton.innerHTML = busy
    ? `<span class="button-mark" aria-hidden="true"></span><span>装卦中</span>`
    : `<span class="button-mark manual" aria-hidden="true"></span><span>手动装卦</span>`;
}

function setMode(mode) {
  modeButtons.forEach((button) => {
    const active = button.dataset.mode === mode;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-selected", String(active));
  });
  modePanels.forEach((panel) => {
    panel.hidden = panel.dataset.modePanel !== mode;
  });
}

function showWaitToast(message = "请等待当前这一卦完成") {
  toast.textContent = message;
  toast.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toast.hidden = true;
  }, 1800);
}

function showConfirmModal() {
  confirmModal.hidden = false;
  document.body.classList.add("modal-open");
  confirmSubmit.focus();
}

function hideConfirmModal() {
  confirmModal.hidden = true;
  document.body.classList.remove("modal-open");
}

async function pollJob(runId) {
  const response = await fetch(`${apiBase}/api/jobs/${runId}`);
  const job = await response.json();
  setStatus(job);

  if (job.status === "DONE") {
    clearInterval(pollTimer);
    pollTimer = null;
    currentRunId = null;
    isRunning = false;
    setRunningControls(false, "一键起卦");
    renderResult(job.result);
    return;
  }

  if (job.status === "ERROR") {
    clearInterval(pollTimer);
    pollTimer = null;
    currentRunId = null;
    isRunning = false;
    setRunningControls(false, "重新起卦");
    renderError(job);
  }
}

async function startPolling(runId) {
  clearInterval(pollTimer);
  currentRunId = runId;
  isRunning = true;
  setRunningControls(true, "一卦进行中");
  renderWaiting();
  await pollJob(runId);
  if (!pollTimer && isRunning) {
    pollTimer = setInterval(() => pollJob(runId), 2200);
  }
}

async function resumeActiveJob() {
  const response = await fetch(`${apiBase}/api/active-job`);
  const data = await response.json();
  if (data.job?.run_id) {
    setStatus(data.job);
    await startPolling(data.job.run_id);
  }
}

async function submitDivination() {
  if (isRunning || currentRunId) {
    showWaitToast();
    return;
  }

  clearInterval(pollTimer);
  isRunning = true;
  setRunningControls(true, "起卦中");
  panelTitle.textContent = "运行中";
  liveDot.className = "live-dot busy";
  statusText.textContent = "准备起卦";
  backendText.textContent = backendSelect.value || "自动选择";
  jobText.textContent = "-";
  renderWaiting();

  try {
    const response = await fetch(`${apiBase}/api/divinations`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ backend: backendSelect.value }),
    });
    const data = await response.json();
    if (!response.ok && response.status !== 409) {
      throw new Error(data.error || data.message || "提交失败");
    }
    if (response.status === 409) {
      showWaitToast(data.message || "请等待当前这一卦完成");
    }
    await startPolling(data.run_id);
  } catch (error) {
    clearInterval(pollTimer);
    pollTimer = null;
    currentRunId = null;
    isRunning = false;
    setRunningControls(false, "重新起卦");
    renderError({ error: error instanceof TypeError ? backendUnavailableMessage : String(error) });
  }
}

async function submitManualChart() {
  if (isRunning || currentRunId) {
    showWaitToast("IBM 作业运行中，完成后再手动排盘");
    return;
  }

  setManualControls(true);
  panelTitle.textContent = "排盘中";
  liveDot.className = "live-dot busy";
  statusText.textContent = "手动排盘";
  backendText.textContent = "手动输入";
  jobText.textContent = "-";

  try {
    const response = await fetch(`${apiBase}/api/manual-chart`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        cast_time: manualDateTime.value,
        yaos: Array.from(manualYaoSelects).map((select) => select.value),
      }),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "手动排盘失败");
    }
    setStatus({
      status: "DONE",
      status_label: "完成",
      backend: data.result?.backend || "手动排盘",
      job_id: data.result?.job_id || "manual",
    });
    renderResult(data.result);
  } catch (error) {
    setStatus({ status: "ERROR", status_label: "出错", backend: "手动输入", job_id: "-" });
    renderError({ error: error instanceof TypeError ? backendUnavailableMessage : String(error) });
  } finally {
    setManualControls(false);
  }
}

window.__submitLiuyaoFromModal = (event) => {
  event?.preventDefault();
  event?.stopImmediatePropagation?.();
  event?.stopPropagation();
  hideConfirmModal();
  submitDivination();
};

castButton.addEventListener("click", () => {
  if (isRunning || currentRunId) {
    showWaitToast();
    return;
  }

  showConfirmModal();
});

modeButtons.forEach((button) => {
  button.addEventListener("click", () => setMode(button.dataset.mode));
});

manualSubmitButton.addEventListener("click", submitManualChart);

confirmCancel.addEventListener("click", (event) => {
  event.preventDefault();
  event.stopPropagation();
  hideConfirmModal();
});

confirmSubmit.addEventListener("click", (event) => {
  event.preventDefault();
  event.stopPropagation();
  hideConfirmModal();
  submitDivination();
});

confirmModal.addEventListener("click", (event) => {
  const actionButton = event.target.closest("[data-confirm-action]");
  if (actionButton?.dataset.confirmAction === "submit") {
    event.preventDefault();
    event.stopPropagation();
    window.__submitLiuyaoFromModal(event);
    return;
  }
  if (actionButton?.dataset.confirmAction === "cancel") {
    event.preventDefault();
    event.stopPropagation();
    hideConfirmModal();
    return;
  }
  if (event.target === confirmModal) {
    hideConfirmModal();
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !confirmModal.hidden) {
    hideConfirmModal();
  }
});

resumeActiveJob().catch(() => {
  setRunningControls(false, "一键起卦");
});

manualDateTime.value = formatDateTimeLocal(new Date());
setManualControls(false);
setMode("quantum");
