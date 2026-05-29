import clsx from "clsx";
import {
  Activity,
  BarChart3,
  Boxes,
  Database,
  FileText,
  Gauge,
  Home,
  Landmark,
  Newspaper,
  Settings,
  ShieldCheck
} from "lucide-react";
import type { PageKey } from "../../App";

const primaryItems: Array<{ key: PageKey; label: string; helper: string; icon: typeof Home }> = [
  { key: "dashboard", label: "总览", helper: "系统、数据、风险", icon: Home },
  { key: "data", label: "刷新与数据源", helper: "一键刷新与诊断", icon: Database },
  { key: "events", label: "行情与新闻", helper: "价格图与事件", icon: Newspaper },
  { key: "predictions", label: "预测观察", helper: "七周期研究观察", icon: Gauge },
  { key: "backtest", label: "回测验证", helper: "Walk-forward 与成本", icon: Activity },
  { key: "reports", label: "报告中心", helper: "日报、周报、事件报告", icon: FileText },
  { key: "settings", label: "设置与诊断", helper: "密钥、日志、系统信息", icon: Settings }
];

const advancedItems: Array<{ key: PageKey; label: string; icon: typeof Home }> = [
  { key: "factors", label: "因子诊断", icon: BarChart3 },
  { key: "governance", label: "模型治理", icon: ShieldCheck },
  { key: "research", label: "研究实验室", icon: Activity },
  { key: "position", label: "持仓情景", icon: Boxes }
];

function NavButton({
  current,
  item,
  onNavigate,
  compact = false
}: {
  current: PageKey;
  item: { key: PageKey; label: string; helper?: string; icon: typeof Home };
  onNavigate: (page: PageKey) => void;
  compact?: boolean;
}) {
  const Icon = item.icon;
  return (
    <button
      className={clsx("nav-item", compact && "compact-nav-item", current === item.key && "active")}
      key={item.key}
      type="button"
      aria-current={current === item.key ? "page" : undefined}
      onClick={() => onNavigate(item.key)}
    >
      <Icon size={18} />
      <span>
        <strong>{item.label}</strong>
        {item.helper ? <em>{item.helper}</em> : null}
      </span>
    </button>
  );
}

export function Sidebar({ current, onNavigate }: { current: PageKey; onNavigate: (page: PageKey) => void }) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <Landmark />
        <div>
          <strong>SNInsightTerminal</strong>
          <span>沪锡量化投研终端</span>
        </div>
      </div>
      <nav aria-label="主导航" className="primary-nav">
        {primaryItems.map((item) => (
          <NavButton current={current} item={item} key={item.key} onNavigate={onNavigate} />
        ))}
      </nav>
      <details className="advanced-nav">
        <summary>高级模式 / 技术明细</summary>
        <div className="advanced-nav-list">
          {advancedItems.map((item) => (
            <NavButton compact current={current} item={item} key={item.key} onNavigate={onNavigate} />
          ))}
        </div>
      </details>
    </aside>
  );
}
