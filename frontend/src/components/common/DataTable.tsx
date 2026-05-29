import { isValidElement } from "react";
import { formatDateTime, formatNullable, formatNumber, formatPercent } from "../../utils/format";
import { EmptyState } from "./EmptyState";
import { ErrorState } from "./ErrorState";
import { LoadingState } from "./LoadingState";
import { StatusPill } from "./StatusPill";

export interface DataTableColumn<T> {
  key: string;
  title: string;
  format?: "text" | "number" | "percent" | "date" | "status";
  render?: (row: T) => unknown;
}

function formatCell(value: unknown, format: DataTableColumn<unknown>["format"] = "text"): string {
  if (format === "number") return formatNumber(value as number | null | undefined);
  if (format === "percent") return formatPercent(value as number | null | undefined);
  if (format === "date") return formatDateTime(value);
  return formatNullable(value);
}

function statusTone(text: string): "good" | "warn" | "bad" | "neutral" | "info" {
  if (text.includes("正常") || text.includes("可用")) return "info";
  if (text.includes("失败") || text.includes("过期") || text.includes("错误")) return "bad";
  if (text.includes("缓存") || text.includes("未配置") || text.includes("等待") || text.includes("谨慎")) return "warn";
  return "neutral";
}

export function DataTable<T extends Record<string, unknown>>({
  data,
  columns,
  loading,
  error,
  emptyLabel = "暂无可用数据"
}: {
  data?: T[];
  columns: Array<DataTableColumn<T>>;
  loading?: boolean;
  error?: string | null;
  emptyLabel?: string;
}) {
  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} />;
  if (!data?.length) {
    return <EmptyState label={emptyLabel} description="请先运行刷新任务，或查看运行期诊断确认数据目录。" />;
  }

  return (
    <div className="data-table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.key}>{column.title}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, index) => (
            <tr key={String(row.id || row.key || index)}>
              {columns.map((column) => {
                const raw = column.render ? column.render(row) : row[column.key];
                if (isValidElement(raw)) {
                  return <td key={column.key}>{raw}</td>;
                }
                const text = formatCell(raw, column.format);
                return (
                  <td key={column.key} title={text}>
                    {column.format === "status" ? <StatusPill label={text} tone={statusTone(text)} /> : <span>{text}</span>}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
