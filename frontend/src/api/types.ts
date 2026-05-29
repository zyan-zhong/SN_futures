export type NullableNumber = number | null | undefined;

export interface TerminalSummary {
  sample?: boolean;
  sample_mode?: boolean;
  sample_banner_zh?: string;
  system_status?: string;
  data_quality_score?: NullableNumber;
  data_quality_label?: string;
  data_quality_components?: Record<string, unknown>;
  data_quality_blocking_reasons?: string[];
  data_quality_degradation_reasons?: string[];
  data_quality_next_actions_zh?: string[];
  main_contract?: string;
  latest_price?: NullableNumber;
  price_change?: NullableNumber;
  price_change_pct?: NullableNumber;
  current_signal?: string;
  model_status?: string;
  backtest_status?: string;
  risk_level?: string;
  last_update_time?: string;
  disclaimer?: string;
}

export interface PredictionCard {
  sample?: boolean;
  sample_mode?: boolean;
  sample_banner_zh?: string;
  message_zh?: string;
  horizon?: string;
  horizon_zh?: string;
  direction?: string;
  signal?: string;
  calibrated_prob_up?: NullableNumber;
  raw_prob_up?: NullableNumber;
  expected_return?: NullableNumber;
  predicted_range?: [NullableNumber, NullableNumber] | NullableNumber[];
  confidence_score?: NullableNumber;
  trade_edge?: NullableNumber;
  decision_explanation?: string;
  top_factors?: string[];
  event_evidence?: string[];
  risk_notes?: string[];
  data_quality?: NullableNumber;
  model_status?: string;
  backtest_summary?: Record<string, unknown>;
  path_guard_summary?: string;
  entry?: NullableNumber;
  stop_loss?: NullableNumber;
  take_profit?: NullableNumber;
  trade_point_note?: string;
}

export interface ModelHealth {
  active_model?: string;
  candidate_model?: string;
  degraded_models?: string[];
  promotion_status?: string;
  degradation_status?: string;
  metrics_by_horizon?: Record<string, unknown>;
  failure_reasons?: string[];
  last_check_time?: string;
}

export interface LearningStatus {
  latest_market_refresh?: string;
  latest_prediction?: string;
  latest_validation?: string;
  latest_calibration?: string;
  latest_candidate_training?: string;
  latest_walk_forward?: string;
  latest_event_ablation?: string;
  latest_promotion_check?: string;
  next_task?: string;
  active_candidate_state?: string;
  failure_reasons?: string[];
}

export interface BacktestDiagnostics {
  horizon?: string;
  walk_forward_metrics?: Record<string, unknown>;
  baseline_comparison?: Record<string, unknown>;
  cost_sensitivity?: Record<string, unknown>;
  by_regime?: Record<string, unknown>;
  by_signal_strength?: Record<string, unknown>;
  drawdown_periods?: Array<Record<string, unknown>>;
  promotion_gate_result?: string;
  failure_reasons?: string[];
}

export interface PositionScenarioInput {
  direction: "long" | "short" | "observe";
  contracts: number;
  entry_price: number;
  account_equity: number;
  max_acceptable_loss: number;
  horizon: string;
}

export interface PositionScenarioResult {
  input?: Record<string, unknown>;
  notional_exposure?: NullableNumber;
  margin_required?: NullableNumber;
  var_95?: NullableNumber;
  stress_var?: NullableNumber;
  max_loss_ratio?: NullableNumber;
  observation_zone?: Array<Record<string, unknown>>;
  risk_zone?: Array<Record<string, unknown>>;
  horizon_resonance?: string;
  event_evidence?: string[];
  uncertainty_notes?: string[];
  disclaimer?: string;
}

export interface DataSourceStatus {
  source_name?: string;
  enabled?: boolean;
  configured?: boolean;
  attempted?: boolean;
  success?: boolean;
  from_cache?: boolean;
  message_zh?: string;
  last_update?: string;
  stale?: boolean;
  status_code?: string;
  status_zh?: string;
  freshness_label?: string;
  last_success_time?: string;
  last_attempt_time?: string;
  ttl_seconds?: number | null;
  ttl_zh?: string;
  next_expected_update?: string | null;
  next_expected_update_time?: string | null;
  row_count?: number;
  error_code?: string;
  error_message_zh?: string;
  next_actions_zh?: string[];
  suggested_action_zh?: string;
}

export interface SystemHealth {
  health?: {
    api_status?: string;
    data_status?: string;
    model_status?: string;
    storage_status?: string;
    report_status?: string;
    frontend_status?: string;
    warnings?: string[];
    last_check_time?: string;
  };
  truth_audit?: Record<string, unknown>;
  disclaimer?: string;
}

export interface ReportItem {
  sample?: boolean;
  sample_mode?: boolean;
  type?: string;
  name?: string;
  title?: string;
  generated_at?: string;
  data_cutoff?: string;
  model_version?: string;
  data_quality_score?: NullableNumber;
  promotion_status?: string;
  promotion_gate_passed?: boolean;
  summary?: string;
  markdown?: string;
  disclaimer?: string;
}

export interface TerminalSnapshot {
  sample?: boolean;
  sample_mode?: boolean;
  sample_banner_zh?: string;
  message_zh?: string;
  summary?: TerminalSummary;
  predictions?: PredictionCard[];
  model_health?: ModelHealth;
  learning_status?: LearningStatus;
  backtest_diagnostics?: BacktestDiagnostics;
  data_status?: { sources?: DataSourceStatus[]; [key: string]: unknown };
  system_health?: SystemHealth;
  refresh_status?: RefreshStatus;
  disclaimer?: string;
}

export interface TerminalSettingsStatus {
  alpha_vantage_configured?: boolean;
  newsapi_configured?: boolean;
  managed_data_proxy_configured?: boolean;
  alpha_vantage_masked?: string;
  newsapi_masked?: string;
  managed_data_proxy_masked?: string;
  alpha_vantage_source?: string;
  newsapi_source?: string;
  managed_data_proxy_source?: string;
  alpha_vantage_source_label_zh?: string;
  newsapi_source_label_zh?: string;
  managed_data_proxy_source_label_zh?: string;
  alpha_vantage_ui_message_zh?: string;
  newsapi_ui_message_zh?: string;
  managed_data_proxy_ui_message_zh?: string;
  config_path?: string;
  user_data_dir?: string;
  logs_dir?: string;
  reports_dir?: string;
  api_base_url?: string;
  terminal_url?: string;
  last_update_time?: string;
  message_zh?: string;
  success?: boolean;
}

export interface KeyDiagnosticsItem {
  configured?: boolean;
  source?: string;
  source_label_zh?: string;
  masked?: string;
  can_read?: boolean;
  last_validation_status?: string;
  ui_message_zh?: string;
  message_zh?: string;
}

export interface KeyDiagnosticsPayload {
  success?: boolean;
  alpha_vantage?: KeyDiagnosticsItem;
  newsapi?: KeyDiagnosticsItem;
  managed_proxy?: KeyDiagnosticsItem;
  message_zh?: string;
}

export interface OnlineDataSourceEntry {
  source_id?: string;
  category?: string;
  provider?: string;
  enabled?: boolean;
  requires_key?: boolean;
  requires_paid_account?: boolean;
  client_upload_required?: boolean;
  priority?: number;
  ttl_seconds?: number;
  legal_note?: string;
  fields_provided?: string[];
  status?: string;
  last_success_time?: string;
  last_attempt_time?: string;
  cooldown_until?: string;
  row_count?: number;
  from_cache?: boolean;
  next_actions_zh?: string[];
}

export interface OnlineDataSourceRegistry {
  generated_at?: string;
  client_upload_required?: boolean;
  message_zh?: string;
  sources?: OnlineDataSourceEntry[];
}

export interface RuntimeDiagnosticFile {
  name?: string;
  relative_name?: string;
  path?: string;
  exists?: boolean;
  size?: number;
  modified_time?: string | null;
  json_valid?: boolean;
  has_cards?: boolean;
  card_count?: number;
  has_quote?: boolean;
  latest_price?: NullableNumber | string;
  report_length?: number;
}

export interface RuntimeDiagnostics {
  user_data_dir?: string;
  output_dir?: string;
  report_dir?: string;
  cache_dir?: string;
  config_dir?: string;
  secrets_path_exists?: boolean;
  alpha_vantage_configured?: boolean;
  newsapi_configured?: boolean;
  expected_output_files?: RuntimeDiagnosticFile[];
  event_store?: {
    has_news_events?: boolean;
    news_event_count?: number;
    stores?: Array<Record<string, unknown>>;
  };
  api_status?: Array<Record<string, unknown>>;
  data_gap_conclusion?: Record<string, boolean>;
  next_actions_zh?: string[];
  generated_at?: string;
  disclaimer?: string;
}

export interface RefreshStepStatus {
  step_name?: string;
  status?: "pending" | "running" | "success" | "failed" | "skipped" | string;
  started_at?: string;
  finished_at?: string;
  duration_seconds?: number | null;
  message_zh?: string;
  output_files?: string[];
  error?: string;
}

export interface RefreshStatus {
  run_id?: string;
  status?: string;
  started_at?: string;
  finished_at?: string;
  message_zh?: string;
  steps?: RefreshStepStatus[];
}

export interface RefreshLastErrorPayload {
  success?: boolean;
  has_error?: boolean;
  latest_error?: Record<string, unknown>;
  errors?: Array<Record<string, unknown>>;
  message_zh?: string;
  next_actions_zh?: string[];
  generated_at?: string;
}

export interface ProviderStatusDetailPayload {
  success?: boolean;
  data_status?: { sources?: DataSourceStatus[]; [key: string]: unknown };
  refresh_status?: RefreshStatus;
  market_provider_status?: Record<string, unknown>;
  news_provider_status?: Record<string, unknown>;
  message_zh?: string;
  generated_at?: string;
}

export interface ProviderTestPayload {
  success?: boolean;
  provider?: string;
  request_params_sanitized?: Record<string, unknown>;
  status?: Record<string, unknown>;
  message_zh?: string;
  next_actions_zh?: string[];
  generated_at?: string;
}

export interface DiagnosticsExportPayload {
  success?: boolean;
  path?: string;
  bundle?: Record<string, unknown>;
  message_zh?: string;
}

export interface PriceHistoryPoint {
  time?: string;
  open?: NullableNumber;
  high?: NullableNumber;
  low?: NullableNumber;
  close?: NullableNumber;
  volume?: NullableNumber;
  open_interest?: NullableNumber;
}

export interface PriceHistoryPayload {
  sample?: boolean;
  sample_mode?: boolean;
  sample_banner_zh?: string;
  symbol?: string;
  contract?: string;
  source?: string;
  data_quality_score?: NullableNumber;
  points?: PriceHistoryPoint[];
  message_zh?: string;
  disclaimer?: string;
}

export interface ForecastPathPoint {
  horizon?: string;
  time?: string;
  center?: NullableNumber;
  lower?: NullableNumber;
  upper?: NullableNumber;
  prob_up?: NullableNumber;
  signal?: string;
}

export interface ForecastPathPayload {
  sample?: boolean;
  sample_mode?: boolean;
  sample_banner_zh?: string;
  horizons?: string[];
  points?: ForecastPathPoint[];
  message_zh?: string;
  disclaimer?: string;
}

export interface NewsEventItem {
  sample?: boolean;
  title?: string;
  source?: string;
  published_at?: string;
  url?: string;
  category?: string;
  sentiment_score?: NullableNumber;
  impact_score?: NullableNumber;
  relevance_score?: NullableNumber;
  hard_evidence_score?: NullableNumber;
  source_reliability_score?: NullableNumber;
  source_domain?: string;
  domain_blacklist_penalty?: NullableNumber;
  allowed_for_event_factor?: boolean;
  used_in_model?: boolean;
  inclusion_reason?: string;
  exclusion_reason?: string;
  summary_zh?: string;
  query_group?: string;
  tin_entity_score?: NullableNumber;
  exchange_score?: NullableNumber;
  keyword_hits?: string[];
  negative_keyword_hits?: string[];
}

export interface NewsEventsPayload {
  sample?: boolean;
  sample_mode?: boolean;
  sample_banner_zh?: string;
  events?: NewsEventItem[];
  provider_status?: Record<string, unknown>;
  message_zh?: string;
  disclaimer?: string;
}

export interface NewsRelevanceDiagnosticsArticle {
  title?: string;
  source?: string;
  query_group?: string;
  relevance_score?: NullableNumber;
  tin_entity_score?: NullableNumber;
  hard_evidence_score?: NullableNumber;
  source_reliability_score?: NullableNumber;
  source_domain?: string;
  category?: string;
  used_in_model?: boolean;
  inclusion_reason?: string;
  exclusion_reason?: string;
  keyword_hits?: string[];
  negative_keyword_hits?: string[];
}

export interface NewsRelevanceDiagnosticsPayload {
  raw_article_count?: number;
  candidate_count?: number;
  used_in_model_count?: number;
  excluded_count?: number;
  articles?: NewsRelevanceDiagnosticsArticle[];
  query_groups?: Record<string, {
    returned_count?: number;
    used_in_model_count?: number;
    avg_relevance?: NullableNumber;
  }>;
  recommendations_zh?: string[];
  message_zh?: string;
}

export interface NewsSourceQualityReport {
  article_count?: number;
  used_in_model_count?: number;
  domains?: Array<{
    domain?: string;
    article_count?: number;
    used_in_model_count?: number;
    avg_source_reliability?: NullableNumber;
  }>;
  source_reliability?: { avg_score?: NullableNumber };
  message_zh?: string;
}

export interface EventEvidencePayload {
  sample?: boolean;
  sample_mode?: boolean;
  sample_banner_zh?: string;
  horizon?: string;
  events?: Array<Record<string, unknown>>;
  event_count?: number;
  recognized_event_count?: number;
  used_in_model_event_count?: number;
  rejected_event_count?: number;
  rejected_reason_breakdown?: Record<string, unknown>;
  message_zh?: string;
  disclaimer?: string;
  [key: string]: unknown;
}

export interface FullReportPayload {
  sample?: boolean;
  sample_mode?: boolean;
  sample_banner_zh?: string;
  type?: string;
  title?: string;
  generated_at?: string;
  data_cutoff?: string;
  markdown?: string;
  message_zh?: string;
  disclaimer?: string;
}

export interface FactorDiagnosticFeature {
  name?: string;
  value?: NullableNumber;
  ic?: NullableNumber;
  missing?: boolean;
  direction_hint?: string;
}

export interface FactorDiagnosticGroup {
  group?: string;
  features?: FactorDiagnosticFeature[];
}

export interface FactorDiagnosticsPayload {
  sample?: boolean;
  sample_mode?: boolean;
  sample_banner_zh?: string;
  groups?: FactorDiagnosticGroup[];
  missing_feature_report?: Record<string, unknown>;
  message_zh?: string;
  disclaimer?: string;
}

export interface FeatureCoverageFeature {
  name?: string;
  group?: string;
  non_null_count?: number;
  non_null_rate?: NullableNumber;
  latest_value?: NullableNumber | string;
  usable_for_training?: boolean;
  availability?: "available" | "partial" | "missing" | string;
  missing_reason?: string;
  required_columns?: string[];
  direction_hint?: string;
  description_zh?: string;
  lookback_window?: number;
}

export interface FeatureCoverageGroup {
  group?: string;
  feature_count?: number;
  available_feature_count?: number;
  partial_feature_count?: number;
  missing_feature_count?: number;
  coverage_rate?: NullableNumber;
  features?: FeatureCoverageFeature[];
}

export interface FeatureCoveragePayload {
  generated_at?: string;
  sample_count?: number;
  date_start?: string | null;
  date_end?: string | null;
  groups?: FeatureCoverageGroup[];
  usable_feature_cols?: string[];
  partial_feature_cols?: string[];
  not_usable_feature_cols?: string[];
  blocking_missing_fields?: string[];
  training_readiness?: {
    can_train_ohlcv_model?: boolean;
    can_train_full_fundamental_model?: boolean;
    reason_zh?: string;
  };
  message_zh?: string;
  warnings?: string[];
  data_quality_score?: NullableNumber;
  cross_market_diagnostics?: {
    date_start?: string | null;
    date_end?: string | null;
    exact_date_overlap_count?: number;
    aligned_non_null_count?: number;
    stale_row_count?: number;
    blocking_reasons?: string[];
    from_cache?: boolean;
    stale?: boolean;
    fields?: string[];
  };
}

export interface OnlineFieldReadiness {
  field?: string;
  category?: string;
  status?: string;
  source?: string;
  non_null_count?: number;
  row_count?: number;
  non_null_rate?: NullableNumber;
  aligned_non_null_count?: number;
  aligned_non_null_rate?: NullableNumber;
  usable_for_training?: boolean;
  from_cache?: boolean;
  stale?: boolean;
  cooldown_until?: string;
  latest_value?: NullableNumber | string;
  message_zh?: string;
}

export interface OnlineFactorGroupReadiness {
  group?: string;
  coverage_rate_before?: NullableNumber;
  coverage_rate_after?: NullableNumber;
  usable_now?: boolean;
  blocking_fields?: string[];
  online_fields_available?: string[];
}

export interface OnlineFeatureReadinessPayload {
  generated_at?: string;
  client_upload_required?: boolean;
  online_sources?: OnlineDataSourceEntry[];
  field_readiness?: OnlineFieldReadiness[];
  available_fields?: string[];
  unavailable_fields?: string[];
  factor_group_readiness?: OnlineFactorGroupReadiness[];
  cross_market_alignment_diagnostics?: Record<string, unknown>;
  research_readiness?: {
    can_train_ohlcv_technical_model?: boolean;
    can_train_online_cross_market_model?: boolean;
    can_train_basis_inventory_model?: boolean;
    can_train_full_institutional_model?: boolean;
    reason_zh?: string;
  };
  research_priority?: {
    can_continue_research?: string[];
    not_recommended_now?: string[];
    recommended_next_steps?: string[];
  };
  next_actions_zh?: string[];
  message_zh?: string;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
  baseline_used?: boolean;
}

export interface FeatureStoreStatus {
  version?: string;
  status?: string;
  exists?: boolean;
  generated_at?: string;
  row_count?: number;
  date_start?: string | null;
  date_end?: string | null;
  feature_store_path?: string;
  manifest_path?: string;
  field_sources?: Record<string, string>;
  alignment_rules?: Record<string, unknown>;
  forward_fill_rules?: Record<string, unknown>;
  stale_rules?: Record<string, unknown>;
  usable_fields?: string[];
  excluded_fields?: string[];
  exclusion_reasons?: Record<string, string>;
  leakage_check_pass?: boolean;
  sample_data_used?: boolean;
  baseline_used?: boolean;
  message_zh?: string;
}

export interface TrainingDatasetStatus {
  status?: string;
  exists?: boolean;
  message_zh?: string;
  manifest_path?: string;
  generated_at?: string;
  dataset_version?: string;
  feature_store_version?: string;
  feature_store_path?: string;
  feature_store_manifest_path?: string;
  feature_set?: string;
  horizons?: number[];
  feature_cols?: string[];
  cross_market_feature_cols?: string[];
  event_feature_cols?: string[];
  label_cols?: string[];
  removed_label_cols?: string[];
  forbidden_feature_patterns?: string[];
  leakage_check_pass?: boolean;
  leakage_check_details?: Record<string, unknown>;
  sample_data_used?: boolean;
  baseline_used?: boolean;
  sample_count_by_horizon?: Record<string, number>;
  feature_count?: number;
  date_start?: string;
  date_end?: string;
  missing_rate_by_feature?: Record<string, number>;
  label_distribution_by_horizon?: Record<string, Record<string, number>>;
  return_summary_by_horizon?: Record<string, Record<string, NullableNumber>>;
  data_source_hash?: string;
  dataset_paths?: Record<string, string>;
  dataset_outputs?: Record<string, Record<string, unknown>>;
  warnings?: string[];
}

export interface CandidateTrainingStatus {
  status?: string;
  message_zh?: string;
  generated_at?: string;
  candidate_version?: string;
  dataset_version?: string;
  feature_set?: string;
  candidate_is_active?: boolean;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
  baseline_scope?: string;
  registry_path?: string;
  records?: Array<Record<string, unknown>>;
  metrics_by_horizon?: Record<string, Record<string, NullableNumber | number | string>>;
  walk_forward_paths?: Record<string, string>;
}

export interface WalkForwardResultsPayload {
  status?: string;
  message_zh?: string;
  results?: Record<string, Record<string, unknown>>;
}

export interface PromotionGateDecision {
  model_id?: string;
  horizon?: string;
  passed?: boolean;
  checks?: Array<Record<string, unknown>>;
  failure_reasons?: string[];
  metrics?: Record<string, unknown>;
}

export interface PromotionReportPayload {
  status?: string;
  passed?: boolean;
  message_zh?: string;
  generated_at?: string;
  candidate_version?: string;
  dry_run?: boolean;
  decisions?: PromotionGateDecision[];
  passed_candidates?: PromotionGateDecision[];
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
  sample_data_used?: boolean;
  baseline_used?: boolean;
  promotion_report_path?: string;
  active_model_path?: string;
}

export interface ActiveModelStatus {
  status?: string;
  exists?: boolean;
  message_zh?: string;
  active_model_path?: string;
  active_models?: Array<Record<string, unknown>>;
  generated_at?: string;
}

export interface CandidateHorizonDiagnostics {
  failure_reasons?: string[];
  metric_summary?: Record<string, unknown>;
  fold_metrics?: Array<Record<string, unknown>>;
  oof_trace_summary?: OOFTraceSummary;
  confusion_matrix?: Record<string, unknown>;
  calibration_bins?: Array<Record<string, unknown>>;
  confidence_deciles?: Array<Record<string, unknown>>;
  top_confidence_metrics?: Record<string, unknown>;
  return_bucket_performance?: Array<Record<string, unknown>>;
  regime_performance?: Array<Record<string, unknown>>;
  drawdown_attribution?: Record<string, unknown>;
  high_confidence_wrong_samples?: Array<Record<string, unknown>>;
  feature_importance_top?: Array<Record<string, unknown>>;
  feature_importance_unstable?: Array<Record<string, unknown>>;
  label_difficulty?: Record<string, unknown>;
  error_diagnosis_zh?: string[];
  next_actions_zh?: string[];
}

export interface CandidateDiagnosticsPayload {
  status?: string;
  generated_at?: string;
  message_zh?: string;
  horizons?: Record<string, CandidateHorizonDiagnostics>;
  global_findings?: string[];
  recommended_research_plan?: string[];
  promotion_status?: string;
  active_written?: boolean;
  customer_prediction_generated?: boolean;
  gate_changed?: boolean;
  baseline_customer_prediction_used?: boolean;
  sample_data_used?: boolean;
}

export interface ModelResearchExperimentSummary {
  experiment_id?: string;
  status?: string;
  created_at?: string;
  message_zh?: string;
  artifact_dir?: string;
  active_updated?: boolean;
}

export interface ModelResearchExperimentList {
  experiments?: ModelResearchExperimentSummary[];
  count?: number;
}

export interface ModelResearchExperimentDetail {
  experiment_id?: string;
  artifact_dir?: string;
  experiment_summary?: Record<string, unknown>;
  config?: Record<string, unknown>;
  feature_set?: Record<string, unknown>;
  label_config?: Record<string, unknown>;
  walk_forward_results?: Record<string, unknown>;
  threshold_results?: Record<string, unknown>;
  calibration_report?: Record<string, unknown>;
  feature_stability?: Record<string, unknown>;
  promotion_preview?: Record<string, unknown>;
  status?: string;
  message_zh?: string;
}

export interface ThresholdOptimizationPayload {
  experiment_id?: string;
  threshold_results?: Record<string, unknown>;
  status?: string;
  message_zh?: string;
}

export interface OOFTraceSummary {
  status?: string;
  horizon?: string;
  path?: string;
  row_count?: number;
  fold_count?: number;
  date_start?: string;
  date_end?: string;
  confusion_matrix?: Record<string, unknown>;
  calibration_bins?: Array<Record<string, unknown>>;
  confidence_deciles?: Array<Record<string, unknown>>;
  top_10pct?: Record<string, unknown>;
  top_20pct?: Record<string, unknown>;
  regime_error_hotspots?: Array<Record<string, unknown>>;
  high_confidence_wrong_samples?: Array<Record<string, unknown>>;
  drawdown_contribution_samples?: Array<Record<string, unknown>>;
  summaries?: Record<string, OOFTraceSummary>;
  message_zh?: string;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
}

export interface OOFTraceSamplePayload {
  status?: string;
  horizon?: string;
  path?: string;
  rows?: Array<Record<string, unknown>>;
  limit?: number;
  message_zh?: string;
}

export interface HighConfidenceSubsetMetrics {
  coverage?: number;
  sample_count?: number;
  actual_coverage?: number;
  direction_accuracy?: number | null;
  balanced_accuracy?: number | null;
  precision_up?: number | null;
  precision_down?: number | null;
  realized_return_mean?: number | null;
  realized_return_median?: number | null;
  cost_adjusted_expectancy?: number | null;
  max_drawdown_proxy?: number | null;
  hit_rate_by_fold?: Array<Record<string, unknown>>;
  hit_rate_by_regime?: Array<Record<string, unknown>>;
  hit_rate_by_year?: Array<Record<string, unknown>>;
  turnover_proxy?: number | null;
  average_holding_horizon?: string;
  worst_fold_accuracy?: number | null;
  worst_regime_accuracy?: number | null;
  worst_year_accuracy?: number | null;
}

export interface OOFIntegrityHorizonReport {
  trace_rows?: number;
  fold_count?: number;
  leakage_checks?: Record<string, unknown>;
  fold_contribution?: Array<Record<string, unknown>>;
  time_period_contribution?: Array<Record<string, unknown>>;
  regime_contribution?: Array<Record<string, unknown>>;
  confidence_subset?: Record<string, HighConfidenceSubsetMetrics>;
  cost_adjusted_metrics?: Record<string, number | null>;
  drawdown_metrics?: Record<string, number | null>;
  preview?: Record<string, unknown>;
  integrity_pass?: boolean;
  blocking_reasons?: string[];
  warnings?: string[];
}

export interface OOFIntegrityReport {
  generated_at?: string;
  candidate_version?: string;
  dataset_version?: string;
  horizons?: Record<string, OOFIntegrityHorizonReport>;
  global_summary?: Record<string, unknown>;
  promotion_readiness?: "research_only" | "eligible_for_next_candidate" | "reject" | string;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
  promotion_gate_lowered?: boolean;
}

export interface HighConfidenceReport {
  status?: string;
  horizon?: string;
  confidence_subset?: Record<string, HighConfidenceSubsetMetrics>;
  blocking_reasons?: string[];
  warnings?: string[];
  preview?: Record<string, unknown>;
  message_zh?: string;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
}

export interface InstitutionalValidationReport {
  status?: string;
  passed?: boolean;
  generated_at?: string;
  candidate_version?: string;
  dry_run?: boolean;
  experiment_id?: string;
  deflated_sharpe_ratio?: Record<string, unknown>;
  probability_of_backtest_overfitting?: Record<string, unknown>;
  reality_check?: Record<string, unknown>;
  multiple_testing_correction?: Record<string, unknown>;
  combinatorial_purged_cv_summary?: Record<string, unknown>;
  cost_stress?: Record<string, Record<string, unknown>>;
  regime_stress?: Record<string, Record<string, unknown>>;
  feature_stability?: Record<string, unknown>;
  dominance_checks?: Record<string, unknown>;
  promotion_eligibility?: {
    eligible?: boolean;
    checks?: Array<Record<string, unknown>>;
    failure_reasons?: string[];
    message_zh?: string;
  };
  active_updated?: boolean;
  promotion_gate_lowered?: boolean;
  customer_prediction_generated?: boolean;
  message_zh?: string;
}

export interface InstitutionalStressTests {
  status?: string;
  cost_stress?: Record<string, Record<string, unknown>>;
  regime_stress?: Record<string, Record<string, unknown>>;
  message_zh?: string;
  generated_at?: string;
}

export interface ResearchBacktestHorizon {
  horizon?: string;
  status?: string;
  equity_curve_path?: string;
  drawdown_curve_path?: string;
  trades_path?: string;
  metrics_path?: string;
  metrics?: Record<string, unknown>;
}

export interface ResearchBacktestPayload {
  status?: string;
  candidate_version?: string;
  generated_at?: string;
  horizons?: Record<string, ResearchBacktestHorizon>;
  report_path?: string;
  markdown?: string;
  message_zh?: string;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
}

export interface ResearchEquityCurvePayload {
  status?: string;
  horizon?: string;
  path?: string;
  points?: Array<Record<string, unknown>>;
  message_zh?: string;
}

export interface ResearchArtifactsPayload {
  status?: string;
  run_id?: string;
  artifact_dir?: string;
  artifacts?: string[];
  runs?: Array<Record<string, unknown>>;
  count?: number;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
}

export interface StrategyOptimizationPayload {
  status?: string;
  candidate_version?: string;
  generated_at?: string;
  best_by_horizon?: Record<string, Record<string, unknown>>;
  all_trials_path?: string;
  report_path?: string;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
}

export interface CandidateV3ResearchPayload {
  status?: string;
  candidate_version?: string;
  dataset_version?: string;
  feature_store_version?: string;
  feature_set?: string;
  horizons?: string[];
  incremental_feature_cols?: string[];
  cross_market_feature_cols?: string[];
  event_feature_cols?: string[];
  reason_zh?: string;
  candidate?: CandidateTrainingStatus;
  institutional_validation?: InstitutionalValidationReport;
  promotion_dry_run?: PromotionReportPayload;
  research_backtest?: ResearchBacktestPayload;
  strategy_optimization?: StrategyOptimizationPayload;
  artifact_dir?: string;
  artifact_run_id?: string;
  message_zh?: string;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
}

export type CandidateV4ResearchPayload = CandidateV3ResearchPayload;
