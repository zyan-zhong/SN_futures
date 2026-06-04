import { isValidElement } from "react";
import { formatDateTime, formatNullable, formatNumber, formatPercent } from "../../utils/format";
import { formatNextAction, formatStatusLabel, getStatusTone } from "../../utils/statusTaxonomy";
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
  if (format === "status") return formatStatusLabel(value);
  return formatNullable(value);
}

type ColumnDescriptor = Pick<DataTableColumn<Record<string, unknown>>, "key" | "title" | "format">;

function inferredFormat(column: ColumnDescriptor): DataTableColumn<unknown>["format"] {
  const key = `${column.key} ${column.title}`.toLowerCase();
  if (column.format) return column.format;
  if (key.includes("status") || key.includes("state")) return "status";
  return "text";
}

function formatActionCell(value: unknown, column: ColumnDescriptor): string | null {
  const key = `${column.key} ${column.title}`.toLowerCase();
  if (key.includes("next") || key.includes("action")) return formatNextAction(value);
  return null;
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
                const resolvedFormat = inferredFormat(column);
                const text = formatActionCell(raw, column) ?? formatCell(raw, resolvedFormat);
                return (
                  <td key={column.key} title={text}>
                    {resolvedFormat === "status" ? <StatusPill label={text} tone={getStatusTone(raw)} /> : <span>{text}</span>}
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
