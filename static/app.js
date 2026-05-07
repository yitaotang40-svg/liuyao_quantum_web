const castButton = document.querySelector("#castButton");
const backendSelect = document.querySelector("#backendSelect");
const statusText = document.querySelector("#statusText");
const backendText = document.querySelector("#backendText");
const jobText = document.querySelector("#jobText");
const yaoList = document.querySelector("#yaoList");
const panelTitle = document.querySelector("#panelTitle");
const liveDot = document.querySelector("#liveDot");
const resultPanel = document.querySelector(".result-panel");
const waitHint = document.querySelector("#waitHint");
const toast = document.querySelector("#toast");
const confirmModal = document.querySelector("#confirmModal");
const confirmCancel = document.querySelector("#confirmCancel");
const confirmSubmit = document.querySelector("#confirmSubmit");

const configuredApiBase = (window.LIUYAO_API_BASE || "").replace(/\/$/, "");
const pageNeedsLocalBackend =
  window.location.protocol === "file:" ||
  window.location.hostname.endsWith("github.io");
const apiBase = configuredApiBase || (pageNeedsLocalBackend ? "http://127.0.0.1:8765" : "");
const backendUnavailableMessage =
  "后端没有连接。请先启动本地 Python 后端，或在 static/config.js 配置云端 API 地址。";
let pollTimer = null;
let currentRunId = null;
let isRunning = false;
let toastTimer = null;
const yaoNames = ["初爻", "二爻", "三爻", "四爻", "五爻", "上爻"];

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
  yaoList.innerHTML = "";
  const item = document.createElement("li");
  item.className = "empty";
  item.textContent = job.error || "起卦失败";
  yaoList.appendChild(item);
}

function renderResult(result) {
  resultPanel.classList.remove("is-waiting");
  waitHint.hidden = true;
  yaoList.innerHTML = "";
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
