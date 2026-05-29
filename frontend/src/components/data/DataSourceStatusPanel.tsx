import type { DataSourceStatus } from "../../api/types";
import { formatDateTime, formatNullable } from "../../utils/format";
import { DataTable } from "../common/DataTable";
import { EmptyState } from "../common/EmptyState";
import { MetricCard } from "../common/MetricCard";
import { StatusPill } from "../common/StatusPill";
import { SectionCard } from "../layout/SectionCard";

type StatusTone = "good" | "warn" | "bad" | "neutral" | "info";

function sourceStatusLabel(source: DataSourceStatus): string {
  if (source.freshness_label) return source.freshness_label;
  if (source.status_zh) return source.status_zh;
  if (!source.enabled && source.configured === false) return "未配置";
  if (source.success && source.from_cache) return "使用缓存";
  if (source.success && !source.stale) return "正常";
  if (source.status_code === "disabled") return "未启用";
  if (source.status_code === "waiting_next_session") return "非交易时段等待更新";
  if (source.stale) return "已过期";
  return "请求失败";
}

function statusTone(status: string): StatusTone {
  if (
    status === "blocked_by_waf" ||
    status === "函数不可用" ||
    status === "无锡数据" ||
    status === "字段不匹配" ||
    status.includes("WAF")
  ) {
    return "warn";
  }
  if (status === "正常" || status === "较旧但可参考") return "good";
  if (status === "使用缓存" || status === "未配置" || status === "未启用" || status === "非交易时段等待更新") {
    return "warn";
  }
  if (status === "已过期" || status === "请求失败") return "bad";
  return "neutral";
}

function countBy(sources: DataSourceStatus[], predicate: (source: DataSourceStatus) => boolean): number {
  return sources.filter(predicate).length;
}

function nextActionsText(source: DataSourceStatus): string {
  const actions = source.next_actions_zh;
  if (Array.isArray(actions) && actions.length) return actions.join("；");
  return source.suggested_action_zh || "查看运行期诊断";
}

export function DataSourceStatusPanel({
  sources,
  onSettings,
  onRefresh,
  logsDir
}: {
  sources?: DataSourceStatus[];
  onSettings?: () => void;
  onRefresh?: () => void;
  logsDir?: string;
}) {
  if (!sources?.length) {
    return (
      <EmptyState
        label="暂无数据源状态"
        description="请先运行一键刷新数据，或打开运行期诊断查看输出目录和刷新日志。"
        actionLabel="刷新状态"
        onAction={onRefresh}
        secondaryActionLabel="前往设置"
        onSecondaryAction={onSettings}
      />
    );
  }

  const rows = sources.map((source) => {
    const status = sourceStatusLabel(source);
    return {
      ...source,
      status,
      status_tone: statusTone(status),
      enabled_label: source.enabled ? "已启用" : source.configured === false ? "未配置" : "未启用",
      success_label: source.success ? "成功" : source.attempted ? "未成功" : "未尝试",
      cache_label: source.from_cache ? "使用缓存" : "本周期数据",
      stale_label: source.stale ? "已过期" : "未过期",
      last_success_time: source.last_success_time || source.last_update,
      last_attempt_time: source.last_attempt_time || source.last_update,
      ttl_zh: source.ttl_zh || (source.ttl_seconds ? `${Math.round(source.ttl_seconds / 60)} 分钟` : "本周期未更新"),
      next_expected_update: source.next_expected_update || source.next_expected_update_time,
      error_message_zh: source.error_message_zh || source.message_zh || "",
      next_actions_text: nextActionsText(source),
      row_count: source.row_count ?? 0
    };
  });

  const normal = countBy(rows, (source) => sourceStatusLabel(source) === "正常");
  const unconfigured = countBy(rows, (source) => sourceStatusLabel(source) === "未配置");
  const disabled = countBy(rows, (source) => sourceStatusLabel(source) === "未启用");
  const failed = countBy(rows, (source) => sourceStatusLabel(source) === "请求失败");
  const cached = countBy(rows, (source) => sourceStatusLabel(source) === "使用缓存");
  const stale = countBy(rows, (source) => sourceStatusLabel(source) === "已过期");

  return (
    <div className="page-stack">
      <SectionCard
        title="数据源总览"
        subtitle="新闻、政策和 SHFE 公共数据使用各自更新周期；未配置、未启用、使用缓存和请求失败会分开解释。"
      >
        <div className="metric-grid">
          <MetricCard label="正常数量" value={normal} tone="good" />
          <MetricCard label="未配置数量" value={unconfigured} tone={unconfigured ? "warn" : "good"} />
          <MetricCard label="未启用数量" value={disabled} tone={disabled ? "warn" : "good"} />
          <MetricCard label="请求失败数量" value={failed} tone={failed ? "bad" : "good"} />
          <MetricCard label="使用缓存数量" value={cached} tone={cached ? "warn" : "good"} />
          <MetricCard label="已过期数量" value={stale} tone={stale ? "bad" : "good"} />
        </div>
        <div className="button-row">
          <button className="ghost-button" type="button" onClick={onSettings}>
            前往设置
          </button>
          <button className="ghost-button" type="button" onClick={onRefresh}>
            刷新状态
          </button>
          <button className="ghost-button" type="button" title={logsDir || "日志目录暂缺"}>
            查看日志位置
          </button>
        </div>
      </SectionCard>

      <SectionCard
        title="数据源列表"
        subtitle="显示最近成功时间、最近尝试时间、TTL、下一次建议刷新、返回条数、错误原因和下一步建议。"
      >
        <DataTable
          data={rows as Array<Record<string, unknown>>}
          columns={[
            { key: "source_name", title: "数据源", render: (row) => formatNullable(row.source_name, "数据源") },
            {
              key: "status",
              title: "状态",
              render: (row) => <StatusPill label={String(row.status || "本周期未更新")} tone={row.status_tone as StatusTone} />
            },
            { key: "enabled_label", title: "启用" },
            { key: "success_label", title: "请求" },
            { key: "cache_label", title: "缓存" },
            { key: "row_count", title: "返回条数" },
            { key: "last_success_time", title: "最近成功", render: (row) => formatDateTime(row.last_success_time) },
            { key: "last_attempt_time", title: "最近尝试", render: (row) => formatDateTime(row.last_attempt_time) },
            { key: "ttl_zh", title: "TTL" },
            { key: "next_expected_update", title: "下次建议刷新", render: (row) => formatDateTime(row.next_expected_update) },
            { key: "error_message_zh", title: "原因说明", render: (row) => formatNullable(row.error_message_zh, "暂无错误") },
            { key: "next_actions_text", title: "下一步建议", render: (row) => formatNullable(row.next_actions_text, "查看运行期诊断") }
          ]}
        />
      </SectionCard>

      <SectionCard
        title="状态解释"
        subtitle="系统健康颜色与行情涨跌颜色分离：系统正常使用蓝/青，行情上涨红色、下跌绿色。"
      >
        <div className="reason-list">
          <StatusPill label="正常：数据源可用" tone="good" />
          <StatusPill label="使用缓存：展示最近成功数据" tone="warn" />
          <StatusPill label="使用缓存：当前展示缓存数据" tone="warn" />
          <StatusPill label="未配置：需要在设置页配置 key" tone="warn" />
          <StatusPill label="未启用：当前版本未启用该自动源" tone="warn" />
          <StatusPill label="已过期：超过对应更新周期" tone="bad" />
          <StatusPill label="已过期：超过更新周期" tone="bad" />
          <StatusPill label="请求失败：接口或网络不可用" tone="bad" />
          <StatusPill label="数据源失败：请求失败或服务不可用" tone="bad" />
          <StatusPill label="非交易时段等待更新：休市不直接判定失败" tone="info" />
        </div>
        <p className="muted">
          本页面不会展示任何 API key。密钥只保存在本机用户目录，并由后端脱敏读取。
        </p>
      </SectionCard>

      <SectionCard title="SHFE / AKShare 辅助源说明" subtitle="库存、仓单、现货基差、交易所日线和会员持仓已拆分展示。">
        <div className="reason-list">
          <StatusPill label="blocked_by_waf：SHFE 官网直连被人机验证阻断" tone="warn" />
          <StatusPill label="函数不可用：当前 AKShare 版本没有该辅助源函数" tone="warn" />
          <StatusPill label="无锡数据：函数返回中没有锡/SN 相关行" tone="warn" />
        </div>
        <p className="muted">
          SHFE 官网直连被人机验证阻断；系统已改用 AKShare/缓存辅助源，不影响主行情。
          库存、仓单、现货基差、交易所日线和会员持仓会拆分展示，避免只显示“SHFE public 不可用”。
        </p>
      </SectionCard>
    </div>
  );
}
