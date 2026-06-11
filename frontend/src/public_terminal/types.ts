export type PublicStatus = "success" | "ready" | "blocked" | "stale" | "skipped" | "running" | "queued" | "failed" | "not_run" | string;

export type PublicTerminalRequestSchemaName =
  | "PublicEmptyRequest"
  | "PublicSettingsSaveRequest"
  | "PublicProviderSmokeRequest"
  | "PublicTaskPathRequest";

export type PublicTerminalResponseSchemaName =
  | "PublicTerminalOpenApiPayload"
  | "PublicReadinessPayload"
  | "PublicPredictionStatusPayload"
  | "PublicSettingsStatus"
  | "PublicSettingsSavePayload"
  | "PublicSmokePayload"
  | "PublicTaskPayload"
  | "PublicTaskCancelPayload"
  | "PublicMarketPayload"
  | "PublicEventsPayload"
  | "PublicReportPayload";

export interface PublicTerminalSideEffects {
  training: false;
  prediction: false;
  backtest: false;
  feature_store: false;
  real_api_default: false;
}

export interface PublicApiErrorPayload {
  error_code: string;
  message: string;
  blocking_reasons: string[];
  details_sanitized: Record<string, unknown>;
  status?: PublicStatus;
  reason?: string;
}

export interface PublicTerminalEndpointContract {
  method: "GET" | "POST";
  path: string;
  summary: string;
  request_schema_name: PublicTerminalRequestSchemaName;
  request_schema: Record<string, unknown>;
  response_schema_name: PublicTerminalResponseSchemaName;
  response_schema: Record<string, unknown>;
  error_schema_name: "PublicApiErrorPayload";
  error_schema: Record<string, unknown>;
  side_effect_classification: "read_only" | "writes_settings" | "starts_task" | "diagnostic_only";
  side_effects: PublicTerminalSideEffects;
  client_function: string;
  used_by: string[];
}

export interface PublicTerminalOpenApiPayload {
  schema_version: string;
  title: string;
  classification: "public";
  endpoints: PublicTerminalEndpointContract[];
  request_schemas: Record<PublicTerminalRequestSchemaName, Record<string, unknown>>;
  response_schemas: Record<PublicTerminalResponseSchemaName, Record<string, unknown>>;
  error_schema_name: "PublicApiErrorPayload";
  error_schema: Record<string, unknown>;
  side_effects: PublicTerminalSideEffects;
}

export interface PublicReadinessPayload {
  status?: PublicStatus;
  summary?: string;
  next_action?: string;
  provider_smoke_passed?: boolean;
  ready_for_refresh?: boolean;
  blocking_reasons?: string[];
  data_watermark?: Record<string, unknown>;
  provider_status?: Record<string, unknown>;
  prediction_readiness?: Record<string, unknown>;
  prediction_core_readiness?: {
    status?: PublicStatus;
    can_predict?: boolean;
    reason?: string;
    active_release_safe?: boolean;
    missing_evidence?: string[];
    blocking_reasons?: string[];
  };
}

export interface PublicPredictionStatusPayload {
  schema_version?: string;
  prediction_status?: {
    schema_version?: string;
    status?: PublicStatus;
    dry_run?: boolean;
    can_predict?: boolean;
    ready_to_generate_prediction?: boolean;
    reason?: string;
    checked_at?: string;
    next_allowed_at?: string;
    blocking_reasons?: string[];
    missing_evidence?: string[];
    active_release_safe?: boolean;
    readiness_status?: string;
    latest_quote?: {
      received?: boolean;
      symbol?: string;
      quote_time?: string;
    };
    worker_pool?: Record<string, unknown>;
    loop_state?: Record<string, unknown>;
    training_invoked?: false;
    prediction_generated?: false;
    backtest_invoked?: false;
    feature_store_written?: false;
    production_cache_written?: false;
    customer_prediction_generated?: false;
  };
  training_invoked?: false;
  prediction_generated?: false;
  backtest_invoked?: false;
  customer_prediction_generated?: false;
}

export interface PublicSettingsStatus {
  configured?: boolean;
  masked?: string;
  sources?: Array<{ id?: string; label?: string; configured?: boolean; masked?: string }>;
  local_api_provider_token_masked?: string;
  tushare_token_masked?: string;
}

export interface PublicSettingsSavePayload extends PublicSettingsStatus {
  success?: boolean;
  message?: string;
  message_zh?: string;
}

export interface PublicSettingsSaveInput {
  base_url?: string;
  token?: string;
  provider?: string;
}

export interface PublicProviderSmokeInput {
  allow_remote?: boolean;
  provider?: string;
}

export interface PublicSmokePayload {
  status?: PublicStatus;
  error_code?: string;
  row_count?: number;
  source_statuses?: Array<Record<string, unknown>>;
  manifest?: Record<string, unknown>;
  blocking_reasons?: string[];
  training_invoked?: boolean;
  prediction_generated?: boolean;
  backtest_invoked?: boolean;
}

export interface PublicTaskPayload {
  task_id?: string;
  status?: PublicStatus;
  progress?: number;
  reason?: string;
  result?: Record<string, unknown>;
  provider_coverage?: Array<Record<string, unknown>>;
  missing_data?: string[];
  training_invoked?: boolean;
  prediction_generated?: boolean;
  backtest_invoked?: boolean;
}

export interface PublicTaskCancelPayload {
  task_id?: string;
  status?: PublicStatus;
  cancel_requested?: boolean;
  message?: string;
  reason?: string;
}

export interface PublicMarketPayload {
  market?: {
    status?: PublicStatus;
    reason?: string;
    chart?: PublicMarketBar[];
    kline?: {
      status?: PublicStatus;
      timeframe?: string;
      bars?: PublicMarketBar[];
    };
    watch_header?: {
      status?: PublicStatus;
      symbol?: string;
      latest_price?: number | null;
      daily_close?: number | null;
      latest_quote_display_only?: boolean;
      quote_time?: string;
      trade_date?: string;
      volume?: number | string | null;
      open_interest?: number | string | null;
    };
    inventory?: {
      warehouse_warrant?: number | string | null;
      inventory?: number | string | null;
      volume?: number | string | null;
      open_interest?: number | string | null;
    };
    latest_quote?: Record<string, unknown> | null;
    indicators?: {
      status?: PublicStatus;
      values?: Record<string, number>;
      blocking_reasons?: string[];
      manifest?: Record<string, unknown>;
    };
    data_watermark?: Record<string, unknown>;
    data_watermark_panel?: {
      display_allowed?: boolean;
      prediction_allowed?: boolean;
      cache_status?: string;
      stale_status?: string;
      source_published_at?: string;
    };
    missing_data?: {
      reasons?: string[];
    };
    sample_data_used?: boolean;
    baseline_used?: boolean;
    customer_prediction_generated?: boolean;
  };
}

export interface PublicMarketBar {
  date?: string;
  time?: string;
  symbol?: string;
  open?: number | string | null;
  high?: number | string | null;
  low?: number | string | null;
  close?: number | string | null;
  volume?: number | string | null;
  open_interest?: number | string | null;
  warehouse_warrant?: number | string | null;
  inventory?: number | string | null;
  source_published_at?: string;
}

export interface PublicEventCenterSummary {
  total_count?: number;
  eligible_count?: number;
  rejected_count?: number;
  categories?: Record<string, number>;
  regions?: Record<string, number>;
  languages?: Record<string, number>;
  latest_source_published_at?: string;
  latest_fetched_at?: string;
}

export interface PublicEventItem {
  event_id?: string;
  title?: string;
  summary?: string;
  url?: string;
  source_name?: string;
  provider_id?: string;
  data_kind?: string;
  source_published_at?: string;
  fetched_at?: string;
  category?: string;
  region?: string;
  language?: string;
  relevance_score?: number;
  relevance_to_shfe_sn?: boolean;
  used_in_model?: boolean;
  eligible_for_event_factor?: boolean;
  blocking_reasons?: string[];
}

export interface PublicEventsPayload {
  event_center?: {
    status?: PublicStatus;
    reason?: string;
    events?: PublicEventItem[];
    summary?: PublicEventCenterSummary;
    categories?: Record<string, number>;
    regions?: Record<string, number>;
    languages?: Record<string, number>;
    sample_data_used?: boolean;
    baseline_used?: boolean;
    customer_prediction_generated?: boolean;
  };
  training_invoked?: boolean;
  prediction_generated?: boolean;
  backtest_invoked?: boolean;
}

export interface PublicReportPayload {
  report?: {
    status?: PublicStatus;
    reason?: string;
    provider_status?: string;
    market_data_coverage?: string;
    event_coverage?: string;
    event_count?: number;
    timed_event_count?: number;
    event_summary?: PublicEventCenterSummary;
    research_only?: boolean;
    investment_advice?: boolean;
    export_allowed?: boolean;
  };
}
