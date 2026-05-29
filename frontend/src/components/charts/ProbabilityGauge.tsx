import { formatPercent } from "../../utils/format";
import { EmptyState } from "../common/EmptyState";
import { ChartBox } from "./ChartBox";

export function ProbabilityGauge({ value, title = "上涨概率" }: { value?: number | null; title?: string }) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return <EmptyState label="暂无概率图数据" />;
  const percent = Math.max(0, Math.min(100, Math.abs(Number(value)) <= 1 ? Number(value) * 100 : Number(value)));
  return (
    <ChartBox
      minHeight={220}
      ariaLabel={`${title}仪表盘`}
      option={{
        backgroundColor: "transparent",
        tooltip: { formatter: `${title}：${formatPercent(percent)}` },
        series: [
          {
            name: title,
            type: "gauge",
            min: 0,
            max: 100,
            progress: { show: true, width: 12 },
            axisLine: { lineStyle: { width: 12 } },
            detail: { formatter: `${percent.toFixed(1)}%`, color: "#e6edf7", fontSize: 22 },
            data: [{ value: percent, name: title }]
          }
        ]
      }}
    />
  );
}
