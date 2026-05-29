import { useEffect, useState } from "react";
import type { ReportItem } from "../../api/types";
import { formatDateTime, formatNullable, formatPercent } from "../../utils/format";
import { DataTable } from "../common/DataTable";
import { EmptyState } from "../common/EmptyState";
import { StatusPill } from "../common/StatusPill";
import { SectionCard } from "../layout/SectionCard";

const REPORT_TYPE_LABELS: Record<string, string> = {
  daily: "日报",
  weekly: "周报",
  monthly: "月报",
  event: "事件报告"
};

function cleanMarkdown(report: ReportItem): string {
  const text = report.markdown || report.summary || "报告内容暂缺";
  const safe = text.replace(/\bnan\b/gi, "数据暂缺");
  const disclaimer = report.disclaimer || "仅供沪锡期货量化投研参考，不构成投资建议，不承诺收益，不接实盘交易。";
  return safe.includes("不构成投资建议") ? safe : `${disclaimer}\n\n${safe}`;
}

function reportLabel(report: ReportItem): string {
  return REPORT_TYPE_LABELS[String(report.type || "").toLowerCase()] || report.title || report.name || "报告";
}

export function ReportCenter({ reports, onReportSelect }: { reports?: ReportItem[]; onReportSelect?: (report: ReportItem) => void }) {
  const [selected, setSelected] = useState<ReportItem | null>(reports?.[0] || null);
  const [copyMessage, setCopyMessage] = useState("");

  useEffect(() => {
    if (!reports?.length) {
      setSelected(null);
      return;
    }
    const selectedType = selected?.type;
    setSelected(reports.find((report) => report.type === selectedType) || reports[0]);
  }, [reports, selected?.type]);

  if (!reports?.length) return <EmptyState label="暂无报告，请先运行报告生成任务。" />;
  const active = selected || reports[0];
  const markdown = cleanMarkdown(active);

  async function copyMarkdown() {
    await navigator.clipboard?.writeText(markdown);
    setCopyMessage("Markdown 已复制。");
  }

  function downloadMarkdown() {
    const blob = new Blob([markdown], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${reportLabel(active)}.md`;
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="page-stack">
      <SectionCard title="报告列表" subtitle="日报、周报、月报和事件报告；内容仅作量化投研参考。">
        <DataTable
          data={reports as Array<Record<string, unknown>>}
          columns={[
            { key: "type", title: "报告类型", render: (row) => reportLabel(row as ReportItem) },
            { key: "generated_at", title: "生成时间", format: "date" },
            { key: "data_cutoff", title: "数据截止时间", format: "date" },
            { key: "model_version", title: "模型版本", render: (row) => (row as ReportItem).model_version || "数据暂缺" },
            { key: "data_quality_score", title: "数据质量", render: (row) => formatPercent((row as ReportItem).data_quality_score) },
            {
              key: "promotion_status",
              title: "Promotion Gate",
              format: "status",
              render: (row) => {
                const item = row as ReportItem;
                if (typeof item.promotion_gate_passed === "boolean") return item.promotion_gate_passed ? "已通过" : "未通过";
                return item.promotion_status || "待验证";
              }
            }
          ]}
        />
        <div className="report-selector">
          {reports.map((report, index) => (
            <button
              className={active === report ? "active" : ""}
              key={`${report.type || "report"}-${index}`}
              type="button"
              onClick={() => {
                setSelected(report);
                onReportSelect?.(report);
              }}
            >
              {reportLabel(report)}
            </button>
          ))}
        </div>
      </SectionCard>

      <SectionCard title="Markdown 预览" subtitle={`当前报告：${reportLabel(active)}；生成时间：${formatDateTime(active.generated_at)}`}>
        <div className="tag-strip">
          <StatusPill label={`数据截止：${formatNullable(active.data_cutoff)}`} tone="info" />
          <StatusPill label={`模型版本：${formatNullable(active.model_version)}`} tone="info" />
          <StatusPill label={`数据质量：${formatPercent(active.data_quality_score)}`} tone="info" />
        </div>
        <details className="report-preview" open>
          <summary>展开/折叠报告内容</summary>
          <pre>{markdown}</pre>
        </details>
        <div className="button-row">
          <button className="ghost-button" type="button" onClick={() => void copyMarkdown()}>
            复制 Markdown
          </button>
          <button className="ghost-button" type="button" onClick={downloadMarkdown}>
            下载 .md
          </button>
          {copyMessage ? <StatusPill label={copyMessage} tone="good" /> : null}
        </div>
      </SectionCard>
    </div>
  );
}
