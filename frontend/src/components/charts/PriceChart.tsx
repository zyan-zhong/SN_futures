import type { MarketAnalysisPayload, PredictionCard, PriceHistoryPayload } from "../../api/types";
import { formatPrice, toFiniteNumber } from "../../utils/format";
import { EmptyState } from "../common/EmptyState";
import { ChartBox } from "./ChartBox";

export function PriceChart({
  keyLevels,
  predictions,
  priceHistory
}: {
  keyLevels?: MarketAnalysisPayload["key_levels"];
  predictions?: PredictionCard[];
  priceHistory?: PriceHistoryPayload | null;
}) {
  const historyPoints = Array.isArray(priceHistory?.points) ? priceHistory.points : [];
  const safePredictions = Array.isArray(predictions) ? predictions : [];

  if (historyPoints.length) {
    const hasVolume = historyPoints.some((item) => toFiniteNumber(item.volume) !== null);
    const markLines = [
      ...(keyLevels?.support_levels || []).map((value) => ({
        name: "支撑",
        yAxis: toFiniteNumber(value),
        lineStyle: { color: "#49c6a7", type: "dotted" }
      })),
      ...(keyLevels?.resistance_levels || []).map((value) => ({
        name: "压力",
        yAxis: toFiniteNumber(value),
        lineStyle: { color: "#f56b6b", type: "dotted" }
      }))
    ].filter((item) => item.yAxis !== null);
    return (
      <ChartBox
        minHeight={360}
        ariaLabel="沪锡历史行情图"
        option={{
          backgroundColor: "transparent",
          tooltip: {
            trigger: "axis",
            valueFormatter: (value: unknown) => formatPrice(toFiniteNumber(value))
          },
          legend: { textStyle: { color: "#9fb1c9" }, data: hasVolume ? ["收盘价", "最高价", "最低价", "成交量"] : ["收盘价", "最高价", "最低价"] },
          grid: { left: 56, right: 24, top: 48, bottom: 48 },
          xAxis: {
            name: "时间",
            type: "category",
            data: historyPoints.map((item) => item.time || "本周期未更新"),
            axisLabel: { color: "#9fb1c9" },
            nameTextStyle: { color: "#9fb1c9" }
          },
          yAxis: [
            {
              name: "价格（元/吨）",
              type: "value",
              axisLabel: { color: "#9fb1c9", formatter: (value: number) => formatPrice(value) },
              nameTextStyle: { color: "#9fb1c9" },
              splitLine: { lineStyle: { color: "#1d2b3d" } }
            },
            {
              name: "成交量",
              type: "value",
              show: hasVolume,
              axisLabel: { color: "#9fb1c9" },
              nameTextStyle: { color: "#9fb1c9" },
              splitLine: { show: false }
            }
          ],
          graphic: priceHistory?.sample_mode
            ? [{ type: "text", right: 28, top: 18, style: { text: "Sample / 样例", fill: "#f7c948", font: "700 16px sans-serif" } }]
            : undefined,
          series: [
            {
              name: "收盘价",
              type: "line",
              smooth: true,
              data: historyPoints.map((item) => toFiniteNumber(item.close)),
              lineStyle: { color: "#f7c948", width: 3 },
              markLine: markLines.length ? { symbol: "none", label: { formatter: "{b}" }, data: markLines } : undefined
            },
            { name: "最高价", type: "line", smooth: true, data: historyPoints.map((item) => toFiniteNumber(item.high)), lineStyle: { color: "#f56b6b", width: 1, type: "dashed" } },
            { name: "最低价", type: "line", smooth: true, data: historyPoints.map((item) => toFiniteNumber(item.low)), lineStyle: { color: "#49c6a7", width: 1, type: "dashed" } },
            ...(hasVolume
              ? [
                  {
                    name: "成交量",
                    type: "bar",
                    yAxisIndex: 1,
                    data: historyPoints.map((item) => toFiniteNumber(item.volume)),
                    itemStyle: { color: "rgba(102, 217, 239, 0.28)" }
                  }
                ]
              : [])
          ]
        }}
      />
    );
  }

  if (!safePredictions.length) return <EmptyState label={priceHistory?.message_zh || "暂无可用图表数据，请点击一键刷新数据。"} />;

  const labels = safePredictions.map((item) => item.horizon_zh || item.horizon || "周期");
  const centers = safePredictions.map((item) => {
    const range = item.predicted_range || [];
    const low = toFiniteNumber(range[0]);
    const high = toFiniteNumber(range[1]);
    return low !== null && high !== null ? (low + high) / 2 : null;
  });
  const lower = safePredictions.map((item) => toFiniteNumber(item.predicted_range?.[0]));
  const upper = safePredictions.map((item) => toFiniteNumber(item.predicted_range?.[1]));

  return (
    <ChartBox
      minHeight={360}
      ariaLabel="预测价格区间图"
      option={{
        backgroundColor: "transparent",
        tooltip: {
          trigger: "axis",
          valueFormatter: (value: unknown) => formatPrice(toFiniteNumber(value))
        },
        legend: { textStyle: { color: "#9fb1c9" }, data: ["预测中枢", "下界", "上界"] },
        grid: { left: 52, right: 24, top: 48, bottom: 40 },
        xAxis: { name: "预测周期", type: "category", data: labels, axisLabel: { color: "#9fb1c9" }, nameTextStyle: { color: "#9fb1c9" } },
        yAxis: { name: "价格（元/吨）", type: "value", axisLabel: { color: "#9fb1c9", formatter: (value: number) => formatPrice(value) }, nameTextStyle: { color: "#9fb1c9" }, splitLine: { lineStyle: { color: "#1d2b3d" } } },
        graphic: safePredictions.some((item) => item.sample_mode)
          ? [{ type: "text", right: 28, top: 18, style: { text: "Sample / 样例", fill: "#f7c948", font: "700 16px sans-serif" } }]
          : undefined,
        series: [
          { name: "预测中枢", type: "line", smooth: true, data: centers, lineStyle: { color: "#f7c948", width: 3 } },
          { name: "下界", type: "line", smooth: true, data: lower, lineStyle: { color: "#49c6a7", width: 1, type: "dashed" } },
          { name: "上界", type: "line", smooth: true, data: upper, lineStyle: { color: "#f56b6b", width: 1, type: "dashed" } }
        ]
      }}
    />
  );
}
