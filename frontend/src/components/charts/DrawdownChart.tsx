import { formatDateTime, formatPercent, toFiniteNumber } from "../../utils/format";
import { EmptyState } from "../common/EmptyState";
import { ChartBox } from "./ChartBox";

export function DrawdownChart({ data }: { data?: Array<{ ts?: string; value?: number }> }) {
  const rows = Array.isArray(data) ? data : [];
  if (!rows.length) return <EmptyState label="暂无可用回撤图数据" />;
  return (
    <ChartBox
      minHeight={240}
      ariaLabel="回撤曲线图"
      option={{
        backgroundColor: "transparent",
        tooltip: { trigger: "axis", valueFormatter: (value: unknown) => formatPercent(toFiniteNumber(value)) },
        xAxis: { name: "时间", type: "category", data: rows.map((item) => formatDateTime(item.ts, "")), axisLabel: { color: "#9fb1c9" }, nameTextStyle: { color: "#9fb1c9" } },
        yAxis: { name: "回撤", type: "value", axisLabel: { color: "#9fb1c9", formatter: (value: number) => formatPercent(value) }, nameTextStyle: { color: "#9fb1c9" }, splitLine: { lineStyle: { color: "#1d2b3d" } } },
        series: [{ name: "回撤", type: "line", data: rows.map((item) => toFiniteNumber(item.value)), lineStyle: { color: "#49c6a7" }, areaStyle: {} }]
      }}
    />
  );
}
