import clsx from "clsx";
import {
  Activity,
  BarChart3,
  Boxes,
  Brain,
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
  { key: "market", label: "行情监控", helper: "quote、图表、provider", icon: BarChart3 },
  { key: "events", label: "新闻与事件", helper: "入模事件与排除原因", icon: Newspaper },
  { key: "factors", label: "因子研究", helper: "coverage 与 Feature Store", icon: Gauge },
  { key: "training", label: "训练数据", helper: "v1-v4 manifest", icon: Database },
  { key: "research", label: "模型研究", helper: "candidate、OOF、gate", icon: Brain },
  { key: "backtest", label: "回测验证", helper: "收益曲线与压力测试", icon: Activity },
  { key: "predictions", label: "预测观察", helper: "active-only 观察", icon: ShieldCheck },
  { key: "reports", label: "报告中心", helper: "报告与 Artifact Center", icon: FileText },
  { key: "settings", label: "设置与诊断", helper: "密钥、日志、数据源", icon: Settings }
];

const advancedItems: Array<{ key: PageKey; label: string; icon: typeof Home }> = [
  { key: "data", label: "数据源诊断", icon: Database },
  { key: "governance", label: "模型治理明细", icon: ShieldCheck },
  { key: "position", label: "持仓情景", icon: Boxes }
];

const legacyNavigationAliases = ["刷新与数据源", "行情与新闻", "因子诊断"];
void legacyNavigationAliases;

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
