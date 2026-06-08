import type { DataSourceStatus, TerminalSettingsStatus, TerminalSnapshot } from "../api/types";

export type LocalSetupSummary = {
  alpha_vantage_configured: boolean;
  newsapi_configured: boolean;
  tushare_configured: boolean;
  local_api_provider_configured: boolean;
};

export type ProviderSetupCard = {
  providerId: string;
  label: string;
  configured: boolean;
  status: "configured" | "not_configured";
  nextAction: string;
};

export type PredictionEmptyStateModel = {
  title: string;
  status: string;
  summary: string;
  reasons: string[];
  nextActions: string[];
};

const providerDefinitions = [
  {
    providerId: "alpha_vantage",
    label: "Alpha Vantage",
    summaryKey: "alpha_vantage_configured",
    nextAction: "Configure SN_ALPHA_VANTAGE_KEY locally, then refresh provider status."
  },
  {
    providerId: "newsapi",
    label: "NewsAPI",
    summaryKey: "newsapi_configured",
    nextAction: "Configure SN_NEWSAPI_KEY locally, then run a news provider smoke test."
  },
  {
    providerId: "tushare",
    label: "Tushare",
    summaryKey: "tushare_configured",
    nextAction: "Configure SN_TUSHARE_TOKEN locally for futures fundamentals."
  },
  {
    providerId: "local_api_provider",
    label: "Local API Provider",
    summaryKey: "local_api_provider_configured",
    nextAction: "Configure SN_LOCAL_API_PROVIDER_* locally, then run provider smoke."
  }
] as const;

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function summaryFromSources(sources?: DataSourceStatus[]): LocalSetupSummary {
  const sourceById = new Map((sources ?? []).map((source) => [String(source.provider_id || source.source_key || "").toLowerCase(), source]));
  const configured = (providerId: string) => Boolean(sourceById.get(providerId)?.configured);
  return {
    alpha_vantage_configured: configured("alpha_vantage"),
    newsapi_configured: configured("newsapi"),
    tushare_configured: configured("tushare"),
    local_api_provider_configured: configured("local_api_provider"),
  };
}

export function buildLocalFirstStatusModel(snapshot?: TerminalSnapshot | null, settings?: TerminalSettingsStatus | null) {
  const snapshotRecord = asRecord(snapshot);
  const dataStatus = asRecord(snapshot?.data_status);
  const embeddedSummary = asRecord(dataStatus.local_setup_summary);
  const snapshotSummary = asRecord(snapshotRecord.local_setup_summary);
  const fallbackSummary = summaryFromSources(snapshot?.data_status?.sources);
  const localSetupSummary: LocalSetupSummary = {
    alpha_vantage_configured: Boolean(settings?.alpha_vantage_configured ?? embeddedSummary.alpha_vantage_configured ?? snapshotSummary.alpha_vantage_configured ?? fallbackSummary.alpha_vantage_configured),
    newsapi_configured: Boolean(settings?.newsapi_configured ?? embeddedSummary.newsapi_configured ?? snapshotSummary.newsapi_configured ?? fallbackSummary.newsapi_configured),
    tushare_configured: Boolean(settings?.tushare_configured ?? embeddedSummary.tushare_configured ?? snapshotSummary.tushare_configured ?? fallbackSummary.tushare_configured),
    local_api_provider_configured: Boolean(settings?.local_api_provider_configured ?? embeddedSummary.local_api_provider_configured ?? snapshotSummary.local_api_provider_configured ?? fallbackSummary.local_api_provider_configured),
  };
  const providerSetupCards = getProviderSetupCards(localSetupSummary);
  const configuredCount = providerSetupCards.filter((card) => card.configured).length;
  const hasRealData = !snapshot?.sample_mode && Boolean(snapshot?.summary?.latest_price || snapshot?.summary?.last_update_time);
  const predictionBlocked = !snapshot?.predictions?.length;
  return {
    localSetupSummary,
    providerSetupCards,
    configuredCount,
    hasRealData,
    predictionBlocked,
    status: configuredCount > 0 ? "partially_configured" : "not_configured",
    nextActions: (dataStatus.local_first_next_actions as string[] | undefined) ?? (snapshotRecord.local_first_next_actions as string[] | undefined) ?? [
      "Configure local provider keys",
      "Run provider smoke after configuration",
      "Refresh market data only after provider status is clear",
    ],
  };
}

export function getProviderSetupCards(summaryOrSnapshot?: LocalSetupSummary | TerminalSnapshot | null): ProviderSetupCard[] {
  const summary = "summary" in asRecord(summaryOrSnapshot)
    ? buildLocalFirstStatusModel(summaryOrSnapshot as TerminalSnapshot).localSetupSummary
    : {
        alpha_vantage_configured: Boolean((summaryOrSnapshot as LocalSetupSummary | undefined)?.alpha_vantage_configured),
        newsapi_configured: Boolean((summaryOrSnapshot as LocalSetupSummary | undefined)?.newsapi_configured),
        tushare_configured: Boolean((summaryOrSnapshot as LocalSetupSummary | undefined)?.tushare_configured),
        local_api_provider_configured: Boolean((summaryOrSnapshot as LocalSetupSummary | undefined)?.local_api_provider_configured),
      };
  return providerDefinitions.map((provider) => {
    const configured = summary[provider.summaryKey];
    return {
      providerId: provider.providerId,
      label: provider.label,
      configured,
      status: configured ? "configured" : "not_configured",
      nextAction: configured ? "Configured. Run provider smoke before trusting downstream gates." : provider.nextAction,
    };
  });
}

export function getPredictionEmptyState(snapshot?: TerminalSnapshot | null): PredictionEmptyStateModel {
  const reasons = [
    "数据源未配置或真实数据水位未通过。",
    "预测已阻断：不会生成客户预测、不会训练模型、不会写 active。",
    "暂无真实预测；sample/demo 不会在默认主路径展示。",
  ];
  const nextActions = buildLocalFirstStatusModel(snapshot).nextActions;
  return {
    title: "暂无真实预测",
    status: "预测已阻断",
    summary: "数据源未配置或真实数据不足。研究参考，不构成投资建议。",
    reasons,
    nextActions,
  };
}
