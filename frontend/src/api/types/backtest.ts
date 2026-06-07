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

export interface BacktestManifest {
  schema_version?: number;
  run_id?: string;
  generated_at?: string;
  input_dir?: string;
  historical_bars_path?: string;
  signals_path?: string;
  data_manifest_hash?: string;
  signal_manifest_hash?: string;
  cost_model?: Record<string, unknown>;
  slippage_model?: Record<string, unknown>;
  margin_model?: Record<string, unknown>;
  blocked_reasons?: string[];
  sample_data_used?: boolean;
  baseline_used?: boolean;
  lookahead_check_pass?: boolean;
  chart_payload_input_used?: boolean;
  display_payload_input_used?: boolean;
  equity_curve_path?: string;
  trades_path?: string;
  metrics_path?: string;
  research_only?: boolean;
  disclaimer?: string;
  [key: string]: unknown;
}

export interface AuditableBacktestPayload {
  status?: string;
  run_id?: string;
  generated_at?: string;
  input_id?: string;
  input_dir?: string;
  read_only?: boolean;
  manifest?: BacktestManifest;
  manifest_path?: string;
  metrics?: Record<string, unknown>;
  equity?: Array<Record<string, unknown>>;
  trades?: Array<Record<string, unknown>>;
  blocking_reasons?: string[];
  chart_payload_input_used?: boolean;
  display_payload_input_used?: boolean;
  sample_data_used?: boolean;
  baseline_used?: boolean;
  feature_store_written?: boolean;
  training_invoked?: boolean;
  backtest_invoked?: boolean;
  active_updated?: boolean;
  customer_prediction_generated?: boolean;
  message_zh?: string;
  disclaimer?: string;
}

export interface ResearchEquityCurvePayload {
  status?: string;
  horizon?: string;
  path?: string;
  points?: Array<Record<string, unknown>>;
  message_zh?: string;
}
