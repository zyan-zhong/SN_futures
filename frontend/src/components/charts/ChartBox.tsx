import { lazy, Suspense, useEffect, useRef } from "react";
import { ErrorBoundary } from "../common/ErrorBoundary";

const ReactECharts = lazy(() => import("echarts-for-react"));

export function ChartBox({
  option,
  minHeight = 280,
  ariaLabel = "图表"
}: {
  option: Record<string, unknown>;
  minHeight?: number;
  ariaLabel?: string;
}) {
  const chartRef = useRef<any>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const resize = () => chartRef.current?.getEchartsInstance?.()?.resize?.();
    window.addEventListener("resize", resize);
    const observer = typeof ResizeObserver !== "undefined" ? new ResizeObserver(resize) : null;
    if (containerRef.current && observer) observer.observe(containerRef.current);
    return () => {
      window.removeEventListener("resize", resize);
      observer?.disconnect();
      chartRef.current?.getEchartsInstance?.()?.dispose?.();
    };
  }, []);

  return (
    <ErrorBoundary moduleName={ariaLabel}>
      <div className="chart-shell" ref={containerRef} role="img" style={{ minHeight }} aria-label={ariaLabel}>
        <Suspense fallback={<div className="chart-loading">图表组件加载中...</div>}>
          <ReactECharts
            ref={chartRef}
            notMerge
            lazyUpdate
            opts={{ renderer: "canvas" }}
            style={{ height: "100%", minHeight }}
            option={option}
          />
        </Suspense>
      </div>
    </ErrorBoundary>
  );
}
