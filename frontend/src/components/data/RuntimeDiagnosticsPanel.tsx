import { useEffect, useState } from "react";
import { getRuntimeDiagnostics } from "../../api/terminal";
import type { RuntimeDiagnostics, RuntimeDiagnosticFile } from "../../api/types";
import { formatDateTime, formatNullable, formatNumber } from "../../utils/format";
import { EmptyState } from "../common/EmptyState";
import { ErrorState } from "../common/ErrorState";
import { LoadingState } from "../common/LoadingState";
import { MetricCard } from "../common/MetricCard";
import { StatusPill } from "../common/StatusPill";
import { DataTable } from "../common/DataTable";
import { SectionCard } from "../layout/SectionCard";

function conclusionLabel(key: string): string {
  const labels: Record<string, string> = {
    no_cache_files: "未找到预测缓存",
    no_predictions: "未找到可展示预测",
    no_reports: "未找到报告",
    no_news_events: "未找到新闻事件",
    no_provider_validation: "尚未完成数据源请求验证",
    frontend_only_shell: "当前更像是前端壳已启动但数据链路未生成"
  };
  return labels[key] || key;
}

function statusTone(value?: boolean): "good" | "warn" {
  return value ? "good" : "warn";
}

function fileRows(files?: RuntimeDiagnosticFile[]) {
  return (files || []).map((file) => ({
    ...file,
    exists_label: file.exists ? "存在" : "缺失",
    cards_label: file.has_cards ? `${file.card_count || 0} 张卡片` : "无预测卡片",
    quote_label: file.has_quote ? formatNullable(file.latest_price) : "无行情水位",
    report_label: file.report_length ? `${formatNumber(file.report_length, 0)} 字符` : "无报告正文"
  }));
}

export function RuntimeDiagnosticsPanel() {
  const [diagnostics, setDiagnostics] = useState<RuntimeDiagnostics | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadDiagnostics = () => {
    setLoading(true);
    setError(null);
    getRuntimeDiagnostics()
      .then(setDiagnostics)
      .catch((err: Error) => setError(err.message || "运行期诊断暂时无法加载。"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadDiagnostics();
  }, []);

  if (loading && !diagnostics) return <LoadingState title="正在读取运行期数据链路..." />;
  if (error && !diagnostics) {
    return (
      <ErrorState
        title="运行期诊断加载失败"
        message={error}
        actionLabel="重新诊断"
        onAction={loadDiagnostics}
      />
    );
  }
  if (!diagnostics) {
    return (
      <EmptyState
        title="暂无运行期诊断结果"
        description="请确认后端已启动，然后重新运行诊断。"
        actionLabel="重新诊断"
        onAction={loadDiagnostics}
      />
    );
  }

  const conclusions = Object.entries(diagnostics.data_gap_conclusion || {}).filter(([, value]) => value);
  const rows = fileRows(diagnostics.expected_output_files);

  return (
    <SectionCard
      title="运行期诊断"
      subtitle="只读取本机缓存、报告和事件库，帮助定位网页为什么没有数据、图表、新闻或报告。"
      actions={
        <button className="ghost-button" type="button" onClick={loadDiagnostics}>
          重新诊断
        </button>
      }
    >
      <div className="metric-grid">
        <MetricCard label="预测输出目录" value={diagnostics.output_dir || "数据暂缺"} />
        <MetricCard label="报告目录" value={diagnostics.report_dir || "数据暂缺"} />
        <MetricCard label="Alpha Vantage" value={diagnostics.alpha_vantage_configured ? "已配置" : "未配置"} tone={statusTone(diagnostics.alpha_vantage_configured)} />
        <MetricCard label="NewsAPI" value={diagnostics.newsapi_configured ? "已配置" : "未配置"} tone={statusTone(diagnostics.newsapi_configured)} />
        <MetricCard label="新闻事件数" value={diagnostics.event_store?.news_event_count ?? 0} tone={diagnostics.event_store?.has_news_events ? "good" : "warn"} />
        <MetricCard label="生成时间" value={formatDateTime(diagnostics.generated_at)} />
      </div>

      <div className="reason-list">
        {conclusions.length ? (
          conclusions.map(([key]) => <StatusPill key={key} label={conclusionLabel(key)} tone="warn" />)
        ) : (
          <StatusPill label="未发现明显运行期数据缺口" tone="good" />
        )}
      </div>

      <DataTable
        data={rows as Array<Record<string, unknown>>}
        emptyLabel="暂无需要检查的运行期文件"
        columns={[
          { key: "relative_name", title: "文件" },
          { key: "exists_label", title: "状态", format: "status" },
          { key: "size", title: "大小", format: "number" },
          { key: "modified_time", title: "更新时间", render: (row) => formatDateTime(row.modified_time) },
          { key: "cards_label", title: "预测卡片" },
          { key: "quote_label", title: "行情水位" },
          { key: "report_label", title: "报告正文" }
        ]}
      />

      <div className="callout">
        <strong>下一步建议</strong>
        <ul>
          {(diagnostics.next_actions_zh || ["请先运行数据刷新、预测生成和报告生成任务。"]).map((action) => (
            <li key={action}>{action}</li>
          ))}
        </ul>
      </div>
    </SectionCard>
  );
}
