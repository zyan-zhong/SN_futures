const $ = (id) => document.getElementById(id);

const HORIZONS = {
  next_5m: { label: "5分钟", short: "5m" },
  next_15m: { label: "15分钟", short: "15m" },
  next_30m: { label: "30分钟", short: "30m" },
  next_hour: { label: "1小时", short: "1h" },
  tomorrow: { label: "下一交易日", short: "1d" },
  one_to_two_weeks: { label: "1-2周", short: "10d" },
  one_to_three_months: { label: "1-3个月", short: "60d" },
};

const LABELS = {
  active_retained: "保留现行模型",
  active_retained_until_candidate_passes_gate: "候选未过门槛，保留现行模型",
  candidate_failed_or_not_run: "候选未通过或尚未运行",
  candidate_ready_for_gate: "候选待晋级检查",
  requires_walk_forward: "需要真实滚动验证",
  stale: "行情偏旧",
  stale_or_missing_quote: "行情缺失或偏旧",
  fresh: "最新",
  fresh_or_recent: "较新",
  fallback: "备用源",
  "primary/cache": "主源或缓存",
  snapshot_cache: "本地快照缓存",
  missing_payload_error: "后端字段缺失",
  invalid_probability_payload: "概率字段异常",
  low_impact: "影响分不足",
  no_available_at: "缺少可用时间",
  event_window_mismatch: "不在本周期事件窗口",
  prediction_time_alignment_failed: "预测时间对齐失败",
  source_not_allowed: "来源暂不可用",
  duplicate_filtered: "重复事件已过滤",
  promotion: "模型晋级",
  cache: "缓存",
  feature_set_id: "特征集编号",
  neutral: "中性/方向优势不足",
  weak_up: "弱偏多",
  strong_up: "强偏多",
  weak_down: "弱偏空",
  strong_down: "强偏空",
  abstain: "暂不输出方向",
  bullish: "偏多",
  bearish: "偏空",
  volatility: "波动风险",
  mixed: "多空分歧",
  pass: "通过",
  guarded: "已守门",
  repaired: "已修复",
  queued: "排队中",
  running: "运行中",
  completed: "已完成",
  failed: "失败",
  not_found: "未找到任务",
  refresh_quotes: "刷新现价",
  refresh_prediction: "刷新预测",
  train_candidate: "训练候选",
  gpu_smoke_test: "GPU测试",
  walk_forward: "滚动验证",
  event_ablation: "事件消融",
  promotion_check: "晋级检查",
  position_scenario_refresh: "持仓情景刷新",
  cached_or_pending: "缓存口径或待生成",
  verify: "兑现验证",
  calibrate: "校准更新",
  backtest: "回测诊断",
  interval_growth_watch: "区间增长偏快",
  interval_growth_guarded: "区间增长已守门",
  interval_explosion_capped: "区间发散已压缩",
  center_flatline_watch: "中心线平直偏高",
  direction_price_conflict: "方向与价格路径分歧",
  first_step_jump_repaired: "第一步跳变已修复",
  flatline_path_micro_variation_added: "低波动路径已加入微扰",
  volatility_atr_event_guard: "波动率/ATR/事件联合守门",
  insufficient_chart_data: "图表数据不足",
};

const state = {
  cards: {},
  boot: {},
  selectedHorizon: "tomorrow",
  timer: null,
  lastTask: null,
};

function label(value, fallback = "--") {
  const key = String(value ?? "").trim();
  if (!key) return fallback;
  return LABELS[key] || key;
}

function sourceLabel(value, fallback = "--") {
  const text = String(value ?? "");
  if (!text) return fallback;
  if (text.includes("fallback")) return "备用源/缓存";
  if (text.includes("cache")) return "本地缓存";
  if (text.includes("real") || text.includes("primary")) return "真实行情源";
  return label(text, text);
}

function reasonLabel(value) {
  const text = String(value ?? "");
  if (!text) return "--";
  return text
    .split(/[|,，;；]/)
    .map((part) => label(part.trim(), part.trim()))
    .filter(Boolean)
    .join("；");
}

function eventTypeLabel(value) {
  const map = {
    macro_policy: "宏观政策",
    general_tin_news: "锡相关资讯",
    exchange_notice: "交易所公告",
    margin_change: "保证金调整",
    inventory_change: "库存变化",
    warehouse_receipt_change: "仓单变化",
    supply_disruption: "供应扰动",
    import_export: "进出口",
    downstream_demand: "下游需求",
    currency_move: "汇率/美元",
    risk_warning: "风险提示",
  };
  return map[value] || label(value, "--");
}

function escapeHTML(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function fmtPrice(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number.toLocaleString("zh-CN", { maximumFractionDigits: 0 }) : "--";
}

function fmtNumber(value, digits = 2) {
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(digits) : "--";
}

function fmtPct(value, digits = 1) {
  const number = Number(value);
  return Number.isFinite(number) ? `${(number * 100).toFixed(digits)}%` : "--";
}

function fmtTime(value) {
  if (!value) return "--";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString("zh-CN", { hour12: false });
}

function toNumber(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function pickNumber(obj, keys) {
  for (const key of keys) {
    const value = toNumber(obj?.[key]);
    if (value !== null) return value;
  }
  return null;
}

function setText(id, value) {
  const el = $(id);
  if (el) el.textContent = value ?? "--";
}

function showToast(message, kind = "info") {
  const el = $("toast");
  if (!el) return;
  el.textContent = message;
  el.dataset.kind = kind;
  el.classList.remove("hidden");
  window.clearTimeout(showToast._timer);
  showToast._timer = window.setTimeout(() => el.classList.add("hidden"), 4200);
}

function showAppError(title, detail) {
  const el = $("appError");
  if (!el) return;
  el.innerHTML = `<b>${escapeHTML(title)}</b><span>${escapeHTML(detail || "")}</span>`;
  el.classList.remove("hidden");
}

function clearAppError() {
  $("appError")?.classList.add("hidden");
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    cache: "no-store",
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    const text = await response.text().catch(() => "");
    throw new Error(`${path} ${response.status} ${text.slice(0, 160)}`);
  }
  return response.json();
}

function cardProbabilities(card) {
  const pUp = pickNumber(card, ["p_up", "prob_up"]);
  const pDown = pickNumber(card, ["p_down", "prob_down"]);
  const pNeutral = pickNumber(card, ["p_neutral", "prob_neutral"]);
  if ([pUp, pDown, pNeutral].some((value) => value === null)) {
    return { ok: false, pUp: null, pDown: null, pNeutral: null, reason: "missing_payload_error" };
  }
  const total = pUp + pDown + pNeutral;
  if (!Number.isFinite(total) || total <= 0) {
    return { ok: false, pUp: null, pDown: null, pNeutral: null, reason: "invalid_probability_payload" };
  }
  return { ok: true, pUp, pDown, pNeutral, reason: "" };
}

function validateCard(card) {
  const required = ["prediction_id", "model_version", "data_timestamp", "source_timestamp", "feature_set_id", "prediction_cache_key"];
  const missing = required.filter((key) => !card?.[key]);
  const probs = cardProbabilities(card);
  if (!probs.ok) missing.push(probs.reason);
  return missing;
}

function directionClass(value) {
  const text = String(value || "").toLowerCase();
  if (text.includes("偏多") || text.includes("上涨") || text.includes("up") || text.includes("bull")) return "bull";
  if (text.includes("偏空") || text.includes("下跌") || text.includes("down") || text.includes("bear")) return "bear";
  return "neutral";
}

function signalLabel(card) {
  return label(card.signal_strength || card.direction_label || card.direction_key, "待判断");
}

function renderProbabilityRows(probs) {
  if (!probs.ok) {
    return `<div class="contract-error">后端未返回完整上涨/下跌/中性概率，前端已拒绝使用假概率。</div>`;
  }
  const rows = [
    ["上涨", probs.pUp, "bull"],
    ["下跌", probs.pDown, "bear"],
    ["中性", probs.pNeutral, "neutral"],
  ];
  return rows
    .map(([rowLabel, value, cls]) => {
      const width = Math.max(0, Math.min(100, value * 100));
      return `<div class="prob-row ${cls}"><b>${rowLabel}</b><div class="bar"><i style="width:${width}%"></i></div><em>${fmtPct(value)}</em></div>`;
    })
    .join("");
}

function renderTag(text, tone = "") {
  return `<span class="tag ${tone}">${escapeHTML(text)}</span>`;
}

function renderTechnicalDetails(title, rows) {
  const items = rows
    .filter(([, value]) => value !== undefined && value !== null && value !== "")
    .map(([name, value]) => `<div><b>${escapeHTML(name)}</b><code>${escapeHTML(value)}</code></div>`)
    .join("");
  if (!items) return "";
  return `<details class="technical-details"><summary>${escapeHTML(title)}</summary>${items}</details>`;
}

function renderStatus(boot, live) {
  const runtime = boot.runtime_status || {};
  const watermark = boot.data_watermark || live.data_watermark || {};
  const quote = live.live_quote || watermark.live_quote || {};
  const session = live.trading_session || {};
  const price = quote.latest ?? watermark.latest_price;
  const quoteTime = quote.quote_time || watermark.latest_quote_time || watermark.source_timestamp;

  setText("appTitle", "SNInsightTerminal V3.8 沪锡期货预测分析终端");
  setText("subtitle", "方向优先 · 七周期独立 · 事件驱动 · 价格路径守门 · 受控晋级");
  setText("contractBox", `主力合约：${watermark.active_contract || quote.contract_code || "SN"}`);
  setText("sessionBox", `版本：${runtime.build_id || boot.version || "--"} · 进程：${runtime.active_pid || "--"} · 端口：${runtime.api_port || "--"}`);
  setText("livePrice", fmtPrice(price));
  setText("livePriceNote", `${quote.contract_code || watermark.active_contract || "SN"} · 行情 ${fmtTime(quoteTime)} · 抓取 ${fmtTime(watermark.fetch_timestamp)} · ${label(watermark.stale_status || "fresh")}`);
  setText("tradingState", session.is_trading ? "交易中" : label(session.trading_status || "非交易时段"));
  setText("tradingWindow", `${fmtTime(session.next_hour_start || session.current_start)} - ${fmtTime(session.next_hour_end || session.current_end)} ${session.note || ""}`);
  setText("qualityScore", fmtPct(watermark.quality_score ?? 0));
  setText("qualityNote", `来源：${sourceLabel(watermark.source || watermark.source_mode)} · 数据年龄：${Math.round(Number(watermark.data_age_seconds ?? 0))}秒 · ${watermark.using_fallback ? "备用源" : "主源/缓存"}`);

  const health = boot.model_health || {};
  setText("validationMode", label(health.validation_mode || "待验证"));
  setText("validationNote", health.health_reason || "真实兑现样本不足时不伪造命中率");
  setText("directionHit", health.direction_hit_rate == null ? "待积累" : fmtPct(health.direction_hit_rate));
  setText("directionCoverage", `强方向率 ${fmtPct(health.strong_signal_rate)} · 中性率 ${fmtPct(health.neutral_rate)}`);
  setText("rangeHit", health.interval_coverage_rate == null ? "待积累" : fmtPct(health.interval_coverage_rate));
  setText("centerError", `中枢误差 ${health.center_mae_pct == null ? "--" : fmtPct(health.center_mae_pct, 2)}`);
  setText("gateStatus", label(health.direction_gate_status || "受控"));
  setText("gateReason", reasonLabel(health.latest_gate_reason || "候选模型未通过晋级门槛前不替换现行模型"));
}

function cardTags(card, missing) {
  if (Array.isArray(card.display_tags) && card.display_tags.length) {
    return card.display_tags.map((item) => {
      if (!item || typeof item !== "object") return { text: String(item || ""), tone: "" };
      return {
        text: `${item.label || "标签"}：${item.value ?? "--"}`,
        tone: item.tone === "warning" ? "warn" : item.tone === "danger" ? "danger" : "",
      };
    });
  }
  const evidence = card.event_evidence || card.news_policy_impact || {};
  const pathWarnings = card.path_warnings || [];
  const tags = [
    `模型版本：${card.model_version || "--"}`,
    `预测编号：${card.prediction_id || "--"}`,
    `事件入模：${evidence.used_in_model_event_count ?? evidence.used_count ?? 0}`,
    `数据状态：${label(card.stale_status || card.data_status || "fresh")}`,
    `晋级状态：${label(card.promotion_result || "active_retained")}`,
  ];
  if (pathWarnings.length) tags.push(`路径告警：${pathWarnings.length}项`);
  if (missing.length) tags.push("字段不完整");
  return tags.map((text, index) => ({ text, tone: index === 5 ? "warn" : "" }));
}

function renderDecisionBlock(card) {
  const explanation = card.decision_explanation || {};
  const directionBasis = Array.isArray(explanation.direction_basis) ? explanation.direction_basis : [];
  const riskNotes = Array.isArray(card.risk_notes) ? card.risk_notes : [];
  return `
    <div class="decision-block">
      <b>决策说明</b>
      <p>${escapeHTML(explanation.headline || "当前方向证据仍在验证中，系统维持审慎解释。")}</p>
      <p>${escapeHTML((directionBasis[0] || explanation.event_basis || "暂无足够独立方向候选。"))}</p>
      <p>${escapeHTML(explanation.price_basis || card.path_guard_summary?.range_source || "价格区间由历史波动率、ATR、兑现误差和事件强度约束。")}</p>
      ${riskNotes.length ? `<p class="muted-text">${escapeHTML(riskNotes[0])}</p>` : ""}
    </div>`;
}

function renderCards(cards) {
  state.cards = cards || {};
  const box = $("predictionCards");
  if (!box) return;
  box.innerHTML = Object.entries(HORIZONS)
    .map(([key, meta]) => {
      const card = state.cards[key] || {};
      const probs = cardProbabilities(card);
      const missing = validateCard(card);
      const cls = directionClass(card.direction_label || card.signal_strength);
      const evidence = card.event_evidence || card.news_policy_impact || {};
      const gate = card.direction_gate || {};
      const live = card.live_quote || {};
      const tags = cardTags(card, missing);
      const warningTone = missing.length || (card.path_warnings || []).length ? "warning" : "";
      return `
        <article class="forecast-card ${cls} ${warningTone}">
          <div class="card-head">
            <span>${escapeHTML(meta.label)}</span>
            <strong>${escapeHTML(signalLabel(card))}</strong>
          </div>
          <div class="price-band">${fmtPrice(card.range_low)} - ${fmtPrice(card.range_high)}</div>
          <div class="center-line">价格中枢 ${fmtPrice(card.price_center)} · 最新价 ${fmtPrice(live.latest || card.anchor_price || card.anchor_close)} · 置信度 ${fmtPct((card.confidence_score ?? card.confidence ?? 0) / (Number(card.confidence_score ?? card.confidence) > 1 ? 100 : 1))}</div>
          ${renderProbabilityRows(probs)}
          <div class="tag-row">${tags.map((item) => renderTag(item.text || item, item.tone || "")).join("")}</div>
          ${missing.length ? `<div class="contract-error">字段缺失：${missing.map((item) => label(item, item)).join(" / ")}</div>` : ""}
          <div class="event-mini">事件证据：识别 ${evidence.recognized_event_count ?? 0} · 入模 ${evidence.used_in_model_event_count ?? 0} · 过滤 ${evidence.rejected_event_count ?? 0}</div>
          <div class="gate-note">方向闸门：${escapeHTML(label(gate.label || gate.status || "待验证"))} · ${escapeHTML(reasonLabel((gate.reasons || [card.validation_note || ""])[0] || ""))}</div>
          ${renderDecisionBlock(card)}
          <button class="detail-link" data-detail="${escapeHTML(key)}">为什么这样判断</button>
          ${renderTechnicalDetails("技术明细", [
            ["缓存键", card.prediction_cache_key],
            ["特征集编号", card.feature_set_id],
            ["数据时间", card.data_timestamp],
            ["行情水位", card.source_timestamp],
            ["原始晋级状态", card.promotion_result],
          ])}
        </article>`;
    })
    .join("");

  box.querySelectorAll("[data-detail]").forEach((btn) => {
    btn.addEventListener("click", () => showPredictionDetail(btn.getAttribute("data-detail")));
  });
}

function renderMatrix(cards, health) {
  const per = health?.per_horizon || {};
  const rows = Object.entries(HORIZONS)
    .map(([key, meta]) => {
      const card = cards[key] || {};
      const probs = cardProbabilities(card);
      const h = per[key] || {};
      return `
        <tr>
          <td>${escapeHTML(meta.label)}</td>
          <td class="${directionClass(card.direction_label || card.signal_strength)}">${escapeHTML(signalLabel(card))}</td>
          <td>${probs.ok ? fmtPct(probs.pUp) : "缺失"}</td>
          <td>${probs.ok ? fmtPct(probs.pDown) : "缺失"}</td>
          <td>${probs.ok ? fmtPct(probs.pNeutral) : "缺失"}</td>
          <td>${fmtPct(h.strong_signal_rate ?? card.strong_signal_rate)}</td>
          <td>${fmtPct(h.neutral_rate ?? probs.pNeutral)}</td>
          <td>${escapeHTML(card.model_version || "--")}</td>
          <td>${escapeHTML(label(card.promotion_result || "active_retained"))}</td>
        </tr>`;
    })
    .join("");
  $("multiHorizonMatrix").innerHTML = `
    <table>
      <thead><tr><th>周期</th><th>方向</th><th>上涨概率</th><th>下跌概率</th><th>中性概率</th><th>强信号率</th><th>中性率</th><th>模型版本</th><th>晋级状态</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
}

function showPredictionDetail(key) {
  const card = state.cards[key] || {};
  const drivers = Array.isArray(card.display_drivers) ? card.display_drivers : [];
  const candidates = Array.isArray(card.direction_candidate_scores) ? card.direction_candidate_scores : [];
  const gate = card.direction_gate || {};
  const priceGate = card.price_realism_gate || card.realistic_price_gate || {};
  const pathWarnings = card.path_warnings || [];
  const explanation = card.decision_explanation || {};
  const technicalTags = Array.isArray(card.technical_tags) ? card.technical_tags : [];
  const riskNotes = Array.isArray(card.risk_notes) ? card.risk_notes : [];
  $("driverDialogBody").innerHTML = `
    <h2>${escapeHTML(HORIZONS[key]?.label || key)} · ${escapeHTML(signalLabel(card))}</h2>
    <div class="diagnostic-item">预测编号：${escapeHTML(card.prediction_id || "--")}<br/>模型版本：${escapeHTML(card.model_version || "--")}<br/>数据时间：${fmtTime(card.data_timestamp)}<br/>行情水位：${fmtTime(card.source_timestamp)}</div>
    <h3>为什么这样判断</h3>
    <div class="diagnostic-item"><b>${escapeHTML(explanation.headline || "当前预测仍在验证中。")}</b><br/>方向依据：${escapeHTML((explanation.direction_basis || []).join("；") || "暂无足够方向候选。")}<br/>事件依据：${escapeHTML(explanation.event_basis || "暂无高权重事件。")}<br/>价格依据：${escapeHTML(explanation.price_basis || "历史波动率、ATR、兑现误差与事件权重共同约束。")}</div>
    <h3>方向闸门</h3>
    <div class="diagnostic-item">${escapeHTML(label(gate.label || gate.status || "--"))}<br/>${escapeHTML(reasonLabel((gate.reasons || []).join("；") || "暂无闸门说明"))}</div>
    <h3>价格路径守门</h3>
    <div class="diagnostic-item">锚定价 ${fmtPrice(priceGate.anchor_price || card.anchor_price)} · 调整中枢 ${fmtPrice(priceGate.adjusted_center || card.price_center)}<br/>${escapeHTML(reasonLabel((priceGate.reasons || pathWarnings || []).join("；") || card.price_band_reason || "未触发路径修复"))}</div>
    <h3>方向候选</h3>
    ${candidates.map((item) => `<div class="diagnostic-item"><b>${escapeHTML(item.name || "候选因子")}</b> · ${escapeHTML(label(item.direction_label || item.direction || "--"))} · 权重 ${fmtNumber(item.weight || 0, 3)}<br/>${escapeHTML(reasonLabel(item.evidence || item.explanation || ""))}</div>`).join("") || "<div class='diagnostic-item'>暂无候选证据。</div>"}
    <h3>核心驱动</h3>
    ${drivers.map((item) => `<div class="diagnostic-item"><b>${escapeHTML(item.name || "驱动因素")}</b> · ${escapeHTML(label(item.direction || "--"))} · ${escapeHTML(label(item.strength || "--"))}<br/>${escapeHTML(reasonLabel(item.explanation || ""))}</div>`).join("") || "<div class='diagnostic-item'>暂无驱动归因。</div>"}
    <h3>风险提示</h3>
    ${(riskNotes.length ? riskNotes : ["模型输出仅用于投研参考，存在误差、延迟和失效风险。"]).map((item) => `<div class="diagnostic-item">${escapeHTML(item)}</div>`).join("")}
    ${renderTechnicalDetails("技术明细", (technicalTags.length ? technicalTags.map((item) => [item.label, item.value]) : [
      ["缓存键", card.prediction_cache_key],
      ["特征集编号", card.feature_set_id],
      ["事件特征哈希", card.event_feature_hash],
      ["原始候选状态", card.active_or_candidate_status],
      ["原始晋级状态", card.promotion_result],
    ]))}
    <h3>合规提示</h3>
    <div class="diagnostic-item">本内容仅为沪锡期货量化投研参考，不构成投资建议。期货交易有风险，投资需谨慎。</div>`;
  $("driverDialog").showModal();
}

function chartValues(history, forecast) {
  const values = [];
  history.forEach((row) => {
    const close = toNumber(row.close);
    if (close !== null) values.push(close);
  });
  forecast.forEach((row) => {
    ["center", "lower", "upper", "pred_center", "pred_low", "pred_high"].forEach((key) => {
      const value = toNumber(row[key]);
      if (value !== null) values.push(value);
    });
  });
  return values;
}

function makePath(rows, xOf, yOf, valueKey) {
  const points = rows
    .map((row, index) => {
      const value = toNumber(row[valueKey]);
      return value === null ? null : [xOf(index), yOf(value)];
    })
    .filter(Boolean);
  return points.map(([x, y], index) => `${index ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
}

function renderSvgChart(container, payload) {
  const history = payload.history || [];
  const forecast = payload.forecast || [];
  const values = chartValues(history, forecast);
  if (!values.length) {
    container.innerHTML = `<div class="empty-state">暂无可绘制数据：${escapeHTML(label(payload.data_status || "insufficient_data"))}</div>`;
    return;
  }
  const width = 1100;
  const height = 400;
  const pad = { left: 58, right: 24, top: 28, bottom: 74 };
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = Math.max(max - min, 1);
  const total = Math.max(history.length + forecast.length - 1, 1);
  const xOf = (index) => pad.left + (index / total) * (width - pad.left - pad.right);
  const yOf = (value) => height - pad.bottom - ((value - min) / span) * (height - pad.top - pad.bottom);
  const forecastXOf = (index) => xOf(history.length + index);
  const splitX = xOf(Math.max(history.length - 1, 0));
  const historyPath = makePath(history, xOf, yOf, "close");
  const centerPath = makePath(forecast, forecastXOf, yOf, "center") || makePath(forecast, forecastXOf, yOf, "pred_center");
  const lowPath = makePath(forecast, forecastXOf, yOf, "lower") || makePath(forecast, forecastXOf, yOf, "pred_low");
  const highPath = makePath(forecast, forecastXOf, yOf, "upper") || makePath(forecast, forecastXOf, yOf, "pred_high");
  const ticks = [min, min + span / 2, max];
  const firstTs = history[0]?.ts || history[0]?.date || "";
  const lastForecast = forecast[forecast.length - 1] || {};
  const lastHistory = history[history.length - 1] || {};
  const lastTs = lastForecast.ts || lastForecast.date || lastHistory.ts || lastHistory.date || "";
  const warning = payload.interval_growth_warning ? `<text x="${splitX + 8}" y="${pad.top + 38}" fill="#f7ba1e" font-size="12">区间告警：${escapeHTML(label(payload.interval_growth_warning))}</text>` : "";
  container.innerHTML = `
    <svg class="fallback-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="历史价格与未来预测区">
      <defs>
        <linearGradient id="forecastArea" x1="0" x2="1">
          <stop offset="0" stop-color="rgba(22,184,255,0.12)" />
          <stop offset="1" stop-color="rgba(53,255,210,0.08)" />
        </linearGradient>
      </defs>
      <rect x="0" y="0" width="${width}" height="${height}" rx="18" fill="rgba(5,12,24,0.36)" />
      <rect x="${splitX}" y="${pad.top}" width="${width - splitX - pad.right}" height="${height - pad.top - pad.bottom}" fill="url(#forecastArea)" />
      ${ticks.map((tick) => `<line x1="${pad.left}" x2="${width - pad.right}" y1="${yOf(tick)}" y2="${yOf(tick)}" stroke="rgba(147,168,198,.16)" /><text x="10" y="${yOf(tick) + 4}" fill="#93a8c6" font-size="12">${fmtPrice(tick)}</text>`).join("")}
      <line x1="${splitX}" x2="${splitX}" y1="${pad.top}" y2="${height - pad.bottom}" stroke="#f7ba1e" stroke-dasharray="6 5" />
      <path d="${historyPath}" fill="none" stroke="#16b8ff" stroke-width="3" />
      <path d="${centerPath}" fill="none" stroke="#f7ba1e" stroke-width="3" />
      <path d="${lowPath}" fill="none" stroke="#00b42a" stroke-width="2" stroke-dasharray="6 5" />
      <path d="${highPath}" fill="none" stroke="#f53f3f" stroke-width="2" stroke-dasharray="6 5" />
      <text x="${pad.left}" y="${height - 42}" fill="#93a8c6" font-size="12">${escapeHTML(fmtTime(firstTs))}</text>
      <text x="${splitX + 8}" y="${pad.top + 18}" fill="#f7ba1e" font-size="12">未来预测区</text>
      ${warning}
      <text x="${width - 290}" y="${height - 42}" fill="#93a8c6" font-size="12">${escapeHTML(fmtTime(lastTs))}</text>
    </svg>`;
}

function renderECharts(container, payload, existing) {
  if (!window.echarts) return null;
  const rows = [
    ...(payload.history || []).map((row) => ({ date: row.ts || row.date, close: row.close })),
    ...(payload.forecast || []).map((row) => ({ date: row.ts || row.date, center: row.center ?? row.pred_center, low: row.lower ?? row.pred_low, high: row.upper ?? row.pred_high })),
  ];
  const chart = existing || window.echarts.init(container);
  chart.setOption({
    tooltip: { trigger: "axis" },
    legend: { textStyle: { color: "#93a8c6" }, data: ["真实价格", "预测中枢", "预测下沿", "预测上沿"] },
    grid: { left: 58, right: 24, top: 44, bottom: 48 },
    xAxis: { type: "category", data: rows.map((row) => row.date), axisLabel: { color: "#93a8c6" } },
    yAxis: { type: "value", scale: true, axisLabel: { color: "#93a8c6" }, splitLine: { lineStyle: { color: "rgba(147,168,198,.16)" } } },
    dataZoom: [{ type: "inside" }, { type: "slider", height: 18, bottom: 8 }],
    series: [
      { name: "真实价格", type: "line", smooth: true, data: rows.map((row) => row.close), lineStyle: { color: "#16b8ff", width: 2 } },
      { name: "预测中枢", type: "line", smooth: true, data: rows.map((row) => row.center), lineStyle: { color: "#f7ba1e", width: 2 } },
      { name: "预测下沿", type: "line", smooth: true, data: rows.map((row) => row.low), lineStyle: { color: "#00b42a", type: "dashed" } },
      { name: "预测上沿", type: "line", smooth: true, data: rows.map((row) => row.high), lineStyle: { color: "#f53f3f", type: "dashed" } },
    ],
  }, true);
  setTimeout(() => chart.resize(), 50);
  return chart;
}

let priceChartInstance = null;
async function renderPriceChart() {
  const horizon = $("horizonSelect").value;
  state.selectedHorizon = horizon;
  const payload = await api(`/api/charts/price-forecast?horizon=${encodeURIComponent(horizon)}`);
  setText("chartStatus", `${payload.horizon_label || HORIZONS[horizon]?.label || horizon} · ${label(payload.data_status || "ok")} · 预测 ${payload.forecast?.length || 0} 步 · ${payload.validation_note || ""}`);
  renderChartDiagnostics(payload);
  const container = $("priceChart");
  priceChartInstance = renderECharts(container, payload, priceChartInstance);
  if (!priceChartInstance) renderSvgChart(container, payload);
  await Promise.all([renderEventEvidence(horizon), renderModelEvidence(horizon)]);
}

function renderChartDiagnostics(payload) {
  const diag = payload.path_diagnostics || {};
  const box = $("chartDiagnostics");
  if (!box) return;
  box.innerHTML = `
    ${renderTag(`第一步跳变：${fmtPrice(diag.first_step_gap)}`)}
    ${renderTag(`区间增长：${fmtNumber(diag.interval_growth_rate, 2)}倍`, payload.interval_growth_warning ? "warn" : "")}
    ${renderTag(`中心线平直率：${fmtPct(diag.center_flatline_rate || 0)}`)}
    ${renderTag(`方向价格冲突：${diag.direction_price_conflict ? "是" : "否"}`, diag.direction_price_conflict ? "warn" : "")}
    ${renderTag(`区间策略：${payload.interval_policy || payload.price_band_policy || "历史波动率与事件权重约束"}`)}
    ${payload.interval_growth_warning ? renderTag(`区间告警：${label(payload.interval_growth_warning)}`, "warn") : ""}
    ${payload.event_shock_markers?.length ? renderTag(`关键事件：${payload.event_shock_markers.length}条`, "warn") : renderTag("关键事件：暂无重大冲击")}`;
}

async function renderEventEvidence(horizon) {
  const data = await api(`/api/events/evidence?horizon=${encodeURIComponent(horizon)}`);
  const reasons = Object.entries(data.rejected_reason_breakdown || {})
    .map(([key, value]) => `<span class="pill danger">${escapeHTML(label(key))}：${escapeHTML(value)}</span>`)
    .join("");
  const used = data.used_events || [];
  const rejected = data.rejected_events || [];
  $("eventEvidenceBox").innerHTML = `
    <div class="evidence-summary">
      <span>识别 ${data.recognized_event_count || 0}</span>
      <span>有效 ${data.valid_event_count || 0}</span>
      <span>入模 ${data.used_in_model_event_count || 0}</span>
      <span>过滤 ${data.rejected_event_count || 0}</span>
      <span>特征哈希已生成</span>
    </div>
    <div class="pill-row">${reasons || "<span class='pill'>暂无过滤异常</span>"}</div>
    ${used.slice(0, 8).map(renderEventItem).join("") || "<div class='diagnostic-item'>当前周期暂无入模事件；这会降低事件因子权重，但不会伪造新闻影响。</div>"}
    ${rejected.slice(0, 5).map((item) => renderEventItem(item, true)).join("")}
    ${renderTechnicalDetails("事件技术明细", [["事件特征哈希", data.event_feature_hash], ["预测时间", data.prediction_time]])}`;
}

function renderEventItem(item, rejected = false) {
  const eventId = item.event_id || "";
  return `
    <div class="diagnostic-item ${rejected ? "muted" : ""}">
      <b>${escapeHTML(item.title || "未命名事件")}</b>
      <small>${escapeHTML(item.source || "--")} · ${label(item.source_tier || "--")} · ${fmtTime(item.available_at || item.published_at)} · ${eventTypeLabel(item.event_type)}</small>
      <span>方向 ${label(item.direction_bias || "--")} · 影响 ${fmtNumber(item.impact_score || 0, 2)} · 置信 ${fmtNumber(item.direction_confidence || item.confidence || 0, 2)} · ${rejected ? `过滤原因：${label(item.rejected_reason || "--")}` : "已入模/可解释"}</span>
      <button class="detail-link" data-open-event="${escapeHTML(eventId)}">查看原文</button>
    </div>`;
}

async function openEvent(eventId) {
  if (!eventId) {
    showToast("缺少事件编号，不能绕过后端打开原文。", "warn");
    return;
  }
  const result = await api("/api/events/open", { method: "POST", body: JSON.stringify({ event_id: eventId }) });
  const url = result.final_open_url || result.url || result.canonical_url;
  if (result.ok && result.opened) {
    showToast("已通过系统默认浏览器打开原文。");
  } else if (result.ok && url) {
    window.open(url, "_blank", "noopener,noreferrer");
  } else {
    showToast(label(result.blocked_reason || result.reason || "原文链接暂不可用"), "warn");
  }
}

async function renderModelEvidence(horizon) {
  const [health, promotion, truth] = await Promise.all([
    api("/api/models/health"),
    api(`/api/model/promotion-report?horizon=${encodeURIComponent(horizon)}`),
    api("/api/diagnostics/system-truth"),
  ]);
  const per = health.per_horizon?.[horizon] || {};
  $("modelEvidenceBox").innerHTML = `
    <div class="diagnostic-item"><b>${escapeHTML(HORIZONS[horizon]?.label || horizon)}</b> · ${escapeHTML(per.model_version || "--")} · ${label(per.active_or_candidate_status || "active_retained")}</div>
    <div class="metric-grid">
      <span>强信号准确率 ${fmtPct(per.strong_signal_accuracy)}</span>
      <span>中性率 ${fmtPct(per.neutral_rate)}</span>
      <span>概率误差(Brier) ${per.brier_score ?? "--"}</span>
      <span>校准误差(ECE) ${per.expected_calibration_error ?? "--"}</span>
      <span>事件消融 ${per.event_ablation_gain ?? promotion.event_ablation_gain ?? "待验证"}</span>
      <span>路径连续 ${per.path_continuity_score ?? "待验证"}</span>
    </div>
    <div class="diagnostic-item">晋级结果：${label(promotion.promotion_result || "active_retained")}；候选状态：${label(promotion.candidate_status || "--")}；原因：${escapeHTML(promotion.promotion_reason || promotion.failure_reason || "未运行真实滚动验证，不替换现行模型。")}</div>
    <div class="diagnostic-item ${truth.system_truth_audit === "pass" ? "" : "danger"}">系统真实性审计：${label(truth.system_truth_audit || "--")} · 元数据 ${truth.metadata_audit?.ok ? "完整" : "缺失"} · 水位 ${label(truth.watermark_audit?.stale_status || "--")}</div>`;
}

async function renderNewsPolicy() {
  const data = await api("/api/news/policy-impact");
  const summary = data.summary || {};
  const events = data.events || [];
  setText("newsPolicySummary", `识别 ${data.recognized_event_count || 0} · 入模 ${data.used_in_model_event_count || 0} · 过滤 ${data.rejected_event_count || 0} · 权重 ${fmtNumber(summary.event_factor_weight || summary.confidence_weight || 0, 3)}`);
  $("newsPolicyBox").innerHTML = events.slice(0, 12).map(renderEventItem).join("") || `<div class="diagnostic-item">暂无沪锡相关可用事件；抓取失败不会清空历史事件。</div>`;
}

async function renderDataFreshness() {
  const [watermark, resources] = await Promise.all([api("/api/data/watermark"), api("/api/hardware/profile")]);
  setText("computeProfile", resources.current_profile || resources.recommended_profile || "CPU-Lite");
  setText("hardwareNote", `${resources.gpu_name || "CPU"} · ${resources.actual_training_device || resources.training_device || "cpu"}`);
  $("dataFreshnessBox").innerHTML = `
    <div class="diagnostic-item">最新价：${fmtPrice(watermark.latest_price)} · 行情时间：${fmtTime(watermark.latest_quote_time)} · 抓取：${fmtTime(watermark.fetch_timestamp)}</div>
    <div class="diagnostic-item">来源：${sourceLabel(watermark.source || watermark.source_mode)} · 数据年龄：${Math.round(Number(watermark.data_age_seconds || 0))}秒 · ${label(watermark.stale_status || "fresh")} · ${watermark.using_fallback ? "备用源" : "主源/缓存"}</div>
    <div class="diagnostic-item">算力：${escapeHTML(resources.current_profile || resources.recommended_profile || "--")} · CUDA：${resources.torch_cuda_available ? "可用" : "不可用"} · 最近GPU训练：${resources.last_training_used_gpu || resources.last_gpu_task_used ? "已使用" : "未使用/待验证"}</div>`;
}

async function renderAudit() {
  const audit = await api("/api/diagnostics/system-truth");
  $("truthAuditBox").innerHTML = `
    <div class="diagnostic-item ${audit.system_truth_audit === "pass" ? "" : "danger"}"><b>系统真实性</b>：${label(audit.system_truth_audit || "--")}</div>
    <div class="diagnostic-item">七周期隔离：概率重复 ${audit.model_independence_audit?.duplicate_direction_prob_hash ? "是" : "否"} · 中枢重复 ${audit.model_independence_audit?.duplicate_center_hash ? "是" : "否"} · 缓存重复 ${audit.model_independence_audit?.duplicate_prediction_cache_key ? "是" : "否"}</div>
    <div class="diagnostic-item">元数据：${audit.metadata_audit?.ok ? "完整" : "缺失"} · 水位：${audit.watermark_audit?.latest_price ? fmtPrice(audit.watermark_audit.latest_price) : "--"} · ${label(audit.watermark_audit?.stale_status || "--")}</div>
    <div class="diagnostic-item">模型训练：${label(audit.model_training_audit?.status || "--")} · 晋级门槛：${label(audit.promotion_gate_audit?.status || "--")} · 防未来函数：${label(audit.no_leakage_audit?.status || "--")}</div>`;
}

async function renderLearningBacktest() {
  const horizon = state.selectedHorizon || $("horizonSelect")?.value || "tomorrow";
  const [learning, backtest, health] = await Promise.all([
    api("/api/learning/status"),
    api(`/api/backtest/diagnostics?horizon=${encodeURIComponent(horizon)}`),
    api("/api/models/health"),
  ]);
  const learningBox = $("learningBox");
  if (learningBox) {
    learningBox.innerHTML = `
      <div class="diagnostic-item"><b>自动学习状态</b>：${learning.auto_scheduler_enabled ? "已开启" : "未开启"} · 当前运行：${learning.is_running ? "是" : "否"}</div>
      <div class="diagnostic-item">最近行情：${fmtTime(learning.last_market_refresh)} · 最近预测：${fmtTime(learning.last_prediction_refresh)} · 最近验证：${fmtTime(learning.last_verification)}</div>
      <div class="diagnostic-item">最近训练：${fmtTime(learning.last_training)} · 最近滚动验证：${fmtTime(learning.last_walk_forward)} · 最近事件消融：${fmtTime(learning.last_event_ablation)}</div>
      <div class="diagnostic-item">下一次预测：${fmtTime(learning.next_prediction_at)} · 下一次训练：${fmtTime(learning.next_training_at)}</div>
      <div class="diagnostic-item ${learning.last_failure ? "danger" : ""}">失败原因：${escapeHTML(learning.last_failure || "暂无失败记录")}<br/>说明：${escapeHTML(learning.learning_note || learning.rate_limit_state || "")}</div>
    `;
  }
  const per = health.per_horizon || {};
  const rows = Object.entries(HORIZONS).map(([key, meta]) => {
    const row = per[key] || {};
    return `<tr>
      <td>${escapeHTML(meta.label)}</td>
      <td>${fmtPct(row.directional_accuracy ?? row.direction_hit_rate)}</td>
      <td>${fmtPct(row.strong_signal_accuracy)}</td>
      <td>${fmtPct(row.neutral_rate)}</td>
      <td>${row.brier_score == null ? "--" : fmtNumber(row.brier_score, 4)}</td>
      <td>${row.expected_calibration_error == null ? "--" : fmtNumber(row.expected_calibration_error, 4)}</td>
      <td>${row.mae == null ? "--" : fmtNumber(row.mae, 2)}</td>
      <td>${row.rmse == null ? "--" : fmtNumber(row.rmse, 2)}</td>
      <td>${fmtPct(row.interval_coverage)}</td>
      <td>${escapeHTML(label(row.promotion_result || "active_retained"))}</td>
    </tr>`;
  }).join("");
  const backtestBox = $("backtestBox");
  if (backtestBox) {
    backtestBox.innerHTML = `
      <div class="diagnostic-item">当前周期：${escapeHTML(HORIZONS[horizon]?.label || horizon)} · 口径：${escapeHTML(backtest.walk_forward_status || "cached_or_pending")} · 晋级：${escapeHTML(label(backtest.promotion_result || "active_retained"))}</div>
      <table>
        <thead><tr><th>周期</th><th>方向命中</th><th>强信号命中</th><th>中性率</th><th>概率误差(Brier)</th><th>校准误差(ECE)</th><th>MAE</th><th>RMSE</th><th>区间覆盖</th><th>晋级状态</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
      <div class="diagnostic-item muted">缺失指标表示尚未生成真实 walk-forward/兑现验证结果，不使用伪指标填充。</div>
    `;
  }
}

async function renderPositionScenario(event) {
  if (event) event.preventDefault();
  const form = $("positionForm");
  const box = $("positionScenarioBox");
  if (!form || !box) return;
  const formData = new FormData(form);
  const payload = Object.fromEntries(formData.entries());
  box.innerHTML = `<div class="diagnostic-item">正在生成情景观察区...</div>`;
  try {
    const data = await api("/api/position/scenario", { method: "POST", body: JSON.stringify(payload) });
    const zones = Array.isArray(data.zones) ? data.zones : [];
    box.innerHTML = `
      <div class="diagnostic-item"><b>${escapeHTML(data.headline || "持仓情景已生成")}</b><br/>最新价：${fmtPrice(data.latest_price)} · 模型方向：${escapeHTML(label(data.model_direction || "--"))} · 置信度：${fmtPct((data.confidence_score || 0) / 100)}</div>
      ${zones.map((zone) => `<div class="diagnostic-item">
        <b>${escapeHTML(zone.name || "观察区")}</b>：${Array.isArray(zone.price_range) ? `${fmtPrice(zone.price_range[0])} - ${fmtPrice(zone.price_range[1])}` : "--"}<br/>
        依据：${escapeHTML(zone.basis || "")}<br/>
        风险：${escapeHTML(zone.risk_note || "")}
      </div>`).join("")}
      <div class="diagnostic-item">仅供投研参考，需独立决策。本模块不构成投资建议或交易指令。</div>
    `;
  } catch (error) {
    box.innerHTML = `<div class="diagnostic-item danger">持仓情景生成失败：${escapeHTML(error.message)}</div>`;
  }
}

async function renderReport() {
  const type = $("reportSelect").value;
  const report = await api(`/api/reports/content?type=${encodeURIComponent(type)}`);
  setText("reportContent", report.content || report.markdown || report.html || "暂无报告内容。");
}

function renderDebugInfo(boot) {
  const box = $("debugContent");
  if (!box) return;
  box.textContent = JSON.stringify({
    runtime: boot.runtime_status,
    watermark: boot.data_watermark,
    health: boot.model_health,
  }, null, 2);
}

async function refreshAll() {
  clearAppError();
  const [boot, live] = await Promise.all([api("/api/ui/bootstrap"), api("/api/predictions/live")]);
  state.boot = boot;
  renderStatus(boot, live);
  renderCards(live.cards || {});
  renderMatrix(live.cards || {}, boot.model_health || {});
  await Promise.all([
    renderPriceChart(),
    renderNewsPolicy(),
    renderDataFreshness(),
    renderAudit(),
    renderLearningBacktest(),
    renderReport(),
  ]);
  renderDebugInfo(boot);
}

function renderTaskStatus(status, type = "") {
  const box = $("taskStatusBox");
  if (!box) return;
  if (!status) {
    box.innerHTML = `<div class="task-empty">暂无后台任务。点击上方按钮后，这里会显示任务进度和失败原因。</div>`;
    return;
  }
  const missing = ["id", "status", "stage"].filter((key) => status[key] == null);
  const progress = Math.max(0, Math.min(1, Number(status.progress ?? 0)));
  const started = Number(status.started_at || 0);
  const finished = Number(status.finished_at || 0);
  const elapsed = started ? Math.max(0, ((finished || Date.now() / 1000) - started)).toFixed(1) : "--";
  box.innerHTML = `
    <div class="task-card ${status.status === "failed" ? "danger" : ""}">
      <div class="task-head"><b>${label(status.type || type)}</b><span>${label(status.status)}</span></div>
      <div class="task-progress"><i style="width:${progress * 100}%"></i></div>
      <div class="task-meta">任务编号：${escapeHTML(status.id || "--")} · 阶段：${escapeHTML(status.stage || "任务状态字段缺失")} · 进度：${Math.round(progress * 100)}% · 耗时：${elapsed}秒</div>
      ${status.error ? `<div class="contract-error">失败原因：${escapeHTML(status.error)}。系统已保留上一次成功预测。</div>` : ""}
      ${missing.length ? `<div class="contract-error">任务状态字段缺失：${missing.join(" / ")}</div>` : ""}
    </div>`;
}

async function runTask(type) {
  const buttons = ["quoteBtn", "refreshBtn", "retrainBtn", "gpuTestBtn", "walkForwardBtn", "eventAblationBtn"];
  buttons.forEach((id) => ($(id).disabled = true));
  try {
    renderTaskStatus({ id: "提交中", type, status: "queued", stage: "已提交后台任务", progress: 0.03 }, type);
    showToast(`已提交后台任务：${label(type)}`);
    const task = await api("/api/tasks/run", {
      method: "POST",
      body: JSON.stringify({ type, refresh_scope: "all", optimization_level: "auto", use_remote: true }),
    });
    state.lastTask = task;
    renderTaskStatus(task, type);
    for (let i = 0; i < 90; i += 1) {
      await new Promise((resolve) => setTimeout(resolve, 1200));
      const status = await api(`/api/tasks/status?id=${encodeURIComponent(task.id)}`);
      state.lastTask = status;
      renderTaskStatus(status, type);
      if (["completed", "failed", "not_found"].includes(status.status)) break;
    }
    await refreshAll();
  } catch (error) {
    showAppError("后台任务失败", `${error.message}。系统已保留上一次成功预测。`);
    renderTaskStatus({ id: state.lastTask?.id || "--", type, status: "failed", stage: "失败", progress: 1, error: error.message }, type);
  } finally {
    buttons.forEach((id) => ($(id).disabled = false));
  }
}

function bindEvents() {
  $("quoteBtn")?.addEventListener("click", () => runTask("refresh_quotes"));
  $("refreshBtn")?.addEventListener("click", () => runTask("refresh_prediction"));
  $("retrainBtn")?.addEventListener("click", () => runTask("train_candidate"));
  $("gpuTestBtn")?.addEventListener("click", () => runTask("gpu_smoke_test"));
  $("walkForwardBtn")?.addEventListener("click", () => runTask("walk_forward"));
  $("eventAblationBtn")?.addEventListener("click", () => runTask("event_ablation"));
  $("openApiBtn")?.addEventListener("click", () => window.open("/api/ui/bootstrap", "_blank", "noopener,noreferrer"));
  $("horizonSelect")?.addEventListener("change", renderPriceChart);
  $("reportSelect")?.addEventListener("change", renderReport);
  $("positionForm")?.addEventListener("submit", renderPositionScenario);
  document.addEventListener("click", (event) => {
    const target = event.target.closest("[data-open-event]");
    if (target) openEvent(target.getAttribute("data-open-event"));
  });
}

window.addEventListener("error", (event) => {
  showAppError("前端运行错误", `${event.message} @ ${event.filename}:${event.lineno}`);
});

window.addEventListener("unhandledrejection", (event) => {
  showAppError("异步加载错误", event.reason?.message || String(event.reason));
});

bindEvents();
renderTaskStatus(null);
refreshAll().catch((error) => showAppError("终端初始化失败", error.message));
state.timer = window.setInterval(() => {
  refreshAll().catch((error) => showToast(`自动刷新失败：${error.message}`, "warn"));
}, 60000);
