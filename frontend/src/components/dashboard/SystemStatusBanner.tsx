import type { TerminalSnapshot } from "../../api/types";
import { isDegraded, isLowQuality } from "../../utils/guards";

function hasUnconfiguredSource(snapshot?: TerminalSnapshot | null): boolean {
  return Boolean(snapshot?.data_status?.sources?.some((source) => !source.enabled || source.message_zh?.includes("未配置")));
}

function hasNoActiveModel(snapshot?: TerminalSnapshot | null): boolean {
  const health = snapshot?.model_health;
  return Boolean(!health?.active_model || health.active_model.includes("暂无"));
}

export function SystemStatusBanner({ snapshot, apiError }: { snapshot?: TerminalSnapshot | null; apiError?: string | null }) {
  const summary = snapshot?.summary;
  let tone: "ok" | "warning" | "error" = "ok";
  let title = "系统运行正常";
  let message = "系统运行正常，当前结果仅供投研参考。";

  if (apiError && !snapshot) {
    tone = "error";
    title = "本地服务暂时不可用";
    message = "本地服务暂时不可用，请稍后重试或查看日志。";
  } else if (isDegraded(summary?.model_status) || snapshot?.model_health?.degradation_status?.includes("降级")) {
    tone = "warning";
    title = "模型健康状态下降";
    message = "模型健康状态下降，已停止显示交易点位。";
  } else if (hasNoActiveModel(snapshot)) {
    tone = "warning";
    title = "暂无可用 active 模型";
    message = "暂无可用 active 模型，当前仅展示研究框架和数据状态。";
  } else if (isLowQuality(summary?.data_quality_score)) {
    tone = "warning";
    title = "数据质量不足";
    message = "数据质量不足，预测已降级为研究观察。";
  } else if (hasUnconfiguredSource(snapshot)) {
    tone = "warning";
    title = "部分外部数据源未配置";
    message = "部分外部数据源未配置，系统已使用可用数据运行。";
  }

  return (
    <div className={`system-status-banner banner-${tone}`} data-status-tone={tone}>
      <strong>{title}</strong>
      <span>{message}</span>
    </div>
  );
}
