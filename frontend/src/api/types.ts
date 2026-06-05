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

export interface LearningSchedulerTask {
  task?: string;
  status?: string;
  ran_at?: string;
  message_zh?: string;
  error_message_zh?: string;
  payload?: Record<string, unknown>;
}

export interface LearningSchedulerStatus {
  status?: string;
  paused?: boolean;
  generated_at?: string;
  last_run_at?: string;
  next_run_at?: string;
  next_task?: string;
  tasks?: LearningSchedulerTask[];
  last_failure_reasons?: string[];
  artifact_dir?: string;
  artifact_run_id?: string;
  manual_approval_required?: boolean;
  manual_approval_message_zh?: string;
  auto_active_disabled?: boolean;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
  message_zh?: string;
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
  provider_id?: string;
  source_name?: string;
  source_key?: string;
  source_file?: string;
  provider_status_source?: string;
  enabled?: boolean;
  configured?: boolean;
  attempted?: boolean;
  success?: boolean;
  from_cache?: boolean;
  message_zh?: string;
  last_update?: string;
  stale?: boolean;
  status_code?: "optional_failed" | string;
  severity?: "optional_failed" | string;
  optional?: boolean;
  blocks_market?: boolean;
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
  status_time?: string;
  data_time?: string;
  report_time?: string;
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

export interface ProcessStatusPayload {
  generated_at?: string;
  pid?: number | null;
  port?: number | null;
  host?: string;
  session_id?: string;
  started_at?: string;
  shutdown_requested?: boolean;
  shutdown_at?: string;
  pid_file_exists?: boolean;
  pid_running?: boolean;
  stale?: boolean;
  runtime_dir?: string;
  message_zh?: string;
}

export interface BackendShutdownPayload {
  status?: string;
  shutdown_at?: string;
  reason?: string;
  pid_file_exists?: boolean;
  accepting_new_tasks?: boolean;
  http_shutdown_scheduled?: boolean;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
  message_zh?: string;
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
  local_api_provider_enabled?: boolean;
  local_api_provider_configured?: boolean;
  local_api_provider_token_configured?: boolean;
  local_api_provider_base_url_configured?: boolean;
  local_api_provider_id?: string;
  local_api_provider_id_source?: string;
  local_api_provider_base_url?: string;
  local_api_provider_base_url_source?: string;
  local_api_provider_token_masked?: string;
  local_api_provider_source?: string;
  local_api_provider_deprecated?: boolean;
  local_api_provider_deprecated_warnings?: string[];
  managed_data_proxy_configured?: boolean;
  managed_data_proxy_endpoint_configured?: boolean;
  tushare_configured?: boolean;
  alpha_vantage_masked?: string;
  newsapi_masked?: string;
  managed_data_proxy_masked?: string;
  managed_data_proxy_endpoint?: string;
  tushare_masked?: string;
  alpha_vantage_source?: string;
  newsapi_source?: string;
  managed_data_proxy_source?: string;
  tushare_source?: string;
  alpha_vantage_source_label_zh?: string;
  newsapi_source_label_zh?: string;
  local_api_provider_source_label_zh?: string;
  managed_data_proxy_source_label_zh?: string;
  tushare_source_label_zh?: string;
  alpha_vantage_ui_message_zh?: string;
  newsapi_ui_message_zh?: string;
  local_api_provider_ui_message_zh?: string;
  managed_data_proxy_ui_message_zh?: string;
  tushare_ui_message_zh?: string;
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
  deprecated?: boolean;
  deprecated_warning?: string;
  can_read?: boolean;
  last_validation_status?: string;
  ui_message_zh?: string;
  message_zh?: string;
}

export interface KeyDiagnosticsPayload {
  success?: boolean;
  alpha_vantage?: KeyDiagnosticsItem;
  newsapi?: KeyDiagnosticsItem;
  local_api_provider?: KeyDiagnosticsItem;
  managed_proxy?: KeyDiagnosticsItem;
  tushare?: KeyDiagnosticsItem;
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

export interface ManagedProxyHealthPayload {
  status?: string;
  provider_status?: string;
  enabled?: boolean;
  configured?: boolean;
  endpoint_configured?: boolean;
  token_configured?: boolean;
  token_masked?: string;
  token_source?: string;
  last_refresh_time?: string;
  last_success_time?: string;
  row_count?: number;
  from_cache?: boolean;
  required_fields?: string[];
  available_fields?: string[];
  missing_fields?: string[];
  group_ready?: Record<string, boolean>;
  required_field_coverage?: {
    total?: number;
    available?: number;
    missing?: number;
    ratio?: number;
    label?: string;
  };
  blocking_reasons?: string[];
  next_allowed_action?: string;
  v12_allowed?: boolean;
  ready?: boolean;
  no_fake_data?: boolean;
  active_model_written?: boolean;
  customer_prediction_generated?: boolean;
  generated_at?: string;
  output_path?: string;
  message_zh?: string;
  error_message_zh?: string;
}

export interface ManagedProxyReliabilityPayload {
  status?: string;
  reliability_version?: string;
  generated_at?: string;
  canary_status?: string;
  latency_ms?: number | null;
  latency_summary?: {
    count?: number;
    min_ms?: number | null;
    median_ms?: number | null;
    max_ms?: number | null;
    p95_ms?: number | null;
  };
  timeout_count?: number;
  error_rate?: number;
  response_size_bytes?: number;
  max_response_bytes?: number;
  schema_drift_status?: string;
  provider_fields_seen?: string[];
  schema_missing_fields?: string[];
  cache_staleness_status?: string;
  cache_age_hours?: number | null;
  circuit_breaker_status?: string;
  consecutive_failure_count?: number;
  blocking_reasons?: string[];
  warning_reasons?: string[];
  next_allowed_action?: string;
  training_invoked?: boolean;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
  fake_data_used?: boolean;
  mock_data_used?: boolean;
  report_path?: string;
  message_zh?: string;
  error_message_zh?: string;
}

export interface ManagedDataQualityPayload {
  status?: string;
  quality_version?: string;
  generated_at?: string;
  row_count?: number;
  date_range?: {
    date_start?: string | null;
    date_end?: string | null;
  };
  null_rate_by_field?: Record<string, number>;
  duplicate_key_count?: number;
  invalid_value_count?: number;
  outlier_summary?: {
    status?: string;
    outlier_count?: number;
    blocking_reasons?: string[];
    warning_reasons?: string[];
    basis?: Record<string, unknown>;
    inventory?: Record<string, unknown>;
  };
  contract_switch_anomaly_summary?: {
    status?: string;
    max_consecutive_switches?: number;
    invalid_flag_count?: number;
    blocking_reasons?: string[];
    warning_reasons?: string[];
  };
  quality_score?: number;
  gate_passed?: boolean;
  blocking_reasons?: string[];
  warning_reasons?: string[];
  training_invoked?: boolean;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
  fake_data_used?: boolean;
  mock_data_used?: boolean;
  scorecard_path?: string;
  message_zh?: string;
}

export interface ManagedProxyAuditPayload {
  status?: string;
  audit_version?: string;
  managed_proxy_status?: Record<string, unknown>;
  row_count?: number;
  required_timestamp_fields?: string[];
  missing_timestamp_fields?: string[];
  required_fundamental_fields?: string[];
  missing_fundamental_fields?: string[];
  field_timestamp_coverage?: {
    row_count?: number;
    complete_rows?: number;
    complete_ratio?: number;
    by_field?: Record<string, { present?: number; missing?: number; coverage?: number }>;
  };
  field_lag_summary?: {
    min_lag_days?: number | null;
    median_lag_days?: number | null;
    max_lag_days?: number | null;
    rows_with_negative_lag?: number;
    rows_with_missing_lag?: number;
    by_field?: Record<string, Record<string, unknown>>;
  };
  leakage_checks?: Record<string, boolean | number | string | null | undefined>;
  blocking_reasons?: string[];
  managed_data_used?: boolean;
  fake_data_used?: boolean;
  mock_data_used?: boolean;
  training_invoked?: boolean;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
  manifest_path?: string;
  v12_allowed?: boolean;
  ready?: boolean;
  message_zh?: string;
}

export interface ManagedPitReplayPayload {
  status?: string;
  replay_version?: string;
  generated_at?: string;
  cases_run?: number;
  cases_passed?: number;
  cases_failed?: number;
  selected_rows?: Array<Record<string, unknown>>;
  rejected_future_rows?: Array<Record<string, unknown>>;
  ingest_timestamp_misuse_detected?: boolean;
  deterministic_tiebreak_status?: string;
  blocking_reasons?: string[];
  point_in_time_join_ready?: boolean;
  training_invoked?: boolean;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
  report_path?: string;
}

export interface ManagedProxySetupPayload {
  status?: string;
  setup_version?: string;
  generated_at?: string;
  enabled?: boolean;
  configured?: boolean;
  base_url_configured?: boolean;
  token_configured?: boolean;
  token_masked?: string;
  token_source?: string;
  base_url_source?: string;
  timeout_seconds?: number;
  endpoint_contract_status?: string;
  schema_contract_status?: string;
  pit_timestamp_contract_status?: string;
  required_fields?: string[];
  missing_fields?: string[];
  required_timestamp_fields?: string[];
  missing_timestamp_fields?: string[];
  dry_run_row_count?: number;
  blocking_reasons?: string[];
  warning_reasons?: string[];
  next_allowed_action?: string;
  managed_proxy_health_allowed?: boolean;
  pit_audit_allowed?: boolean;
  feature_store_v12_allowed?: boolean;
  training_invoked?: boolean;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
  no_fake_data?: boolean;
  report_path?: string;
}

export type SetupChecklistStepStatus = "complete" | "blocked" | "available" | "locked" | "running" | "failed";

export interface SetupChecklistStepPayload {
  step_id?: string;
  label?: string;
  status?: SetupChecklistStepStatus | string;
  short_reason?: string;
  safe_action_id?: string;
  action_enabled?: boolean;
  action_disabled_reason?: string;
  evidence_path?: string;
  is_current_step?: boolean;
}

export interface SetupActionRunPayload {
  run_id?: string;
  action_id?: string;
  action_label?: string;
  started_at?: string;
  finished_at?: string;
  duration_ms?: number;
  status?: "success" | "failed" | "blocked" | "skipped" | string;
  blocking_reasons?: string[];
  next_allowed_action?: string;
  triggered_endpoint?: string;
  run_type?: string;
  action_scope?: string;
  forbidden_side_effects?: string[];
  input_redacted?: boolean;
  output_redacted?: boolean;
  training_invoked?: boolean;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
}

export interface SetupActionTelemetryPayload {
  status?: string;
  latest_action?: string;
  latest_action_status?: string;
  latest_failure_reason?: string[];
  successful_action_count?: number;
  failed_action_count?: number;
  blocked_action_count?: number;
  last_successful_step?: string;
  current_step?: string;
  recommended_next_action?: string;
  feature_store_v12_allowed?: boolean;
  is_prediction_failure?: boolean;
  training_invoked?: boolean;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
}

export interface SetupChecklistStatusPayload {
  status?: string;
  generated_at?: string;
  checklist_version?: string;
  current_step?: string;
  steps?: SetupChecklistStepPayload[];
  enabled_safe_actions?: string[];
  locked_steps?: string[];
  safe_actions?: string[];
  unsafe_actions?: string[];
  blocking_reasons?: string[];
  next_allowed_action?: string;
  prediction_generation_allowed?: boolean;
  feature_store_v12_allowed?: boolean;
  setup_action_telemetry?: SetupActionTelemetryPayload;
  setup_action_history?: SetupActionRunPayload[];
  setup_action_history_count?: number;
  training_invoked?: boolean;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
}

export interface SetupChecklistSafeActionPayload {
  status?: string;
  action_id?: string;
  action_result?: Record<string, unknown>;
  checklist_status?: SetupChecklistStatusPayload;
  setup_action_run?: SetupActionRunPayload;
  blocking_reasons?: string[];
  training_invoked?: boolean;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
}

export interface ManagedProxySchemaMappingPayload {
  status?: string;
  mapping_version?: string;
  generated_at?: string;
  canonical_fields?: string[];
  provider_fields_seen?: string[];
  mapped_fields?: string[];
  unmapped_required_fields?: string[];
  ambiguous_mappings?: Array<Record<string, unknown>>;
  duplicate_targets?: Array<Record<string, unknown>>;
  timestamp_mapping_status?: string;
  schema_mapping_ready?: boolean;
  mapping_applied?: boolean;
  blocking_reasons?: string[];
  warning_reasons?: string[];
  fake_data_used?: boolean;
  training_invoked?: boolean;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
  report_path?: string;
}

export interface ManagedProxySampleFixturePayload {
  status?: string;
  generated_at?: string;
  fixture_version?: string;
  fixture_path?: string;
  row_count?: number;
  schema_contract_status?: string;
  pit_replay_status?: string;
  data_quality_status?: string;
  sample_data_used?: boolean;
  managed_data_used?: boolean;
  fake_data_used?: boolean;
  mock_data_used?: boolean;
  production_eligible?: boolean;
  feature_store_v12_allowed?: boolean;
  blocking_reasons?: string[];
  warning_reasons?: string[];
  training_invoked?: boolean;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
  report_path?: string;
}

export interface ManagedProxyEndpointSmokePayload {
  status?: string;
  generated_at?: string;
  smoke_version?: string;
  auth_status?: string;
  endpoint_reachable?: boolean;
  response_format_status?: string;
  token_echo_status?: string;
  schema_field_names_seen?: string[];
  required_fields_present?: string[];
  timestamp_fields_present?: string[];
  sample_row_count?: number;
  raw_rows_persisted?: boolean;
  managed_data_cache_updated?: boolean;
  feature_store_v12_allowed?: boolean;
  training_invoked?: boolean;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
  blocking_reasons?: string[];
  warning_reasons?: string[];
  next_allowed_action?: string;
  latency_ms?: number | null;
  report_path?: string;
}

export interface ManagedProxyQuarantineSnapshotPayload {
  status?: string;
  generated_at?: string;
  snapshot_version?: string;
  snapshot_pulled?: boolean;
  snapshot_row_count?: number;
  row_budget?: number;
  quarantine_path?: string;
  preview_path?: string;
  redacted_preview?: Record<string, unknown>;
  schema_field_names_seen?: string[];
  timestamp_fields_seen?: string[];
  required_fields_seen?: string[];
  missing_required_fields?: string[];
  missing_timestamp_fields?: string[];
  secret_safety_status?: string;
  raw_rows_persisted?: boolean;
  managed_cache_updated?: boolean;
  production_eligible?: boolean;
  feature_store_v12_allowed?: boolean;
  blocking_reasons?: string[];
  warning_reasons?: string[];
  training_invoked?: boolean;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
  report_path?: string;
}

export interface ManagedProxyQuarantineContractPayload {
  status?: string;
  generated_at?: string;
  contract_version?: string;
  source_quarantine_path?: string;
  row_count?: number;
  schema_contract_status?: string;
  pit_replay_status?: string;
  pit_audit_status?: string;
  data_quality_status?: string;
  research_cache_promotion_allowed?: boolean;
  research_cache_path?: string;
  research_cache_written?: boolean;
  production_eligible?: boolean;
  feature_store_v12_allowed?: boolean;
  blocking_reasons?: string[];
  warning_reasons?: string[];
  training_invoked?: boolean;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
  report_path?: string;
}

export interface ManagedDataBackfillPlannerPayload {
  status?: string;
  generated_at?: string;
  planner_version?: string;
  required_date_range?: Record<string, unknown>;
  target_horizons?: string[];
  required_managed_fields?: string[];
  required_timestamp_fields?: string[];
  coverage_budget?: Record<string, unknown>;
  batch_plan?: Record<string, unknown>;
  retry_policy?: Record<string, unknown>;
  abort_conditions?: string[];
  human_approval_checklist?: string[];
  production_cache_write_allowed?: boolean;
  feature_store_v12_allowed?: boolean;
  rows_fetched?: boolean;
  historical_backfill_executed?: boolean;
  production_cache_written?: boolean;
  training_invoked?: boolean;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
  blocking_reasons?: string[];
  warning_reasons?: string[];
  report_path?: string;
}

export interface ManagedDataProductionCacheGatePayload {
  status?: string;
  generated_at?: string;
  gate_version?: string;
  production_cache_write_allowed?: boolean;
  production_cache_written?: boolean;
  production_cache_path_candidate?: string;
  production_cache_path_safety?: Record<string, unknown>;
  precondition_checks?: Array<{
    name?: string;
    status?: string;
    passed?: boolean;
    path?: string;
    blocking_reasons?: string[];
  }>;
  linked_research_cache_path?: string;
  linked_backfill_plan_path?: string;
  linked_pit_replay_path?: string;
  linked_audit_path?: string;
  linked_quality_path?: string;
  linked_manual_approval_path?: string;
  dry_run_plan?: Record<string, unknown>;
  human_approval_checklist?: string[];
  rollback_plan?: string[];
  feature_store_v12_allowed?: boolean;
  blocking_reasons?: string[];
  warning_reasons?: string[];
  training_invoked?: boolean;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
  report_path?: string;
}

export interface FeatureStoreV12InputContractPayload {
  status?: string;
  generated_at?: string;
  contract_version?: string;
  production_cache_path?: string;
  required_fields?: string[];
  missing_required_fields?: string[];
  required_timestamp_fields?: string[];
  missing_timestamp_fields?: string[];
  date_range_required?: Record<string, unknown>;
  date_range_available?: Record<string, unknown>;
  coverage_diff?: Record<string, unknown>;
  pit_readiness?: Record<string, unknown>;
  quality_readiness?: Record<string, unknown>;
  no_lookahead_readiness?: Record<string, unknown>;
  input_contract_ready?: boolean;
  feature_store_v12_build_allowed?: boolean;
  blocking_reasons?: string[];
  warning_reasons?: string[];
  training_invoked?: boolean;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
  report_path?: string;
}

export interface FeatureStoreV12BuildPlanPayload {
  status?: string;
  generated_at?: string;
  plan_version?: string;
  input_contract_status?: string;
  expected_feature_store_path?: string;
  expected_manifest_path?: string;
  expected_fields?: string[];
  expected_row_count?: number;
  precondition_checks?: Array<Record<string, unknown>>;
  rollback_plan?: string[];
  resource_budget?: Record<string, unknown>;
  forbidden_side_effects?: string[];
  feature_store_v12_build_executed?: boolean;
  training_invoked?: boolean;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
  blocking_reasons?: string[];
  warning_reasons?: string[];
  report_path?: string;
}

export interface FeatureStoreV12ControlledBuildPayload {
  status?: string;
  generated_at?: string;
  executor_version?: string;
  build_executed?: boolean;
  feature_store_v12_path?: string;
  feature_store_v12_manifest_path?: string;
  precondition_checks?: Array<Record<string, unknown>>;
  input_contract_summary?: Record<string, unknown>;
  production_cache_gate_summary?: Record<string, unknown>;
  build_plan_summary?: Record<string, unknown>;
  row_count?: number;
  date_range?: Record<string, unknown>;
  field_coverage?: Record<string, unknown>;
  timestamp_coverage?: Record<string, unknown>;
  artifact_boundary_checks?: { status?: string; [key: string]: unknown };
  forbidden_side_effect_checks?: { status?: string; [key: string]: unknown };
  blocking_reasons?: string[];
  warning_reasons?: string[];
  training_dataset_v12_triggered?: boolean;
  candidate_triggered?: boolean;
  training_invoked?: boolean;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
  report_path?: string;
}

export interface ManagedProxyConfigWizardPayload {
  status?: string;
  wizard_version?: string;
  generated_at?: string;
  setup_status?: string;
  endpoint_configured?: boolean;
  token_configured?: boolean;
  safe_config_methods?: string[];
  env_var_template_status?: string;
  local_config_template_status?: string;
  gitignore_secret_coverage?: {
    status?: string;
    missing_patterns?: string[];
    required_patterns?: string[];
    path?: string;
  };
  setup_steps?: string[];
  dry_run_checklist?: string[];
  next_allowed_action?: string;
  blocking_reasons?: string[];
  warning_reasons?: string[];
  training_invoked?: boolean;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
  report_path?: string;
}

export interface ProviderDetailsPayload {
  provider_id?: string;
  display_name?: string;
  key_configured?: boolean;
  key_masked?: string;
  key_source?: string;
  research_only?: boolean;
  production_eligible?: boolean;
  realtime_guarantee?: boolean;
  can_unlock_v12?: boolean;
  credential_handoff_required?: boolean;
}

export interface ProviderCredentialsPayload {
  status?: string;
  generated_at?: string;
  credentials_version?: string;
  provider_mode?: string;
  current_step?: string;
  provider_credentials_status?: string;
  configured_providers?: string[];
  missing_provider_credentials?: string[];
  providers?: Record<string, ProviderDetailsPayload>;
  safe_config_methods?: string[];
  copy_safe_setup_commands?: string[];
  local_cache_policy?: Record<string, unknown>;
  legacy_managed_proxy_status?: Record<string, unknown>;
  blocking_reasons?: string[];
  warning_reasons?: string[];
  feature_store_v12_allowed?: boolean;
  training_invoked?: boolean;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
  report_path?: string;
}

export interface ProviderSmokePayload {
  status?: string;
  generated_at?: string;
  smoke_version?: string;
  provider?: string;
  provider_mode?: string;
  auth_status?: string;
  endpoint_reachable?: boolean;
  field_coverage?: {
    fields_seen?: string[];
    canonical_fields_seen?: string[];
    missing_canonical_fields?: string[];
    row_count?: number;
    freshness_status?: string;
    field_coverage_ratio?: number;
  };
  rate_limit_warning?: string;
  freshness_status?: string;
  research_only?: boolean;
  production_eligible?: boolean;
  realtime_guarantee?: boolean;
  feature_store_v12_allowed?: boolean;
  feature_store_written?: boolean;
  production_cache_written?: boolean;
  training_invoked?: boolean;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
  blocking_reasons?: string[];
  report_path?: string;
}

export interface LocalApiProviderHubPayload {
  status?: string;
  generated_at?: string;
  hub_version?: string;
  provider_mode?: string;
  current_step?: string;
  provider_credentials_status?: string;
  configured_providers?: string[];
  missing_provider_credentials?: string[];
  managed_proxy_required?: boolean;
  legacy_managed_proxy_status?: Record<string, unknown>;
  yfinance_research_only?: Record<string, unknown>;
  provider_smoke_status?: string;
  provider_smoke?: ProviderSmokePayload;
  provider_credentials?: ProviderCredentialsPayload;
  local_cache_policy?: Record<string, unknown>;
  blocking_reasons?: string[];
  warning_reasons?: string[];
  next_allowed_action?: string;
  feature_store_v12_allowed?: boolean;
  training_invoked?: boolean;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
  report_path?: string;
}

export interface ManagedProxyConfigHandoffPayload {
  status?: string;
  generated_at?: string;
  handoff_version?: string;
  current_step?: string;
  endpoint_configured?: boolean;
  token_configured?: boolean;
  token_masked?: string;
  enabled_configured?: boolean;
  config_sources_detected?: string[];
  env_alias_consistency?: {
    status?: string;
    configured_aliases?: string[];
    conflicts?: string[];
  };
  gitignore_secret_coverage?: {
    status?: string;
    missing_patterns?: string[];
    required_patterns?: string[];
  };
  local_config_safety?: {
    status?: string;
    env_example_exists?: boolean;
    local_config_template_exists?: boolean;
    mapping_config_template_exists?: boolean;
    local_config_exists?: boolean;
    env_local_exists?: boolean;
    missing_gitignore_patterns?: string[];
  };
  copy_safe_setup_commands?: string[];
  user_action_checklist?: string[];
  next_safe_actions_after_config?: string[];
  blocking_reasons?: string[];
  warning_reasons?: string[];
  feature_store_v12_allowed?: boolean;
  training_invoked?: boolean;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
  report_path?: string;
}

export interface ManagedProxyOperatorRunbookPayload {
  status?: string;
  runbook_version?: string;
  generated_at?: string;
  config_methods?: string[];
  env_template_status?: {
    status?: string;
    missing_keys?: string[];
    required_keys?: string[];
    path?: string;
  };
  local_config_template_status?: {
    status?: string;
    missing_keys?: string[];
    required_keys?: string[];
    path?: string;
  };
  mapping_template_status?: {
    status?: string;
    missing_canonical_fields?: string[];
    required_canonical_fields?: string[];
    path?: string;
  };
  gitignore_secret_coverage?: {
    status?: string;
    missing_patterns?: string[];
    required_patterns?: string[];
    path?: string;
  };
  current_config_state?: Record<string, unknown>;
  endpoint_configured?: boolean;
  token_configured?: boolean;
  token_masked?: string;
  env_alias_consistency?: {
    status?: string;
    aliases_checked?: string[];
    configured_aliases?: string[];
    conflicts?: string[];
  };
  safe_setup_steps?: string[];
  verification_commands?: string[];
  next_allowed_action?: string;
  blocking_reasons?: string[];
  warning_reasons?: string[];
  training_invoked?: boolean;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
  report_path?: string;
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

export interface DataConsistencyReport {
  status?: string;
  generated_at?: string;
  message_zh?: string;
  latest_dates?: {
    market_history?: string;
    price_history?: string;
    price_chart?: string;
    market_analysis?: string;
    watermark_market_updated_at?: string;
  };
  market_history?: {
    row_count?: number;
    latest_date?: string;
    path?: string;
  };
  checks?: Record<string, boolean>;
  blocking_reasons?: string[];
  sample_mode_active?: boolean;
  current_data_mode?: string;
  next_actions_zh?: string[];
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

export interface TerminalTaskStatus {
  task_id?: string;
  kind?: string;
  status?: "queued" | "running" | "success" | "failed" | "cancel_requested" | "not_found" | "missing" | string;
  created_at?: string;
  started_at?: string;
  finished_at?: string;
  progress?: number;
  message_zh?: string;
  error_message_zh?: string;
  log_summary?: string[];
  payload?: Record<string, unknown>;
  result?: Record<string, unknown>;
  deduped?: boolean;
  experiment_id?: string;
  artifact_run_id?: string;
  reason_zh?: string;
}

export interface TerminalTaskList {
  generated_at?: string;
  tasks?: TerminalTaskStatus[];
  count?: number;
}

export interface TaskNotificationsPayload {
  status?: string;
  generated_at?: string;
  notification_version?: string;
  toast_task?: TerminalTaskStatus | null;
  latest_failed_task?: TerminalTaskStatus | null;
  stale_failure_suppressed?: boolean;
  notification_center?: {
    title?: string;
    tasks?: TerminalTaskStatus[];
    failed_tasks?: TerminalTaskStatus[];
    active_tasks?: TerminalTaskStatus[];
    setup_action_history?: SetupActionTelemetryPayload;
  };
  setup_action_history?: SetupActionTelemetryPayload;
  training_invoked?: boolean;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
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

export interface FullSystemReportPayload {
  status?: string;
  txt_path?: string;
  latest_txt_path?: string;
  json_path?: string;
  diagnostics_bundle_path?: string;
  text_preview?: string;
  summary?: {
    active_status?: string;
    api_failed_count?: number;
    current_data_mode?: string;
    diagnostics_bundle_path?: string;
    [key: string]: unknown;
  };
  message_zh?: string;
}

export interface SystemRepairPlanIssue {
  id?: string;
  priority?: "P0" | "P1" | "P2" | string;
  category?: "data" | "model" | "frontend" | "performance" | "security" | "release" | string;
  title?: string;
  evidence?: string;
  impact?: string;
  fix_plan?: string;
  owner?: string;
  expected_gain?: string;
}

export interface SystemRepairPlanPayload {
  status?: string;
  generated_at?: string;
  overall_status?: "research_ready" | "blocked_for_prediction" | "degraded" | string;
  issues?: SystemRepairPlanIssue[];
  summary?: Record<string, unknown>;
  source_files?: Record<string, unknown>;
  next_prompts?: string[];
  json_path?: string;
  markdown_path?: string;
  markdown?: string;
  message_zh?: string;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
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
  schema_version?: number;
  chart_type?: string;
  x_field?: string;
  y_fields?: string[];
  units?: Record<string, string>;
  source_files?: string[];
  research_only?: boolean;
  downsampled?: boolean;
  downsample_method?: string;
  missing_reason?: string;
  status?: string;
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

export interface MarketAnalysisPayload {
  status?: string;
  analysis_mode?: string;
  not_prediction?: boolean;
  sample_data_used?: boolean;
  baseline_used?: boolean;
  generated_at?: string;
  message_zh?: string;
  data_sources?: Record<string, unknown>;
  trend?: {
    short_term?: string;
    medium_term?: string;
    ma_structure?: string;
    ma_5?: NullableNumber;
    ma_20?: NullableNumber;
    ma_60?: NullableNumber;
    return_5?: NullableNumber;
    return_20?: NullableNumber;
    return_60?: NullableNumber;
    momentum_score?: NullableNumber;
  };
  volatility?: {
    atr_14?: NullableNumber;
    atr_pct_14?: NullableNumber;
    realized_vol_20?: NullableNumber;
    bollinger_width_20?: NullableNumber;
    volatility_regime?: string;
  };
  key_levels?: {
    recent_high_20?: NullableNumber;
    recent_low_20?: NullableNumber;
    recent_high_60?: NullableNumber;
    recent_low_60?: NullableNumber;
    support_levels?: NullableNumber[];
    resistance_levels?: NullableNumber[];
  };
  volume_liquidity?: {
    volume_trend?: string;
    volume_zscore?: NullableNumber;
    volume_momentum_5?: NullableNumber;
    latest_volume?: NullableNumber;
    open_interest_available?: boolean;
  };
  regime?: {
    label?: string;
    trend_score?: NullableNumber;
    volatility_score?: NullableNumber;
  };
  risk_flags?: string[];
  missing_fundamentals?: string[];
  next_actions_zh?: string[];
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
  source_quality?: Record<string, Record<string, unknown>>;
  group_coverage?: Record<string, Record<string, unknown>>;
  selected_params?: Record<string, Record<string, unknown>>;
  failed_subinterfaces?: Array<Record<string, unknown>>;
  tushare_wsr_used?: boolean;
  tushare_daily_used?: boolean;
  tushare_settle_used?: boolean;
  tushare_holding_used?: boolean;
  tushare_diagnostics?: Record<string, unknown>;
  warehouse_missing_policy?: {
    warehouse_receipt_available?: boolean;
    source?: string;
    reason?: string;
    no_fake_data?: boolean;
    inventory_missing_flag?: number;
    warehouse_data_quality_score?: number;
    message_zh?: string;
    [key: string]: unknown;
  };
  warehouse_policy_features?: string[];
  managed_schema?: Record<string, unknown>;
  managed_proxy_status?: Record<string, unknown>;
  managed_fundamentals_used?: boolean;
  managed_fundamental_fields?: string[];
  missing_managed_fields?: string[];
  feature_store_v10_readiness?: {
    status?: string;
    ready?: boolean;
    available_fields?: string[];
    missing_fields?: string[];
    group_ready?: Record<string, boolean>;
    blocking_reasons?: string[];
    next_actions_zh?: string[];
  };
  feature_store_v11_readiness?: {
    status?: string;
    ready?: boolean;
    provider_status?: string;
    available_fields?: string[];
    missing_fields?: string[];
    group_ready?: Record<string, boolean>;
    blocking_reasons?: string[];
    next_actions_zh?: string[];
  };
  feature_store_version?: string;
  health_status?: string;
  audit_status?: string;
  required_timestamp_fields?: string[];
  missing_timestamp_fields?: string[];
  timestamp_field_coverage?: {
    total?: number;
    available?: number;
    missing?: number;
    ratio?: number;
    label?: string;
    row_count?: number;
    complete_rows?: number;
    complete_ratio?: number;
    by_field?: Record<string, { present?: number; missing?: number; coverage?: number }>;
  };
  required_fundamental_fields?: string[];
  missing_fundamental_fields?: string[];
  managed_field_coverage?: {
    total?: number;
    available?: number;
    missing?: number;
    ratio?: number;
    label?: string;
    row_count?: number;
    complete_rows?: number;
    complete_ratio?: number;
    by_field?: Record<string, { present?: number; missing?: number; coverage?: number }>;
  };
  technical_feature_coverage?: {
    total?: number;
    available?: number;
    missing?: number;
    ratio?: number;
    label?: string;
    row_count?: number;
    complete_rows?: number;
    complete_ratio?: number;
    by_field?: Record<string, { present?: number; missing?: number; coverage?: number }>;
  };
  point_in_time_join_ready?: boolean;
  training_dataset_v12_allowed?: boolean;
  training_invoked?: boolean;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
  blocking_reasons?: string[];
  v12_input_contract?: FeatureStoreV12InputContractPayload;
  v12_input_contract_status?: string;
  v12_input_contract_ready?: boolean;
  managed_proxy_minimal_loop?: {
    status?: string;
    required_fields?: string[];
    available_fields?: string[];
    missing_fields?: string[];
    group_ready?: Record<string, boolean>;
    no_fake_data?: boolean;
  };
  fut_wsr_status?: string;
  no_fake_data?: boolean;
  cost_features?: string[];
  positioning_features?: string[];
  sparse_features?: string[];
  sparse_policy?: Record<string, unknown>;
  sparse_feature_policy?: Record<string, unknown>;
  alignment_rules?: Record<string, unknown>;
  forward_fill_rules?: Record<string, unknown>;
  stale_rules?: Record<string, unknown>;
  usable_fields?: string[];
  excluded_fields?: string[];
  exclusion_reasons?: Record<string, string>;
  leakage_check_pass?: boolean;
  no_lookahead_pass?: boolean;
  mock_data_used?: boolean;
  sample_data_used?: boolean;
  baseline_used?: boolean;
  message_zh?: string;
}

export interface CandidateV6ReadinessPayload {
  status?: "ready" | "blocked" | string;
  ready?: boolean;
  candidate_version?: string;
  required_groups?: string[];
  new_factor_groups?: string[];
  new_fields?: string[];
  missing_fields?: string[];
  coverage_delta?: Record<string, {
    before?: NullableNumber;
    after?: NullableNumber;
    delta?: NullableNumber;
  }>;
  sample_data_used?: boolean;
  mock_data_used?: boolean;
  baseline_used?: boolean;
  no_lookahead_pass?: boolean;
  feature_store_leakage_check_pass?: boolean;
  blocked_reasons?: string[];
  next_actions_zh?: string[];
  training_invoked?: boolean;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
  generated_at?: string;
  json_path?: string;
}

export interface TrainingDatasetStatus {
  status?: string;
  exists?: boolean;
  message_zh?: string;
  manifest_path?: string;
  generated_at?: string;
  dataset_version?: string;
  feature_store_version?: string;
  feature_store_status?: string;
  feature_store_path?: string;
  feature_store_manifest_path?: string;
  feature_set?: string;
  horizons?: number[];
  feature_cols?: string[];
  cross_market_feature_cols?: string[];
  event_feature_cols?: string[];
  cost_features?: string[];
  positioning_features?: string[];
  sparse_features?: string[];
  sparse_policy?: Record<string, unknown>;
  sparse_feature_policy?: Record<string, unknown>;
  label_cols?: string[];
  removed_label_cols?: string[];
  forbidden_feature_patterns?: string[];
  leakage_check_pass?: boolean;
  leakage_check_details?: Record<string, unknown>;
  sample_data_used?: boolean;
  mock_data_used?: boolean;
  baseline_used?: boolean;
  no_lookahead_pass?: boolean;
  point_in_time_join_ready?: boolean;
  active_model_written?: boolean;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
  no_model_training?: boolean;
  sample_count_by_horizon?: Record<string, number>;
  regime_distribution?: Record<string, number>;
  regime_sample_weights?: Record<string, Record<string, number>>;
  horizon_regime_counts?: Record<string, Record<string, number>>;
  horizon_regime_train_counts?: Record<string, Record<string, number>>;
  horizon_regime_validation_counts?: Record<string, Record<string, number>>;
  regime_balance_policy?: Record<string, unknown>;
  horizon_row_counts?: Record<string, number>;
  train_validation_counts?: Record<string, Record<string, number>>;
  technical_regime_counts?: Record<string, Record<string, number>>;
  managed_regime_counts?: Record<string, Record<string, number>>;
  managed_field_coverage?: Record<string, unknown>;
  managed_interaction_feature_coverage?: Record<string, unknown>;
  sample_weight_summary?: Record<string, Record<string, unknown>>;
  blocked_reasons?: string[];
  insufficient_coverage_reasons?: string[];
  managed_data_used?: boolean;
  candidate_v12_allowed?: boolean;
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

export interface ActiveAbsenceRootCause {
  category?: string;
  severity?: "P0" | "P1" | "P2" | string;
  evidence?: string;
  fix_plan?: string;
}

export interface FeatureStabilityEvidencePayload {
  generated_at?: string;
  candidate_version?: string;
  evidence_status?: string;
  evidence_mode?: string;
  fold_count?: number;
  informative_fold_count?: number;
  stability_score?: NullableNumber;
  threshold?: NullableNumber;
  passed?: boolean;
  stable_features?: string[];
  unstable_features?: string[];
  permutation_importance_status?: string;
  recommendations?: string[];
  report_path?: string;
}

export interface ActiveAbsenceDiagnosticsPayload {
  generated_at?: string;
  active_status?: "none" | "available" | string;
  candidate_version?: string;
  root_causes?: ActiveAbsenceRootCause[];
  blocking_metrics?: Record<string, unknown>;
  feature_stability_evidence?: FeatureStabilityEvidencePayload;
  candidate_v6_plan?: {
    status?: string;
    candidate_version?: string;
    auto_publish_active?: boolean;
    customer_prediction_generated?: boolean;
    data_repair_priority?: string[];
    label_governance?: string[];
    model_family_plan?: string[];
    risk_controls?: string[];
    multi_objective_optimization?: string[];
    minimum_go_live_gates?: string[];
    needed_data_sources?: string[];
    [key: string]: unknown;
  };
  source_files?: Record<string, string | string[]>;
  report_path?: string;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
  baseline_used?: boolean;
  fake_prediction_generated?: boolean;
  message_zh?: string;
}

export interface ActiveReleaseApprovalPayload {
  status?: string;
  candidate_version?: string;
  active_updated?: boolean;
  active_model_path?: string;
  audit_path?: string;
  approver?: string;
  notes?: string;
  approval_checklist?: Array<Record<string, unknown>>;
  blocking_reasons?: string[];
  live_trading_enabled?: boolean;
  customer_order_routing_enabled?: boolean;
  message_zh?: string;
  disclaimer?: string;
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
export type CandidateV6ResearchPayload = CandidateV3ResearchPayload & {
  candidate_v6_readiness?: CandidateV6ReadinessPayload;
  v6_admission?: Record<string, unknown>;
  oof_integrity?: OOFIntegrityReport;
  gate_passed?: boolean;
  manual_approval_recommended?: boolean;
  blocking_reasons?: string[];
  new_fields?: string[];
  new_factor_groups?: string[];
};

export type CandidateV7ResearchPayload = CandidateV3ResearchPayload & {
  v7_admission?: Record<string, unknown>;
  v7_feature_evidence?: Record<string, unknown>;
  oof_integrity?: OOFIntegrityReport;
  feature_stability?: Record<string, unknown>;
  stability_objective?: Record<string, unknown>;
  v6_vs_v7?: Record<string, unknown>;
  gate_passed?: boolean;
  manual_approval_recommended?: boolean;
  blocking_reasons?: string[];
  candidate_v7_registry_path?: string;
  institutional_validation_path?: string;
  promotion_dry_run_path?: string;
};

export type CandidateV8ResearchPayload = CandidateV3ResearchPayload & {
  v8_admission?: Record<string, unknown>;
  v7_feature_evidence?: Record<string, unknown>;
  oof_integrity?: OOFIntegrityReport;
  feature_stability?: Record<string, unknown>;
  stable_strategy_policy?: Record<string, unknown>;
  v7_vs_v8?: Record<string, unknown>;
  disabled_horizons?: string[];
  no_trade_reasons?: string[];
  gate_passed?: boolean;
  manual_approval_recommended?: boolean;
  blocking_reasons?: string[];
  candidate_v8_registry_path?: string;
  institutional_validation_path?: string;
  promotion_dry_run_path?: string;
  stable_strategy_policy_path?: string;
};

export type CandidateV9ResearchPayload = CandidateV3ResearchPayload & {
  v9_admission?: Record<string, unknown>;
  v7_feature_evidence?: Record<string, unknown>;
  oof_integrity?: OOFIntegrityReport;
  feature_stability?: Record<string, unknown>;
  regime_neutral_policy?: Record<string, unknown>;
  regime_neutral_policy_application?: Record<string, unknown>;
  v8_vs_v9?: Record<string, unknown>;
  gate_passed?: boolean;
  manual_approval_recommended?: boolean;
  blocking_reasons?: string[];
  candidate_v9_registry_path?: string;
  institutional_validation_path?: string;
  promotion_dry_run_path?: string;
  regime_neutral_policy_path?: string;
};

export type CandidateV10ResearchPayload = CandidateV3ResearchPayload & {
  v10_admission?: Record<string, unknown>;
  training_dataset_v10?: Record<string, unknown>;
  cpcv_validation?: Record<string, unknown>;
  oof_integrity?: OOFIntegrityReport;
  feature_stability?: Record<string, unknown>;
  year_concentration_evidence?: YearConcentrationEvidence;
  cost_stress_attribution?: CostStressAttributionEvidence;
  v10_gate_checks?: Record<string, unknown>;
  v10_vs_v9?: Record<string, unknown>;
  gate_passed?: boolean;
  manual_approval_recommended?: boolean;
  blocking_reasons?: string[];
  candidate_v10_registry_path?: string;
  institutional_validation_path?: string;
  promotion_dry_run_path?: string;
  cpcv_validation_path?: string;
};

export type CandidateV12ResearchPayload = CandidateV3ResearchPayload & {
  training_dataset_status?: string;
  feature_store_status?: string;
  readiness_checks?: Record<string, Record<string, unknown>>;
  training_invoked?: boolean;
  oof_trace_path?: string;
  cpcv_report_path?: string;
  pbo?: NullableNumber;
  reality_check?: Record<string, unknown>;
  institutional_cost_stress?: Record<string, unknown>;
  year_concentration_evidence?: YearConcentrationEvidence;
  cost_stress_attribution?: CostStressAttributionEvidence;
  regime_concentration?: Record<string, unknown>;
  fold_concentration?: Record<string, unknown>;
  v12_vs_v10?: Record<string, unknown>;
  gate_checks?: Record<string, unknown>;
  blocking_reasons?: string[];
  manual_approval_recommended?: boolean;
  promotion_dry_run_result?: Record<string, unknown>;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
  fake_data_used?: boolean;
  mock_data_used?: boolean;
  report_path?: string;
};

export interface YearPerformanceRow {
  year?: number;
  sample_count?: number;
  sample_share?: NullableNumber;
  gross_pnl?: NullableNumber;
  net_pnl?: NullableNumber;
  pnl_share?: NullableNumber;
  hit_rate?: NullableNumber;
  avg_return?: NullableNumber;
  median_return?: NullableNumber;
  expectancy?: NullableNumber;
  max_drawdown?: NullableNumber;
  worst_period_return?: NullableNumber;
}

export interface YearConcentrationEvidence {
  status?: "pass" | "fail" | "missing" | "skipped" | string;
  passed?: boolean;
  candidate_version?: string;
  generated_at?: string;
  skipped_reason?: string;
  time_column?: string;
  year_performance_table?: YearPerformanceRow[];
  max_year_sample_share?: NullableNumber;
  max_year_pnl_share?: NullableNumber;
  positive_year_count?: number;
  negative_year_count?: number;
  total_year_count?: number;
  min_required_years?: number;
  concentration_thresholds?: Record<string, unknown>;
  blocking_reasons?: string[];
  oof_trace_paths?: string[];
  training_invoked?: boolean;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
}

export interface YearConcentrationPayload {
  status?: string;
  generated_at?: string;
  summary_path?: string;
  candidate_v10?: {
    candidate_version?: string;
    report_path?: string;
    report_rewritten?: boolean;
    year_concentration_evidence?: YearConcentrationEvidence;
    manual_approval_recommended?: boolean;
  };
  candidate_v12?: {
    candidate_version?: string;
    report_path?: string;
    report_rewritten?: boolean;
    year_concentration_evidence?: YearConcentrationEvidence;
    manual_approval_recommended?: boolean;
  };
  reports_rewritten?: boolean;
  training_invoked?: boolean;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
}

export interface CostStressAttributionRow {
  horizon?: string;
  regime_label?: string;
  year?: number;
  sample_count?: number;
  trade_count?: number;
  gross_expectancy?: NullableNumber;
  net_expectancy_1x?: NullableNumber;
  net_expectancy_2x?: NullableNumber;
  net_expectancy_3x?: NullableNumber;
  cost_drag_2x?: NullableNumber;
  cost_drag_3x?: NullableNumber;
  cost_drag?: NullableNumber;
  turnover?: NullableNumber;
  signal_flip_count?: number;
  signal_flip_rate?: NullableNumber;
  avg_holding_period?: NullableNumber;
  passed?: boolean;
  main_failure_driver?: string;
}

export interface CostStressAttributionTable {
  status?: string;
  rows?: CostStressAttributionRow[];
  blocking_reasons?: string[];
  time_column?: string;
}

export interface CostStressAttributionEvidence {
  status?: "pass" | "fail" | "missing" | "skipped" | string;
  passed?: boolean;
  candidate_version?: string;
  generated_at?: string;
  report_path?: string;
  source_candidate_report_path?: string;
  source_oof_trace_path?: string;
  source_oof_trace_paths?: string[];
  institutional_cost_stress_source?: Record<string, unknown>;
  by_horizon?: CostStressAttributionTable;
  by_regime?: CostStressAttributionTable;
  by_year?: CostStressAttributionTable;
  turnover_diagnostics?: Record<string, unknown>;
  signal_flip_diagnostics?: Record<string, unknown>;
  holding_period_diagnostics?: Record<string, unknown>;
  cost_drag_summary?: Record<string, unknown>;
  failure_drivers?: string[];
  skipped_reason?: string;
  blocking_reasons?: string[];
  training_invoked?: boolean;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
}

export interface CostStressAttributionPayload {
  status?: string;
  generated_at?: string;
  summary_path?: string;
  candidate_v10?: {
    candidate_version?: string;
    report_path?: string;
    report_rewritten?: boolean;
    cost_stress_attribution?: CostStressAttributionEvidence;
    manual_approval_recommended?: boolean;
  };
  candidate_v12?: {
    candidate_version?: string;
    report_path?: string;
    report_rewritten?: boolean;
    cost_stress_attribution?: CostStressAttributionEvidence;
    manual_approval_recommended?: boolean;
  };
  reports_rewritten?: boolean;
  training_invoked?: boolean;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
}

export interface V10CostRemediationPayload {
  status?: string;
  candidate_version?: string;
  generated_at?: string;
  report_path?: string;
  source_candidate_report_path?: string;
  source_oof_trace_paths?: string[];
  source_cost_attribution_path?: string;
  source_cpcv_path?: string;
  failure_context?: Record<string, unknown>;
  hypotheses?: Array<Record<string, unknown>>;
  candidate_filters?: Array<Record<string, unknown>>;
  no_train_counterfactuals?: Array<Record<string, unknown>>;
  best_no_train_counterfactual?: Record<string, unknown>;
  ranked_hypotheses?: Array<Record<string, unknown>>;
  expected_tradeoff?: string;
  affected_horizon?: string | number;
  affected_regime?: string;
  affected_year?: string | number;
  risk_of_overfitting?: string;
  recommended_next_experiment?: string;
  manual_approval_recommended?: boolean;
  research_only?: boolean;
  blocking_reasons?: string[];
  training_invoked?: boolean;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
}

export interface CandidateV10RemediationPreflightPayload {
  status?: string;
  candidate_version?: string;
  generated_at?: string;
  preflight_version?: string;
  report_path?: string;
  linked_hypotheses?: Array<Record<string, unknown>>;
  evidence_dependencies?: Array<Record<string, unknown>>;
  overfitting_risk?: Record<string, unknown>;
  metric_budget_status?: Record<string, unknown>;
  recommended_experiment_order?: Array<Record<string, unknown>>;
  blocked_experiments?: Array<Record<string, unknown>>;
  warnings?: string[];
  blocking_reasons?: string[];
  training_invoked?: boolean;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
}

export interface ShadowModeReadinessPayload {
  status?: string;
  generated_at?: string;
  shadow_mode_version?: string;
  report_path?: string;
  shadow_mode_allowed?: boolean;
  entry_gates?: Array<Record<string, unknown>>;
  blocked_gates?: string[];
  output_isolation_contract?: Record<string, unknown>;
  prediction_isolation?: Record<string, unknown>;
  forbidden_outputs?: string[];
  approval_required?: boolean;
  active_publish_allowed?: boolean;
  evidence_paths?: Record<string, Record<string, unknown>>;
  run_ledger_status?: string;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
}

export interface ShadowOutputContractPayload {
  status?: string;
  generated_at?: string;
  contract_version?: string;
  shadow_output_allowed?: boolean;
  dry_run_artifact_created?: boolean;
  synthetic_contract_only?: boolean;
  shadow_output_root?: string;
  forbidden_output_roots?: string[];
  schema_fields?: string[];
  schema_validation_status?: string;
  path_isolation_status?: string;
  customer_prediction_collision_status?: string;
  active_model_collision_status?: string;
  blocking_reasons?: string[];
  warning_reasons?: string[];
  artifact_path?: string;
  training_invoked?: boolean;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
  report_path?: string;
}

export interface ShadowReplayPayload {
  status?: string;
  generated_at?: string;
  replay_version?: string;
  source_candidate_version?: string;
  source_oof_trace_path?: string;
  source_oof_trace_paths?: string[];
  replay_artifact_path?: string;
  replay_row_count?: number;
  schema_validation_status?: string;
  output_isolation_status?: string;
  stability_metrics?: Record<string, unknown>;
  risk_tags?: string[];
  top_risk_tags?: string[];
  skipped_reasons?: string[];
  blocking_reasons?: string[];
  warning_reasons?: string[];
  training_invoked?: boolean;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
  report_path?: string;
}

export interface PostReleaseMonitoringSpecPayload {
  status?: string;
  generated_at?: string;
  monitoring_spec_version?: string;
  monitoring_mode?: string;
  live_monitoring_enabled?: boolean;
  active_model_present?: boolean;
  shadow_replay_status?: string;
  shadow_replay_source_candidate?: string;
  data_drift_sentinels?: Array<Record<string, unknown>>;
  prediction_drift_sentinels?: Array<Record<string, unknown>>;
  cost_drift_sentinels?: Array<Record<string, unknown>>;
  pit_regression_sentinels?: Array<Record<string, unknown>>;
  shadow_vs_live_comparison_metrics?: Record<string, unknown>;
  alert_thresholds?: Record<string, Record<string, unknown>>;
  sentinel_count?: number;
  active_customer_prediction_sentinel_status?: string;
  escalation_policy?: string[];
  readiness_gaps?: string[];
  blocking_reasons?: string[];
  warning_reasons?: string[];
  decision_board_active_publish_allowed?: boolean;
  training_invoked?: boolean;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
  report_path?: string;
}

export interface RollbackRehearsalPayload {
  status?: string;
  generated_at?: string;
  rollback_rehearsal_version?: string;
  quarantine_needed?: boolean;
  artifacts_detected?: Array<Record<string, unknown>>;
  simulated_quarantine_actions?: Array<Record<string, unknown>>;
  quarantine_manifest?: Record<string, unknown>;
  rollback_plan?: string[];
  manual_actions_required?: string[];
  safety_checks?: Record<string, unknown>;
  linked_incident_drill_path?: string;
  linked_registry_safety_path?: string;
  linked_monitoring_spec_path?: string;
  linked_decision_board_path?: string;
  blocking_reasons?: string[];
  warning_reasons?: string[];
  training_invoked?: boolean;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
  report_path?: string;
}

export interface ModelRegistrySafetyPayload {
  status?: string;
  generated_at?: string;
  safety_version?: string;
  candidate_version?: string;
  report_path?: string;
  active_write_allowed?: boolean;
  approval_required?: boolean;
  rollback_target_available?: boolean;
  current_active_model_exists?: boolean;
  unapproved_active_detected?: boolean;
  promotion_dry_run_status?: string;
  rollback_plan?: Record<string, unknown>;
  active_model_path?: string;
  active_release_audit_path?: string;
  promotion_report_path?: string;
  candidate_report_path?: string;
  decision_board_path?: string;
  run_ledger_status?: string;
  contract?: Record<string, unknown>;
  preconditions?: Record<string, unknown>;
  blocking_reasons?: string[];
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
}

export interface GovernanceAccessControlPayload {
  status?: string;
  generated_at?: string;
  access_control_version?: string;
  permission_matrix?: Record<string, Record<string, unknown>>;
  api_action_inventory?: Array<Record<string, unknown>>;
  ui_action_inventory?: Array<Record<string, unknown>>;
  forbidden_actions?: string[];
  allowed_safe_actions?: string[];
  blocked_heavy_actions?: string[];
  blocked_secret_actions?: string[];
  ui_api_violations?: string[];
  ui_api_violations_count?: number;
  decision_board_state?: Record<string, unknown>;
  active_write_allowed?: boolean;
  customer_prediction_write_allowed?: boolean;
  training_invoked?: boolean;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
  report_path?: string;
}

export interface GovernanceObservabilityPayload {
  status?: string;
  generated_at?: string;
  observability_version?: string;
  telemetry_summary?: Record<string, unknown>;
  slo_definitions?: Record<string, unknown>;
  slo_results?: Record<string, Record<string, unknown> | string>;
  error_budget?: Record<string, unknown>;
  run_ledger_source?: string;
  freshness_source?: string;
  access_control_source?: string;
  secret_scan_source?: string;
  blocking_reasons?: string[];
  warning_reasons?: string[];
  training_invoked?: boolean;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
  report_path?: string;
}

export interface IncidentDrillPayload {
  status?: string;
  generated_at?: string;
  drill_version?: string;
  scenario_results?: Array<Record<string, unknown>>;
  scenarios_run?: number;
  scenarios_passed?: number;
  scenarios_failed?: number;
  lockdown_triggered?: boolean;
  lockdown_reasons?: string[];
  real_lockdown_state?: Record<string, unknown>;
  simulated_lockdown_state?: Record<string, unknown>;
  simulated_artifacts_only?: boolean;
  remediation_playbook?: string[];
  required_human_actions?: string[];
  decision_board_override?: Record<string, unknown>;
  active_publish_allowed?: boolean;
  customer_prediction_write_allowed?: boolean;
  training_invoked?: boolean;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
  report_path?: string;
}

export interface ManualApprovalPayload {
  status?: string;
  generated_at?: string;
  approval_version?: string;
  candidate_version?: string;
  requested_action?: string;
  approval_request_allowed?: boolean;
  approval_decision?: string;
  reviewers?: Array<Record<string, unknown>>;
  reviewer_count?: number;
  two_person_review_pass?: boolean;
  expires_at?: string;
  linked_decision_board_path?: string;
  linked_evidence_bundle_path?: string;
  linked_registry_safety_path?: string;
  linked_shadow_readiness_path?: string;
  precondition_checks?: Array<Record<string, unknown>>;
  blocking_reasons?: string[];
  warning_reasons?: string[];
  active_write_allowed?: boolean;
  customer_prediction_write_allowed?: boolean;
  training_invoked?: boolean;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
  report_path?: string;
}

export interface EvidenceBundlePayload {
  status?: string;
  generated_at?: string;
  bundle_version?: string;
  bundle_path?: string;
  current_research_state?: string;
  next_allowed_action?: string;
  evidence_files?: Record<string, Record<string, unknown>>;
  evidence_file_count?: number;
  file_hashes?: Record<string, Record<string, unknown>>;
  missing_reports?: string[];
  incomplete_reports?: string[];
  skipped_or_blocked_reports?: string[];
  reproducibility_checklist?: Record<string, unknown>;
  safety_flags?: string[];
  no_active_confirmation?: Record<string, unknown>;
  no_prediction_confirmation?: Record<string, unknown>;
  training_invoked?: boolean;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
}

export interface ExternalAuditExportPayload {
  status?: string;
  generated_at?: string;
  audit_export_version?: string;
  current_research_state?: string;
  next_allowed_action?: string;
  evidence_files?: Record<string, Record<string, unknown>>;
  evidence_file_count?: number;
  file_hashes?: Record<string, Record<string, unknown>>;
  redacted_fields?: string[];
  redacted_fields_count?: number;
  omitted_sensitive_files?: string[];
  missing_reports?: string[];
  incomplete_reports?: string[];
  blocking_reasons?: string[];
  active_model_confirmation?: Record<string, unknown>;
  customer_prediction_confirmation?: Record<string, unknown>;
  redaction_status?: string;
  training_invoked?: boolean;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
  export_root?: string;
  audit_index_path?: string;
  review_summary_path?: string;
  evidence_file_manifest_path?: string;
  hash_manifest_path?: string;
  redaction_report_path?: string;
}

export interface ProductionCutoverChecklistPayload {
  status?: string;
  generated_at?: string;
  cutover_version?: string;
  cutover_allowed?: boolean;
  noop_release_plan_ready?: boolean;
  precondition_checks?: Array<Record<string, unknown>>;
  required_manual_steps?: string[];
  rollback_plan_summary?: Record<string, unknown>;
  observability_requirements?: Record<string, unknown>;
  incident_response_requirements?: string[];
  forbidden_actions?: string[];
  blocking_reasons?: string[];
  active_publish_allowed?: boolean;
  customer_prediction_write_allowed?: boolean;
  training_invoked?: boolean;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
  report_path?: string;
  noop_plan_path?: string;
  release_plan_id?: string;
  release_type?: string;
  intended_candidate_version?: string;
  steps?: string[];
  expected_no_side_effects?: string[];
  forbidden_outputs?: string[];
  rollback_drill_required?: boolean;
  signoff_required?: boolean;
  plan_path?: string;
}

export interface PromotionDryRunEvidencePayload {
  status?: string;
  generated_at?: string;
  dry_run_version?: string;
  candidate_version?: string;
  requested_action?: string;
  precondition_checks?: Array<Record<string, unknown>>;
  simulated_registry_write_plan?: Record<string, unknown>;
  artifact_boundary_checks?: Record<string, unknown>;
  active_write_attempted?: boolean;
  active_write_allowed?: boolean;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
  customer_prediction_write_allowed?: boolean;
  training_invoked?: boolean;
  blocking_reasons?: string[];
  warning_reasons?: string[];
  report_path?: string;
}

export interface ModelCardPayload {
  status?: string;
  model_card_version?: string;
  generated_at?: string;
  system_name?: string;
  current_status?: string;
  intended_use?: string[];
  prohibited_use?: string[];
  model_or_candidate_scope?: Record<string, unknown>;
  active_model_status?: Record<string, unknown>;
  customer_prediction_status?: Record<string, unknown>;
  data_sources?: Record<string, unknown>;
  data_readiness?: Record<string, unknown>;
  managed_proxy_status?: Record<string, unknown>;
  pit_readiness?: Record<string, unknown>;
  feature_store_status?: Record<string, unknown>;
  training_dataset_status?: Record<string, unknown>;
  candidate_status?: Record<string, unknown>;
  validation_summary?: Record<string, unknown>;
  year_evidence_summary?: Record<string, unknown>;
  cost_attribution_summary?: Record<string, unknown>;
  shadow_replay_summary?: Record<string, unknown>;
  monitoring_spec_summary?: Record<string, unknown>;
  rollback_rehearsal_summary?: Record<string, unknown>;
  manual_approval_summary?: Record<string, unknown>;
  registry_safety_summary?: Record<string, unknown>;
  cutover_summary?: Record<string, unknown>;
  known_limitations?: string[];
  risk_disclosure?: Record<string, string[]>;
  gate_failures?: string[];
  next_allowed_action?: string;
  no_active_confirmation?: Record<string, unknown>;
  no_prediction_confirmation?: Record<string, unknown>;
  evidence_paths?: Record<string, string>;
  missing_reports?: string[];
  incomplete_reports?: string[];
  training_invoked?: boolean;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
  report_path?: string;
  model_card_md_path?: string;
  risk_disclosure_path?: string;
}

export interface GovernanceMaturityDomainScore {
  domain?: string;
  score?: number;
  status?: string;
  blockers?: string[];
  evidence_paths?: string[];
  next_actions?: string[];
}

export interface GovernanceMaturityPromptStep {
  priority?: number;
  action?: string;
}

export interface GovernanceMaturityMatrixPayload {
  status?: string;
  generated_at?: string;
  maturity_matrix_version?: string;
  production_readiness?: boolean;
  shadow_readiness?: Record<string, unknown>;
  current_research_state?: string;
  next_allowed_action?: string;
  domain_scores?: Record<string, GovernanceMaturityDomainScore>;
  domain_statuses?: Record<string, string>;
  completed_controls?: string[];
  missing_controls?: string[];
  critical_gaps?: string[];
  immediate_blockers?: string[];
  data_onboarding_blockers?: string[];
  research_validation_blockers?: string[];
  governance_blockers?: string[];
  shadow_readiness_blockers?: string[];
  production_cutover_blockers?: string[];
  recommended_prompt_sequence?: GovernanceMaturityPromptStep[];
  roadmap?: Record<string, string[]>;
  evidence_paths?: Record<string, string>;
  training_invoked?: boolean;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
  report_path?: string;
}

export interface EvidenceFreshnessPayload {
  status?: string;
  generated_at?: string;
  freshness_version?: string;
  report_ages?: Record<string, Record<string, unknown>>;
  stale_reports?: string[];
  missing_reports?: string[];
  missing_timestamps?: string[];
  version_mismatches?: Array<Record<string, unknown>>;
  timestamp_inversions?: Array<Record<string, unknown>>;
  max_allowed_age_hours_by_report_type?: Record<string, number>;
  blocking_reasons?: string[];
  warning_reasons?: string[];
  training_invoked?: boolean;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
  report_path?: string;
}

export interface AntiPHackingLedgerPayload {
  status?: string;
  generated_at?: string;
  ledger_version?: string;
  ledger_path?: string;
  hypothesis_count?: number;
  open_hypotheses?: Array<Record<string, unknown>>;
  closed_hypotheses?: Array<Record<string, unknown>>;
  experiment_budget_by_blocker?: Record<string, Record<string, unknown>>;
  repeated_test_count?: number;
  p_hacking_risk_level?: string;
  warning_reasons?: string[];
  blocking_reasons?: string[];
  training_invoked?: boolean;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
}

export interface HypothesisRegistryPayload {
  status?: string;
  generated_at?: string;
  registry_version?: string;
  registry_path?: string;
  hypothesis_count?: number;
  open_hypotheses?: number;
  closed_hypotheses?: number;
  hypotheses?: Array<Record<string, unknown>>;
  hypothesis_templates?: Array<Record<string, unknown>>;
  anti_p_hacking_ledger?: AntiPHackingLedgerPayload;
  p_hacking_risk_level?: string;
  experiment_budget_by_blocker?: Record<string, Record<string, unknown>>;
  training_invoked?: boolean;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
}

export interface ResearchRunLedgerPayload {
  status?: string;
  generated_at?: string;
  ledger_version?: string;
  ledger_path?: string;
  report_path?: string;
  latest_run_count?: number;
  latest_runs?: Array<Record<string, unknown>>;
  violation_count?: number;
  safe_check_count?: number;
  report_refresh_count?: number;
  heavy_task_count?: number;
  forbidden_side_effects?: string[];
  training_invoked?: boolean;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
}

export interface ReadinessDagPayload {
  status?: string;
  generated_at?: string;
  dag_version?: string;
  nodes?: Array<Record<string, unknown>>;
  edges?: Array<Record<string, unknown>>;
  node_statuses?: Record<string, Record<string, unknown>>;
  blocked_nodes?: string[];
  skipped_nodes?: string[];
  runnable_safe_checks?: string[];
  safe_checks_executed?: string[];
  safe_check_errors?: Record<string, string>;
  forbidden_actions?: string[];
  critical_path?: string[];
  next_allowed_action?: string;
  top_blockers?: string[];
  evidence_paths?: Record<string, string>;
  candidate_training_allowed?: boolean;
  manual_approval_allowed?: boolean;
  active_publish_allowed?: boolean;
  training_invoked?: boolean;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
  report_path?: string;
}

export interface ResearchDecisionBoardPayload {
  status?: string;
  generated_at?: string;
  current_research_state?: string;
  next_allowed_action?: string;
  candidate_training_allowed?: boolean;
  training_dataset_v12_allowed?: boolean;
  candidate_v12_allowed?: boolean;
  manual_approval_recommended?: boolean;
  active_publish_allowed?: boolean;
  managed_proxy_summary?: Record<string, unknown>;
  pit_audit_summary?: Record<string, unknown>;
  feature_store_v12_summary?: Record<string, unknown>;
  training_dataset_v12_summary?: Record<string, unknown>;
  candidate_v10_summary?: Record<string, unknown>;
  candidate_v12_summary?: Record<string, unknown>;
  cpcv_summary?: Record<string, unknown>;
  year_concentration_summary?: Record<string, unknown>;
  cost_stress_attribution_summary?: Record<string, unknown>;
  promotion_dry_run_summary?: Record<string, unknown>;
  manual_approval_summary?: Record<string, unknown>;
  blocking_reasons?: string[];
  warning_reasons?: string[];
  evidence_paths?: Record<string, string>;
  stale_or_missing_reports?: string[];
  training_invoked?: boolean;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
  board_path?: string;
}

export interface PredictionWorkspaceStatusPayload {
  status?: string;
  prediction_status?: string;
  generated_at?: string;
  workspace_version?: string;
  decision_board_status?: string;
  decision_board_path?: string;
  current_research_state?: string;
  next_allowed_action?: string;
  required_gates?: string[];
  active_model_available?: boolean;
  active_model_path_exists?: boolean;
  customer_predictions_path_exists?: boolean;
  manual_approval_recommended?: boolean;
  active_publish_allowed?: boolean;
  prediction_generation_allowed?: boolean;
  customer_visible_output_allowed?: boolean;
  blocking_reasons?: string[];
  warning_reasons?: string[];
  evidence_paths?: Record<string, string>;
  training_invoked?: boolean;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
}

export interface CandidateV8DiagnosticsPayload {
  status?: string;
  candidate_version?: string;
  institutional_validation_status?: string;
  validation_passed?: boolean;
  failed_checks?: Record<string, unknown>[];
  pbo_attribution?: Record<string, unknown>;
  pbo_attribution_by_fold?: Record<string, unknown>[];
  pbo_attribution_by_year?: Record<string, unknown>[];
  pbo_attribution_by_regime?: Record<string, unknown>[];
  reality_check_bootstrap_summary?: Record<string, unknown>;
  regime_concentration_table?: Record<string, unknown>[];
  regime_concentration_attribution?: Record<string, unknown>;
  disabled_horizons?: string[];
  no_trade_policy_effect?: Record<string, unknown>;
  trade_count_by_horizon?: Record<string, number>;
  turnover_by_horizon?: Record<string, number>;
  cost_stress_by_horizon?: Record<string, Record<string, unknown>>;
  recommended_v9_actions?: Record<string, unknown>[];
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
  json_path?: string;
  markdown_path?: string;
}

export interface CPCVValidationPayload {
  status?: string;
  generated_at?: string;
  candidate_version?: string;
  source?: string;
  report_path?: string;
  split_count?: number;
  cpcv_config?: Record<string, unknown>;
  pbo?: {
    method?: string;
    pbo?: NullableNumber;
    path_count?: number;
    overfit_path_count?: number;
    pbo_by_path?: Array<Record<string, unknown>>;
    [key: string]: unknown;
  };
  pbo_by_path?: Array<Record<string, unknown>>;
  reality_check?: {
    method?: string;
    aggregate_p_value?: NullableNumber;
    aggregate_observed_mean?: NullableNumber;
    aggregate_sample_count?: number;
    passed?: boolean;
    reality_check_by_path?: Array<Record<string, unknown>>;
    [key: string]: unknown;
  };
  reality_check_by_path?: Array<Record<string, unknown>>;
  research_only?: boolean;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
  message_zh?: string;
}
