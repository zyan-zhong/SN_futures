import { formatDateTime, formatNumber, toFiniteNumber } from "../../utils/format";
import { EmptyState } from "../common/EmptyState";
import { ChartBox } from "./ChartBox";

export function EquityCurveChart({ data }: { data?: Array<{ ts?: string; value?: number }> }) {
  if (!data?.length) return <EmptyState label="暂无可用图表数据" />;
  return (
    <ChartBox
      minHeight={260}
      ariaLabel="权益曲线图"
      option={{
        backgroundColor: "transparent",
        tooltip: { trigger: "axis", valueFormatter: (value: unknown) => formatNumber(toFiniteNumber(value), 2) },
        xAxis: { name: "时间", type: "category", data: data.map((item) => formatDateTime(item.ts, "")), axisLabel: { color: "#9fb1c9" }, nameTextStyle: { color: "#9fb1c9" } },
        yAxis: { name: "权益", type: "value", axisLabel: { color: "#9fb1c9" }, nameTextStyle: { color: "#9fb1c9" }, splitLine: { lineStyle: { color: "#1d2b3d" } } },
        series: [{ name: "权益曲线", type: "line", smooth: true, data: data.map((item) => toFiniteNumber(item.value)), areaStyle: {} }]
      }}
    />
  );
}
