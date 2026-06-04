import clsx from "clsx";
import {
  Activity,
  Archive,
  BarChart3,
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
import type { UIMode } from "../../context/UIModeContext";

type NavItem = { key: PageKey; label: string; helper?: string; icon: typeof Home };

const simpleItems: NavItem[] = [
  { key: "terminal-overview", label: "Terminal Overview", helper: "state / next action", icon: Home },
  { key: "prediction-workspace", label: "Prediction Workspace", helper: "blocked placeholder", icon: ShieldCheck },
  { key: "data-onboarding", label: "Data Onboarding", helper: "Managed Proxy / v12", icon: Database },
  { key: "candidate-research", label: "Candidate Research", helper: "v10 / v12 summary", icon: Brain },
  { key: "research-governance", label: "Governance Console", helper: "safe checks", icon: ShieldCheck },
  { key: "settings", label: "Settings", helper: "diagnostics", icon: Settings }
];

const professionalItems: NavItem[] = [
  { key: "market", label: "Market Monitor", helper: "quote / chart / provider", icon: BarChart3 },
  { key: "events", label: "News and Events", helper: "events / exclusion", icon: Newspaper },
  { key: "factors", label: "Feature Store / Dataset", helper: "coverage / feature store", icon: Gauge },
  { key: "training", label: "Training Data", helper: "manifest / labels", icon: Database },
  { key: "research", label: "Model Research", helper: "candidate / OOF / gate", icon: Brain },
  { key: "research-governance", label: "Research Governance", helper: "safe checks / blockers", icon: ShieldCheck },
  { key: "backtest", label: "Backtest Validation", helper: "equity / drawdown", icon: Activity },
  { key: "predictions", label: "Prediction Observation", helper: "active-only", icon: ShieldCheck },
  { key: "reports", label: "Report Center", helper: "Artifact Center", icon: FileText },
  { key: "data", label: "Artifact Center", helper: "data source status", icon: Database },
  { key: "settings", label: "Settings and Diagnostics", helper: "keys / logs / report", icon: Settings },
  { key: "terminal-overview", label: "Terminal Overview", helper: "state / next action", icon: Home },
  { key: "prediction-workspace", label: "Prediction Workspace", helper: "blocked placeholder", icon: ShieldCheck },
  { key: "data-onboarding", label: "Data Onboarding", helper: "Managed Proxy / v12", icon: Database },
  { key: "candidate-research", label: "Candidate Research", helper: "v10 / v12 summary", icon: Brain },
  { key: "research-archive", label: "Research Archive", helper: "collapsed history", icon: Archive }
];

function NavButton({
  current,
  item,
  onNavigate,
  compact
}: {
  current: PageKey;
  item: NavItem;
  onNavigate: (page: PageKey) => void;
  compact?: boolean;
}) {
  const Icon = item.icon;
  return (
    <button
      className={clsx("nav-item", compact && "compact-nav-item", current === item.key && "active")}
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

export function SimpleSidebar({
  current,
  mode,
  onModeChange,
  onNavigate
}: {
  current: PageKey;
  mode: UIMode;
  onModeChange: (mode: UIMode) => void;
  onNavigate: (page: PageKey) => void;
}) {
  const isProfessional = mode === "professional";
  const items = isProfessional ? professionalItems : simpleItems;

  return (
    <aside className="sidebar">
      <div className="brand">
        <Landmark />
        <div>
          <strong>SNInsightTerminal</strong>
          <span>{isProfessional ? "Professional workspace" : "Simple workspace"}</span>
        </div>
      </div>

      <div className="mode-switch" role="group" aria-label="Display mode">
        <button
          className={!isProfessional ? "active" : ""}
          data-testid="ui-mode-toggle"
          type="button"
          onClick={() => onModeChange("simple")}
        >
          Simple
        </button>
        <button
          className={isProfessional ? "active" : ""}
          type="button"
          onClick={() => onModeChange("professional")}
        >
          Professional
        </button>
      </div>

      <nav
        aria-label={isProfessional ? "Professional navigation" : "Simple navigation"}
        className="primary-nav"
        data-testid={isProfessional ? "professional-nav" : "simple-nav"}
      >
        {items.map((item) => (
          <NavButton compact={!isProfessional} current={current} item={item} key={`${mode}-${item.label}-${item.key}`} onNavigate={onNavigate} />
        ))}
      </nav>
    </aside>
  );
}
