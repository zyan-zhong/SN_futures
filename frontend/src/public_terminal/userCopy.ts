const statusLabels: Record<string, string> = {
  blocked: "暂时不能继续",
  failed: "检查失败",
  not_run: "尚未检查",
  queued: "排队中",
  running: "检查中",
  skipped: "已跳过",
  stale: "可查看旧数据",
  success: "已完成",
  ready: "已准备好"
};

const reasonLabels: Record<string, string> = {
  insufficient_data: "数据不足",
  local_provider_not_configured: "还没有配置数据源",
  missing_daily_bars: "缺少历史行情数据",
  no_active_provider_smoke_pass: "还没有通过数据源检查",
  no_rows: "没有返回可用数据",
  provider_keys_missing: "还没有配置访问密钥",
  request_timeout: "连接超时"
};

const nextActionLabels: Record<string, string> = {
  open_setup: "打开 Setup，配置或跳过数据源",
  refresh_data_status: "打开 Data Status，刷新数据完整度",
  run_provider_smoke: "运行数据源检查",
  setup_required: "先完成 Setup"
};

export function friendlyStatus(value: unknown, fallback = "暂时不能继续") {
  const key = String(value ?? "").trim().toLowerCase();
  return statusLabels[key] || fallback;
}

export function friendlyReason(value: unknown, fallback = "需要先补齐真实数据") {
  const key = String(value ?? "").trim().toLowerCase();
  return reasonLabels[key] || fallback;
}

export function friendlyNextAction(value: unknown, fallback = "先到 Setup 配置数据源，或选择稍后配置") {
  const key = String(value ?? "").trim().toLowerCase();
  return nextActionLabels[key] || fallback;
}

export function maskOrEmpty(value: unknown) {
  const text = String(value ?? "").trim();
  return text || "未配置";
}

export function technicalSummary(payload: unknown) {
  return JSON.stringify(payload ?? {}, null, 2);
}
