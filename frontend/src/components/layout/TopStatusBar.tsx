import type { TerminalSummary } from "../../api/types";
import { formatDateTime, formatNullable, formatPercent, formatPrice } from "../../utils/format";
import { StatusPill } from "../common/StatusPill";

export function TopStatusBar({ summary }: { summary?: TerminalSummary }) {
  const quality = summary?.data_quality_score;
  const qualityTone = typeof quality === "number" && quality >= 0.75 ? "info" : typeof quality === "number" && quality >= 0.55 ? "warn" : "bad";
  const change = typeof summary?.price_change_pct === "number" ? summary.price_change_pct : null;
  const changeClass = change === null ? "market-flat" : change > 0 ? "market-up" : change < 0 ? "market-down" : "market-flat";
  return (
    <header className="top-status">
      <div>
        <span className="status-label">主力合约</span>
        <strong>{formatNullable(summary?.main_contract, "SN")}</strong>
      </div>
      <div>
        <span className="status-label">最新价格</span>
        <strong>{formatPrice(summary?.latest_price)}</strong>
      </div>
      <div>
        <span className="status-label">涨跌幅</span>
        <strong className={changeClass}>{formatPercent(summary?.price_change_pct)}</strong>
      </div>
      <div>
        <span className="status-label">数据质量</span>
        <StatusPill label={formatNullable(summary?.data_quality_label)} tone={qualityTone} />
      </div>
      <div>
        <span className="status-label">当前信号</span>
        <strong>{formatNullable(summary?.current_signal, "观望")}</strong>
      </div>
      <div>
        <span className="status-label">更新时间</span>
        <strong>{formatDateTime(summary?.last_update_time)}</strong>
      </div>
    </header>
  );
}
