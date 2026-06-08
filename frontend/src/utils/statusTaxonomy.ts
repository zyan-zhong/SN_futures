export type StatusTone = "good" | "warn" | "bad" | "neutral" | "info";

export type StatusTaxonomyEntry = {
  label: string;
  description: string;
  tone: StatusTone;
  allowedNextActionStyle: "none" | "read_only" | "safe_refresh" | "operator_review" | "manual_followup";
  canUnlockDownstreamGates: boolean;
};

export const STATUS_TAXONOMY: Record<string, StatusTaxonomyEntry> = {
  "blocked": {
    label: "已阻断",
    description: "关键前置条件未满足，后续 gate 不会解锁。",
    tone: "bad",
    allowedNextActionStyle: "operator_review",
    canUnlockDownstreamGates: false
  },
  "missing": {
    label: "资料缺失",
    description: "需要补齐真实配置、报告或 evidence 后才能继续。",
    tone: "warn",
    allowedNextActionStyle: "manual_followup",
    canUnlockDownstreamGates: false
  },
  "not_run": {
    label: "尚未运行",
    description: "检查或报告尚未执行；不要把它当作通过。",
    tone: "warn",
    allowedNextActionStyle: "safe_refresh",
    canUnlockDownstreamGates: false
  },
  "skipped": {
    label: "已跳过",
    description: "该项被显式跳过，需要查看原因和适用范围。",
    tone: "warn",
    allowedNextActionStyle: "operator_review",
    canUnlockDownstreamGates: false
  },
  "research_only": {
    label: "仅研究观察",
    description: "只允许查看研究证据，不允许发布 active 或生成客户预测。",
    tone: "info",
    allowedNextActionStyle: "read_only",
    canUnlockDownstreamGates: false
  },
  "planning_only": {
    label: "仅规划",
    description: "当前内容只是计划或清单，不代表实际执行。",
    tone: "info",
    allowedNextActionStyle: "read_only",
    canUnlockDownstreamGates: false
  },
  "dry_run_only": {
    label: "仅 dry-run",
    description: "只保留演练或模拟证据，不写 active、不生成客户输出。",
    tone: "info",
    allowedNextActionStyle: "read_only",
    canUnlockDownstreamGates: false
  },
  "ready": {
    label: "可继续审核",
    description: "当前检查可进入下一步人工审核；不等于自动放行。",
    tone: "good",
    allowedNextActionStyle: "operator_review",
    canUnlockDownstreamGates: true
  },
  "pass": {
    label: "检查通过",
    description: "该检查通过，但仍需遵守上游和人工 approval gate。",
    tone: "good",
    allowedNextActionStyle: "operator_review",
    canUnlockDownstreamGates: true
  },
  "fail": {
    label: "检查失败",
    description: "该检查失败，需要人工排查；不能解锁后续 gate。",
    tone: "bad",
    allowedNextActionStyle: "manual_followup",
    canUnlockDownstreamGates: false
  },
  "warning": {
    label: "需要注意",
    description: "存在非阻断风险或配置提示，需要阅读说明。",
    tone: "warn",
    allowedNextActionStyle: "operator_review",
    canUnlockDownstreamGates: false
  },
  "guarded": {
    label: "受保护",
    description: "安全 guard 已生效，只允许安全查看或刷新。",
    tone: "info",
    allowedNextActionStyle: "read_only",
    canUnlockDownstreamGates: false
  },
  "locked_down": {
    label: "已锁定",
    description: "该区域被锁定，禁止训练、promotion、active 和客户预测。",
    tone: "bad",
    allowedNextActionStyle: "read_only",
    canUnlockDownstreamGates: false
  },
  "incomplete": {
    label: "未完成",
    description: "证据或步骤不完整，不能作为通过依据。",
    tone: "warn",
    allowedNextActionStyle: "manual_followup",
    canUnlockDownstreamGates: false
  },
  "ready_with_missing_config": {
    label: "可查看但配置未齐",
    description: "基础页面可查看，但仍缺少必要配置，不能解锁后续 gate。",
    tone: "warn",
    allowedNextActionStyle: "manual_followup",
    canUnlockDownstreamGates: false
  }
};

const STATUS_ALIASES: Record<string, string> = {
  "blocked_or_not_run": "blocked",
  "done": "pass",
  "failed": "fail",
  "ok": "pass",
  "passed": "pass",
  "success": "pass",
  "unavailable": "missing",
  "unknown": "missing"
};

const NEXT_ACTION_LABELS: Record<string, string> = {
  // Legacy managed-proxy copy retained for contract compatibility only:
  // 配置 Managed Proxy endpoint 或 token
  // 閰嶇疆 Managed Proxy endpoint 鎴?token
  "configure_local_api_provider_credentials": "配置 Local API Provider credentials",
  "configure_managed_proxy_endpoint_or_token": "配置 Local API Provider credentials",
  "configure_managed_proxy_endpoint_token": "配置 Local API Provider credentials",
  "review_governance_console": "查看 Governance Console",
  "review_missing_evidence": "核对缺失 evidence",
  "wait_for_upstream_readiness": "等待上游 readiness",
  "safe_report_refresh": "刷新安全报告",
  "manual_review": "人工复核"
};

const RAW_STATUS_KEYS = [
  "blocked_or_not_run",
  "ready_with_missing_config",
  "research_only",
  "planning_only",
  "dry_run_only",
  "locked_down",
  "not_run"
];

function normalizeStatus(value: unknown): string {
  const raw = String(value ?? "").trim().toLowerCase();
  if (!raw) return "missing";
  return STATUS_ALIASES[raw] ?? raw;
}

function splitRawWords(value: string): string {
  return value
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function formatUnknownStatus(value: unknown): string {
  const words = splitRawWords(String(value ?? ""));
  return words ? `待确认：${words}` : STATUS_TAXONOMY.missing.label;
}

export function formatStatusLabel(value: unknown): string {
  const key = normalizeStatus(value);
  if (STATUS_TAXONOMY[key]) return STATUS_TAXONOMY[key].label;
  const original = String(value ?? "").trim();
  if (/[\u4e00-\u9fff]/.test(original) && !/[_-]/.test(original)) return original;
  return formatUnknownStatus(value);
}

export function formatGateStatus(value: unknown): string {
  return formatStatusLabel(value);
}

export function formatCandidateStatus(value: unknown): string {
  return formatStatusLabel(value);
}

export function formatNextAction(value: unknown): string {
  const key = String(value ?? "").trim().toLowerCase();
  if (!key) return "等待人工复核";
  return NEXT_ACTION_LABELS[key] ?? `下一步：${splitRawWords(String(value))}`;
}

export function formatEvidenceState(value: unknown): string {
  return formatStatusLabel(value);
}

export function getStatusTone(value: unknown): StatusTone {
  const key = normalizeStatus(value);
  return STATUS_TAXONOMY[key]?.tone ?? "neutral";
}

export function getStatusDescription(value: unknown): string {
  const key = normalizeStatus(value);
  return STATUS_TAXONOMY[key]?.description ?? "未识别状态；请查看 Raw status 技术字段。";
}

export function getDisabledReason(reason?: unknown): string {
  const text = String(reason ?? "").trim();
  if (!text) return "当前按钮被安全 guard 禁用，需要先完成前置 evidence 或人工复核。";
  return formatNextAction(text);
}

export function assertNoRawStatusLeak(text: string) {
  const primaryText = text
    .replace(/Raw status:[^\n\r<]*/gi, "")
    .replace(/Raw field:[^\n\r<]*/gi, "");
  const leakedStatusKeys = RAW_STATUS_KEYS.filter((key) => primaryText.includes(key));
  const concatenatedLeaks = primaryText.match(/[A-Za-z0-9_-]+(?:not_run|ready_with_missing_config|research_only)/g) ?? [];
  const invalidLiterals = ["undefined", "null", "NaN"].filter((item) => primaryText.includes(item));
  const leaks = [...new Set([...leakedStatusKeys, ...concatenatedLeaks, ...invalidLiterals])];
  return {
    passed: leaks.length === 0,
    rawStatusLeakCount: leaks.length,
    leakedStatusKeys: leaks
  };
}
