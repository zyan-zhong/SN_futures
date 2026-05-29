import type { ForecastPathPayload } from "../../api/types";
import { formatPercent, formatPrice, toFiniteNumber } from "../../utils/format";
import { EmptyState } from "../common/EmptyState";
import { ChartBox } from "./ChartBox";

export function ForecastPathChart({ forecastPath }: { forecastPath?: ForecastPathPayload | null }) {
  const points = forecastPath?.points || [];
  if (!points.length) {
    return <EmptyState label={forecastPath?.message_zh || "暂无预测路径数据，请点击生成预测或一键刷新数据。"} />;
  }

  const labels = points.map((item) => `${item.horizon || "周期"} ${item.time || ""}`.trim());
  return (
    <ChartBox
      minHeight={380}
      ariaLabel="预测路径图"
      option={{
        backgroundColor: "transparent",
        tooltip: {
          trigger: "axis",
          formatter: (params: unknown) => {
            const rows = Array.isArray(params) ? params : [];
            return rows
              .map((item: any) => `${item.marker || ""}${item.seriesName}：${item.seriesName === "上涨概率" ? formatPercent(toFiniteNumber(item.value)) : formatPrice(toFiniteNumber(item.value))}`)
              .join("<br/>");
          }
        },
        legend: { textStyle: { color: "#9fb1c9" }, data: ["预测中枢", "下界", "上界", "上涨概率"] },
        grid: { left: 58, right: 42, top: 52, bottom: 56 },
        xAxis: { name: "预测步", type: "category", data: labels, axisLabel: { color: "#9fb1c9" }, nameTextStyle: { color: "#9fb1c9" } },
        yAxis: [
          {
            name: "价格（元/吨）",
            type: "value",
            axisLabel: { color: "#9fb1c9", formatter: (value: number) => formatPrice(value) },
            nameTextStyle: { color: "#9fb1c9" },
            splitLine: { lineStyle: { color: "#1d2b3d" } }
          },
          {
            name: "概率",
            type: "value",
            min: 0,
            max: 1,
            axisLabel: { color: "#9fb1c9", formatter: (value: number) => formatPercent(value) },
            nameTextStyle: { color: "#9fb1c9" }
          }
        ],
        graphic: forecastPath?.sample_mode
          ? [{ type: "text", right: 28, top: 18, style: { text: "Sample / 样例", fill: "#f7c948", font: "700 16px sans-serif" } }]
          : undefined,
        series: [
          { name: "预测中枢", type: "line", smooth: true, data: points.map((item) => toFiniteNumber(item.center)), lineStyle: { color: "#f7c948", width: 3 } },
          { name: "下界", type: "line", smooth: true, data: points.map((item) => toFiniteNumber(item.lower)), lineStyle: { color: "#49c6a7", width: 1, type: "dashed" } },
          { name: "上界", type: "line", smooth: true, data: points.map((item) => toFiniteNumber(item.upper)), lineStyle: { color: "#f56b6b", width: 1, type: "dashed" } },
          { name: "上涨概率", type: "bar", yAxisIndex: 1, data: points.map((item) => toFiniteNumber(item.prob_up)), itemStyle: { color: "#6ea8fe", opacity: 0.35 } }
        ]
      }}
    />
  );
}
