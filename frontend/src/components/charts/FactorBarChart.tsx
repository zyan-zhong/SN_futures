import { formatNumber, toFiniteNumber } from "../../utils/format";
import { EmptyState } from "../common/EmptyState";
import { ChartBox } from "./ChartBox";

export function FactorBarChart({ data }: { data?: Array<{ name: string; value: number }> }) {
  const rows = Array.isArray(data) ? data : [];
  if (!rows.length) return <EmptyState label="暂无完整因子诊断数据，请先运行因子诊断任务" />;
  const cleaned = rows.map((item) => ({ name: item.name || "因子", value: toFiniteNumber(item.value) }));
  return (
    <ChartBox
      minHeight={280}
      ariaLabel="因子贡献图"
      option={{
        backgroundColor: "transparent",
        tooltip: { trigger: "axis", valueFormatter: (value: unknown) => formatNumber(toFiniteNumber(value), 3) },
        xAxis: { name: "贡献值", type: "value", axisLabel: { color: "#9fb1c9" }, nameTextStyle: { color: "#9fb1c9" } },
        yAxis: { name: "因子", type: "category", data: cleaned.map((item) => item.name), axisLabel: { color: "#9fb1c9" }, nameTextStyle: { color: "#9fb1c9" } },
        series: [{ name: "因子贡献", type: "bar", data: cleaned.map((item) => item.value), itemStyle: { color: "#66d9ef" } }]
      }}
    />
  );
}
