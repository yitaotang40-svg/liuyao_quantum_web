const castButton = document.querySelector("#castButton");
const backendSelect = document.querySelector("#backendSelect");
const modeButtons = document.querySelectorAll("[data-mode]");
const modePanels = document.querySelectorAll("[data-mode-panel]");
const manualDateTime = document.querySelector("#manualDateTime");
const manualSubmitButton = document.querySelector("#manualSubmitButton");
const manualYaoSelects = document.querySelectorAll("[data-manual-yao]");
const lifeName = document.querySelector("#lifeName");
const lifeCalendarType = document.querySelector("#lifeCalendarType");
const lifeBirthTimeLabel = document.querySelector("#lifeBirthTimeLabel");
const lifeBirthTime = document.querySelector("#lifeBirthTime");
const lifeLeapField = document.querySelector("#lifeLeapField");
const lifeLunarLeap = document.querySelector("#lifeLunarLeap");
const lifeGender = document.querySelector("#lifeGender");
const lifeSubmitButton = document.querySelector("#lifeSubmitButton");
const statusText = document.querySelector("#statusText");
const backendText = document.querySelector("#backendText");
const jobText = document.querySelector("#jobText");
const yaoList = document.querySelector("#yaoList");
const resultTitleText = document.querySelector(".result-title span");
const resultToolbarPrimary = document.querySelector(".result-toolbar span:first-child");
const resultToolbarSecondary = document.querySelector(".result-toolbar span:last-child");
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

function setResultChrome(mode) {
  const isLife = mode === "life";
  resultPanel.classList.toggle("life-terminal", isLife);
  resultToolbarPrimary.textContent = isLife ? "LIFE KLINE" : "Measurement result";
  resultToolbarSecondary.textContent = isLife ? "OHLC · 1Y" : "Bottom to top";
}

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
  setResultChrome("quantum");
  resultPanel.classList.add("is-waiting");
  waitHint.hidden = false;
  resultTitleText.textContent = "等待量子结果：";
  yaoList.classList.remove("chart-mode", "life-mode");
  yaoList.innerHTML = "";
  yaoNames.forEach((name) => {
    const item = document.createElement("li");
    item.className = "waiting-row";
    item.innerHTML = `<span class="yao-label">${name}：</span><span class="waiting-pill"></span>`;
    yaoList.appendChild(item);
  });
}

function renderError(job, mode = "quantum") {
  setResultChrome(mode);
  resultPanel.classList.remove("is-waiting");
  waitHint.hidden = true;
  resultTitleText.textContent = mode === "life" ? "人生K线错误：" : "运行结果：";
  yaoList.classList.remove("chart-mode", "life-mode");
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
  setResultChrome("quantum");
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

function numericValue(value, fallback = 0) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

const LIFE_CHART = {
  width: 1120,
  height: 430,
  left: 56,
  right: 74,
  top: 34,
  bottom: 58,
};

function buildLifeChartSvg(points) {
  const { width, height, left, right, top, bottom } = LIFE_CHART;
  const innerWidth = width - left - right;
  const innerHeight = height - top - bottom;
  const highs = points.map((point) => numericValue(point.high, point.score));
  const lows = points.map((point) => numericValue(point.low, point.score));
  const maxValue = Math.max(100, ...highs);
  const minValue = Math.min(0, ...lows);
  const spread = Math.max(1, maxValue - minValue);
  const y = (value) => top + ((maxValue - value) / spread) * innerHeight;
  const step = innerWidth / Math.max(1, points.length - 1);
  const bodyWidth = Math.max(3, Math.min(8, step * 0.58));
  const gridLines = [0, 20, 40, 60, 80, 100];

  const candles = points
    .map((point, index) => {
      const x = left + index * step;
      const open = numericValue(point.open, point.score);
      const close = numericValue(point.close, point.score);
      const high = numericValue(point.high, Math.max(open, close));
      const low = numericValue(point.low, Math.min(open, close));
      const isUp = close >= open;
      const color = isUp ? "#42be65" : "#fa4d56";
      const bodyTop = Math.min(y(open), y(close));
      const bodyHeight = Math.max(2, Math.abs(y(open) - y(close)));
      return `
        <g class="life-candle" data-age="${escapeHtml(point.age)}" data-year="${escapeHtml(point.year)}">
          <line x1="${x.toFixed(2)}" y1="${y(high).toFixed(2)}" x2="${x.toFixed(2)}" y2="${y(low).toFixed(2)}" stroke="${color}" stroke-width="1.4" />
          <rect x="${(x - bodyWidth / 2).toFixed(2)}" y="${bodyTop.toFixed(2)}" width="${bodyWidth.toFixed(2)}" height="${bodyHeight.toFixed(2)}" fill="${color}" />
        </g>`;
    })
    .join("");

  const xTicks = points
    .map((point, index) => {
      if (index % 10 !== 0 && index !== points.length - 1) return "";
      const x = left + index * step;
      return `<text x="${x.toFixed(2)}" y="${height - 18}" text-anchor="middle">${escapeHtml(point.year)}</text>`;
    })
    .join("");

  const grid = gridLines
    .map((value) => {
      const gy = y(value);
      return `
        <line x1="${left}" y1="${gy.toFixed(2)}" x2="${width - right}" y2="${gy.toFixed(2)}" />
        <text x="${width - right + 12}" y="${(gy + 4).toFixed(2)}">${value}</text>`;
    })
    .join("");

  return `
    <svg class="life-chart-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="人生K线图，可用鼠标沿横轴选择年份">
      <g class="life-grid">${grid}</g>
      <line class="life-axis" x1="${left}" y1="${height - bottom}" x2="${width - right}" y2="${height - bottom}" />
      <line class="life-axis" x1="${left}" y1="${top}" x2="${left}" y2="${height - bottom}" />
      <g class="life-candles">${candles}</g>
      <g class="life-crosshair" data-life-crosshair hidden>
        <line class="life-crosshair-line life-crosshair-x" x1="${left}" y1="${top}" x2="${left}" y2="${height - bottom}" />
        <line class="life-crosshair-line life-crosshair-y" x1="${left}" y1="${top}" x2="${width - right}" y2="${top}" />
        <circle class="life-selected-dot" cx="${left}" cy="${top}" r="5" />
        <rect class="life-axis-label-bg" x="${left - 28}" y="${height - bottom + 9}" width="64" height="24" rx="3" />
        <text class="life-axis-label" x="${left + 4}" y="${height - bottom + 26}" text-anchor="middle"></text>
        <rect class="life-price-label-bg" x="${width - right + 8}" y="${top - 12}" width="46" height="24" rx="3" />
        <text class="life-price-label" x="${width - right + 31}" y="${top + 5}" text-anchor="middle"></text>
      </g>
      <g class="life-xaxis">${xTicks}</g>
      <rect class="life-hit-area" x="${left}" y="${top}" width="${innerWidth}" height="${innerHeight}" />
    </svg>`;
}

function buildLifeYearRail(points) {
  return points
    .map((point, index) => {
      if (index % 5 !== 0 && index !== points.length - 1) return "";
      return `<button type="button" data-life-year-index="${index}">${escapeHtml(point.year)}</button>`;
    })
    .join("");
}

function lifePointText(point) {
  if (!point) return "-";
  const delta = numericValue(point.close) - numericValue(point.open);
  const sign = delta > 0 ? "+" : "";
  return `${escapeHtml(point.year)} · ${escapeHtml(point.ganZhi)} · ${escapeHtml(point.age)}岁 · ${sign}${delta}`;
}

function updateLifeSelection(card, points, index, lock = false) {
  if (!points.length) return;
  const safeIndex = Math.max(0, Math.min(points.length - 1, index));
  const point = points[safeIndex];
  const { width, height, left, right, top, bottom } = LIFE_CHART;
  const innerWidth = width - left - right;
  const innerHeight = height - top - bottom;
  const step = innerWidth / Math.max(1, points.length - 1);
  const x = left + safeIndex * step;
  const y = top + ((100 - numericValue(point.close, point.score)) / 100) * innerHeight;
  const labelX = Math.max(left + 32, Math.min(width - right - 32, x));
  const priceY = Math.max(top + 12, Math.min(height - bottom - 12, y));
  const crosshair = card.querySelector("[data-life-crosshair]");

  if (lock) {
    card.dataset.lockedIndex = String(safeIndex);
  }
  card.querySelectorAll("[data-life-selected]").forEach((node) => {
    const key = node.dataset.lifeSelected;
    const value = {
      year: point.year,
      age: `${point.age}岁`,
      ganZhi: point.ganZhi,
      daYun: point.daYun,
      open: point.open,
      high: point.high,
      low: point.low,
      close: point.close,
      score: point.score,
      delta: lifePointText(point),
      reason: point.reason,
    }[key];
    node.textContent = value ?? "-";
  });
  card.querySelectorAll("[data-life-year-index]").forEach((button) => {
    button.classList.toggle("is-selected", Number(button.dataset.lifeYearIndex) === safeIndex);
  });

  if (!crosshair) return;
  crosshair.removeAttribute("hidden");
  crosshair.querySelector(".life-crosshair-x").setAttribute("x1", x.toFixed(2));
  crosshair.querySelector(".life-crosshair-x").setAttribute("x2", x.toFixed(2));
  crosshair.querySelector(".life-crosshair-y").setAttribute("y1", y.toFixed(2));
  crosshair.querySelector(".life-crosshair-y").setAttribute("y2", y.toFixed(2));
  crosshair.querySelector(".life-selected-dot").setAttribute("cx", x.toFixed(2));
  crosshair.querySelector(".life-selected-dot").setAttribute("cy", y.toFixed(2));
  crosshair.querySelector(".life-axis-label-bg").setAttribute("x", (labelX - 32).toFixed(2));
  crosshair.querySelector(".life-axis-label").setAttribute("x", labelX.toFixed(2));
  crosshair.querySelector(".life-axis-label").textContent = point.year;
  crosshair.querySelector(".life-price-label-bg").setAttribute("y", (priceY - 12).toFixed(2));
  crosshair.querySelector(".life-price-label").setAttribute("y", (priceY + 5).toFixed(2));
  crosshair.querySelector(".life-price-label").textContent = point.close;
}

function setupLifeChartInteraction(card, points) {
  if (!points.length) return;
  const svg = card.querySelector(".life-chart-svg");
  const yearButtons = card.querySelectorAll("[data-life-year-index]");
  const indexFromEvent = (event) => {
    const rect = svg.getBoundingClientRect();
    const rawX = ((event.clientX - rect.left) / rect.width) * LIFE_CHART.width;
    const step = (LIFE_CHART.width - LIFE_CHART.left - LIFE_CHART.right) / Math.max(1, points.length - 1);
    return Math.round((rawX - LIFE_CHART.left) / step);
  };
  const peakIndex = points.reduce(
    (bestIndex, point, index) => (numericValue(point.high) > numericValue(points[bestIndex]?.high) ? index : bestIndex),
    0,
  );

  updateLifeSelection(card, points, peakIndex, true);
  svg.addEventListener("pointermove", (event) => updateLifeSelection(card, points, indexFromEvent(event)));
  svg.addEventListener("click", (event) => updateLifeSelection(card, points, indexFromEvent(event), true));
  svg.addEventListener("pointerleave", () => updateLifeSelection(card, points, Number(card.dataset.lockedIndex || peakIndex)));
  yearButtons.forEach((button) => {
    button.addEventListener("click", () => updateLifeSelection(card, points, Number(button.dataset.lifeYearIndex), true));
  });
}

function renderLifeAnalysisCards(analysis) {
  const cards = [
    ["命理总评", analysis.summary, analysis.summaryScore],
    ["性格", analysis.personality, analysis.personalityScore],
    ["事业", analysis.industry, analysis.industryScore],
    ["财富", analysis.wealth, analysis.wealthScore],
    ["婚姻", analysis.marriage, analysis.marriageScore],
    ["健康", analysis.health, analysis.healthScore],
    ["六亲", analysis.family, analysis.familyScore],
    ["发展风水", analysis.fengShui, analysis.fengShuiScore],
    ["币圈交易", analysis.crypto, analysis.cryptoScore],
  ];
  return cards
    .map(([title, content, score]) => {
      const displayScore = numericValue(score, 5);
      const width = Math.max(0, Math.min(10, displayScore)) * 10;
      return `
        <article class="life-analysis-card">
          <div class="life-card-head">
            <strong>${escapeHtml(title)}</strong>
            <span>${escapeHtml(displayScore)} / 10</span>
          </div>
          <p>${escapeHtml(content)}</p>
          <div class="life-score"><i style="width:${width}%"></i></div>
        </article>`;
    })
    .join("");
}

function renderLifeWaiting() {
  setResultChrome("life");
  resultPanel.classList.add("is-waiting");
  waitHint.hidden = false;
  resultTitleText.textContent = "人生K线 · 生成中";
  yaoList.innerHTML = "";
  yaoList.classList.add("life-mode");
  yaoList.classList.remove("chart-mode");
  const item = document.createElement("li");
  item.className = "life-kline-card life-loading-card";
  item.innerHTML = `
    <div class="life-tv-header">
      <div class="life-symbol-block">
        <span>LIFEKLINE</span>
        <strong>正在生成</strong>
        <em>1Y</em>
      </div>
      <div class="life-ohlc-strip">
        <span>Y <strong>--</strong></span>
        <span>O <strong>--</strong></span>
        <span>H <strong>--</strong></span>
        <span>L <strong>--</strong></span>
        <span>C <strong>--</strong></span>
      </div>
    </div>
    <div class="life-trading-layout">
      <section class="life-chart-panel" aria-label="人生K线生成中">
        <div class="life-chart-toolbar">
          <span>loading market series</span>
          <button type="button" class="is-active">1Y</button>
          <button type="button">OHLC</button>
          <button type="button">Bazi</button>
        </div>
        <div class="life-chart-loader" aria-hidden="true">
          <span></span><span></span><span></span><span></span><span></span><span></span>
          <span></span><span></span><span></span><span></span><span></span><span></span>
        </div>
      </section>
      <aside class="life-side-panel">
        <div><span>四柱</span><strong class="life-skeleton-text"></strong></div>
        <div><span>大运</span><strong class="life-skeleton-text short"></strong></div>
        <div><span>选中年份</span><strong>等待后端生成 OHLC</strong></div>
      </aside>
    </div>`;
  yaoList.appendChild(item);
}

function renderLifeKline(result) {
  setResultChrome("life");
  resultPanel.classList.remove("is-waiting");
  waitHint.hidden = true;
  yaoList.innerHTML = "";
  yaoList.classList.add("life-mode");
  yaoList.classList.remove("chart-mode");
  resultTitleText.textContent = "人生K线 · 年线图";

  const birth = result.birthInfo || {};
  const analysis = result.analysis || {};
  const points = Array.isArray(result.chartData) ? result.chartData : [];
  const dayun = birth.dayun || {};
  const bazi = Array.isArray(birth.bazi) ? birth.bazi : analysis.bazi || [];
  const peak = points.reduce((best, point) => (numericValue(point.high) > numericValue(best?.high) ? point : best), null);
  const first = points[0] || {};
  const last = points[points.length - 1] || {};
  const item = document.createElement("li");
  item.className = "life-kline-card";
  item.innerHTML = `
    <div class="life-tv-header">
      <div class="life-symbol-block">
        <span>LIFEKLINE</span>
        <strong>${escapeHtml(birth.name || "人生K线")}</strong>
        <em>1Y</em>
      </div>
      <div class="life-ohlc-strip" aria-live="polite">
        <span>Y <strong data-life-selected="year">${escapeHtml(first.year || "-")}</strong></span>
        <span>O <strong data-life-selected="open">${escapeHtml(first.open || "-")}</strong></span>
        <span>H <strong data-life-selected="high">${escapeHtml(first.high || "-")}</strong></span>
        <span>L <strong data-life-selected="low">${escapeHtml(first.low || "-")}</strong></span>
        <span>C <strong data-life-selected="close">${escapeHtml(first.close || "-")}</strong></span>
        <span>Score <strong data-life-selected="score">${escapeHtml(first.score || "-")}</strong></span>
      </div>
    </div>
    <div class="life-trading-layout">
      <section class="life-chart-panel" aria-label="人生K线图表">
        <div class="life-chart-toolbar">
          <span>${escapeHtml(first.year || "-")} - ${escapeHtml(last.year || "-")}</span>
          <button type="button" class="is-active">1Y</button>
          <button type="button">OHLC</button>
          <button type="button">Bazi</button>
        </div>
        ${buildLifeChartSvg(points)}
        <div class="life-year-rail" aria-label="选择年份">${buildLifeYearRail(points)}</div>
      </section>
      <aside class="life-side-panel">
        <div>
          <span>四柱</span>
          <strong>${bazi.map(escapeHtml).join("　")}</strong>
        </div>
        <div>
          <span>大运</span>
          <strong>${escapeHtml(dayun.direction || "-")}，${escapeHtml(dayun.startAge || "-")}岁起运，首运 ${escapeHtml(
            dayun.firstDaYun || "-",
          )}</strong>
        </div>
        <div>
          <span>峰值</span>
          <strong>${peak ? `${escapeHtml(peak.year)}年 ${escapeHtml(peak.ganZhi)}，${escapeHtml(peak.age)}岁` : "-"}</strong>
        </div>
        <div class="life-selected-panel">
          <span>选中年份</span>
          <strong data-life-selected="delta">${first.year ? lifePointText(first) : "-"}</strong>
          <p><b data-life-selected="daYun">${escapeHtml(first.daYun || "-")}</b> · <b data-life-selected="ganZhi">${escapeHtml(
            first.ganZhi || "-",
          )}</b></p>
          <p data-life-selected="reason">${escapeHtml(first.reason || "移动鼠标或点击横轴选择年份。")}</p>
        </div>
      </aside>
    </div>
    <div class="life-crypto-badges">
      <span>暴富流年：${escapeHtml(analysis.cryptoYear || "待定")}</span>
      <span>交易风格：${escapeHtml(analysis.cryptoStyle || "稳健低杠杆")}</span>
    </div>
    <div class="life-analysis-grid">${renderLifeAnalysisCards(analysis)}</div>`;
  yaoList.appendChild(item);
  setupLifeChartInteraction(item, points);
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

function setLifeControls(busy) {
  lifeSubmitButton.disabled = busy;
  lifeSubmitButton.classList.toggle("is-busy", busy);
  lifeName.disabled = busy;
  lifeCalendarType.disabled = busy;
  lifeBirthTime.disabled = busy;
  lifeLunarLeap.disabled = busy;
  lifeGender.disabled = busy;
  lifeSubmitButton.innerHTML = busy
    ? `<span class="button-mark" aria-hidden="true"></span><span>生成中</span>`
    : `<span class="button-mark life" aria-hidden="true"></span><span>生成人生K线</span>`;
}

function updateLifeCalendarFields() {
  const isLunar = lifeCalendarType.value === "lunar";
  lifeBirthTimeLabel.textContent = isLunar ? "农历出生日期时间" : "阳历出生日期时间";
  lifeLeapField.hidden = !isLunar;
  if (!isLunar) {
    lifeLunarLeap.checked = false;
  }
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

async function submitLifeKline() {
  if (isRunning || currentRunId) {
    showWaitToast("IBM 作业运行中，完成后再生成人生K线");
    return;
  }

  if (!lifeBirthTime.value) {
    showWaitToast(`请填写${lifeCalendarType.value === "lunar" ? "农历" : "阳历"}出生日期时间`);
    return;
  }

  setLifeControls(true);
  panelTitle.textContent = "生成中";
  liveDot.className = "live-dot busy";
  statusText.textContent = "人生K线生成中";
  backendText.textContent = "Gemini API";
  jobText.textContent = "life-kline";
  renderLifeWaiting();

  try {
    const response = await fetch(`${apiBase}/api/life-kline`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: lifeName.value,
        calendar_type: lifeCalendarType.value,
        birth_time: lifeBirthTime.value,
        lunar_is_leap: lifeLunarLeap.checked,
        gender: lifeGender.value,
      }),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "人生K线生成失败");
    }
    setStatus({
      status: "DONE",
      status_label: "完成",
      backend: "Gemini API",
      job_id: "life-kline",
    });
    renderLifeKline(data.result);
  } catch (error) {
    setStatus({ status: "ERROR", status_label: "出错", backend: "Gemini API", job_id: "-" });
    renderError({ error: error instanceof TypeError ? backendUnavailableMessage : String(error) }, "life");
  } finally {
    setLifeControls(false);
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
lifeSubmitButton.addEventListener("click", submitLifeKline);
lifeCalendarType.addEventListener("change", updateLifeCalendarFields);

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
updateLifeCalendarFields();
setManualControls(false);
setLifeControls(false);
setMode("quantum");
