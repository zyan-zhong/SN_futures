import { useCallback, useState } from "react";
import { buildTrainingDataset, buildTrainingDatasetV12, getTrainingDatasetStatus, getTrainingDatasetV12 } from "../api/terminal";
import type { TrainingDatasetStatus } from "../api/types";
import { DataTable } from "../components/common/DataTable";
import { ErrorState } from "../components/common/ErrorState";
import { LoadingState } from "../components/common/LoadingState";
import { StatusPill } from "../components/common/StatusPill";
import { SectionCard } from "../components/layout/SectionCard";
import { usePolling } from "../hooks/usePolling";
import { formatDateTime, formatNullable, formatNumber } from "../utils/format";

const datasetVersions = ["v1", "v2", "v3", "v4", "v5", "v7", "v10", "v12"];

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function coverageLabel(value?: Record<string, unknown>) {
  const record = asRecord(value);
  if (typeof record.label === "string") return record.label;
  const available = typeof record.available === "number" ? record.available : 0;
  const total = typeof record.total === "number" ? record.total : 0;
  return `${available}/${total}`;
}

function distributionRows(status?: TrainingDatasetStatus | null) {
  return Object.entries(status?.sample_count_by_horizon || {}).map(([horizon, count]) => ({
    horizon,
    sample_count: count,
    label_distribution: JSON.stringify(status?.label_distribution_by_horizon?.[horizon] || {}),
    return_summary: JSON.stringify(status?.return_summary_by_horizon?.[horizon] || {})
  }));
}

function datasetPathRows(status?: TrainingDatasetStatus | null) {
  return Object.entries(status?.dataset_paths || {}).map(([horizon, filePath]) => ({ horizon, file_path: filePath }));
}

function regimeRows(status?: TrainingDatasetStatus | null) {
  const counts = status?.horizon_regime_counts || {};
  const trainCounts = status?.horizon_regime_train_counts || {};
  const validationCounts = status?.horizon_regime_validation_counts || {};
  const weights = status?.regime_sample_weights || {};
  return Object.entries(counts).flatMap(([horizon, regimeCounts]) =>
    Object.entries(regimeCounts).map(([regime, sampleCount]) => ({
      horizon,
      regime,
      sample_count: sampleCount,
      train_count: trainCounts[horizon]?.[regime] ?? 0,
      validation_count: validationCounts[horizon]?.[regime] ?? 0,
      sample_weight: weights[horizon]?.[regime] ?? 1
    }))
  );
}

function flatRows(record?: Record<string, number>, valueKey = "value") {
  return Object.entries(record || {}).map(([name, value]) => ({ name, [valueKey]: value }));
}

function nestedRows(record?: Record<string, Record<string, unknown>>, valueKey = "value") {
  return Object.entries(record || {}).flatMap(([group, values]) =>
    Object.entries(values || {}).map(([name, value]) => ({ group, name, [valueKey]: value }))
  );
}

function reasonRows(reasons?: string[]) {
  return (reasons || []).map((reason) => ({ reason }));
}

function v12StatusTone(status?: string) {
  const value = String(status || "").toLowerCase();
  if (value === "success" || value === "ready") return "good";
  if (value === "blocked" || value === "failed") return "bad";
  return "info";
}

export function TrainingDataPage() {
  const [version, setVersion] = useState("v3");
  const [building, setBuilding] = useState(false);
  const [message, setMessage] = useState("");
  const loader = useCallback(() => (version === "v12" ? getTrainingDatasetV12() : getTrainingDatasetStatus(version)), [version]);
  const { data, error, loading, refresh } = usePolling<TrainingDatasetStatus>(loader, 60000);

  async function handleBuildDataset() {
    setBuilding(true);
    setMessage("");
    try {
      if (version === "v12") {
        const result = await buildTrainingDatasetV12();
        setMessage(result.message_zh || "v12 training dataset build queued.");
        await refresh();
        return;
      }
      const isV10 = version === "v10";
      const isV7 = version === "v7";
      const result = await buildTrainingDataset({
        dataset_version: version,
        feature_store_version: isV10 ? "v7" : version === "v1" || version === "v2" ? undefined : version,
        feature_set: isV10
          ? "regime_balanced_tushare_cost_positioning"
          : isV7
            ? "institutional_tushare_cost_positioning"
            : version === "v1"
              ? "usable_real_features"
              : "ohlcv_technical_regime_cross_market_event",
        horizons: [1, 3, 5, 10, 20],
        min_feature_coverage: isV7 || isV10 ? 0 : 0.7
      });
      setMessage(result.message_zh || `${version} training dataset build queued.`);
      await refresh();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Training dataset build failed.");
    } finally {
      setBuilding(false);
    }
  }

  if (loading && !data) return <LoadingState label="Loading training dataset status..." />;
  if (error && !data) return <ErrorState title="Training dataset status unavailable" message={error} actionLabel="Reload" onAction={refresh} />;

  return (
    <div className="page-stack">
      <SectionCard
        title="Training Data"
        subtitle="Build research datasets, inspect manifests, and verify leakage controls. This page does not train models or publish active."
        actions={
          <select aria-label="dataset version selector" value={version} onChange={(event) => setVersion(event.target.value)}>
            {datasetVersions.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        }
      >
        <div className="button-row">
          <button className="primary-button" type="button" onClick={() => void handleBuildDataset()} disabled={building}>
            {building ? "Building..." : `Build ${version} training dataset`}
          </button>
          <button className="secondary-button" type="button" onClick={() => void refresh()}>
            Refresh status
          </button>
          <StatusPill label="No model training / no prediction / no active publish" tone="info" />
        </div>
        {message ? <StatusPill label={message} tone={message.toLowerCase().includes("fail") ? "bad" : "info"} /> : null}
      </SectionCard>

      <SectionCard title={`${version} manifest summary`} subtitle="Manifest values are used for research reproducibility and leakage checks.">
        <div className="metric-grid compact">
          <div className="metric-card">
            <span className="metric-label">Status</span>
            <strong>{formatNullable(data?.status, "not_built")}</strong>
            <small>{formatDateTime(data?.generated_at)}</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">Sample range</span>
            <strong>{formatNullable(data?.date_start, "none")}</strong>
            <small>to {formatNullable(data?.date_end, "none")}</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">Feature count</span>
            <strong>{formatNumber(data?.feature_count, 0)}</strong>
            <small>feature_cols: {data?.feature_cols?.length || 0}</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">Leakage check</span>
            <strong>{data?.leakage_check_pass || data?.no_lookahead_pass ? "pass" : "pending"}</strong>
            <small>label columns excluded</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">Feature Store</span>
            <strong>{formatNullable(data?.feature_store_version, "none")}</strong>
            <small>{formatNullable(data?.feature_store_path || data?.feature_store_manifest_path, "not linked")}</small>
          </div>
        </div>
        <div className="notice-card">
          <strong>Manifest path</strong>
          <p>{formatNullable(data?.manifest_path, "No manifest")}</p>
        </div>
      </SectionCard>

      {version === "v7" ? (
        <SectionCard title="v7 cost and positioning dataset" subtitle="institutional_tushare_cost_positioning">
          <div className="metric-grid compact">
            <div className="metric-card">
              <span className="metric-label">cost_features</span>
              <strong>{data?.cost_features?.length || 0}</strong>
              <small>{(data?.cost_features || []).slice(0, 4).join(", ") || "not built"}</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">positioning_features</span>
              <strong>{data?.positioning_features?.length || 0}</strong>
              <small>{(data?.positioning_features || []).slice(0, 4).join(", ") || "not built"}</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">no_lookahead_pass</span>
              <strong>{data?.no_lookahead_pass ? "pass" : "pending"}</strong>
              <small>point-in-time join ready: {data?.point_in_time_join_ready ? "yes" : "no"}</small>
            </div>
          </div>
        </SectionCard>
      ) : null}

      {version === "v10" ? (
        <SectionCard title="v10 regime balance" subtitle="High-volatility samples are capped; low-volatility and range regimes receive higher training weight.">
          <div className="metric-grid compact">
            <div className="metric-card">
              <span className="metric-label">high-vol samples</span>
              <strong>{formatNumber(data?.regime_distribution?.high_volatility, 0)}</strong>
              <small>downweighted</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">low-vol samples</span>
              <strong>{formatNumber(data?.regime_distribution?.low_volatility, 0)}</strong>
              <small>boosted</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">range samples</span>
              <strong>{formatNumber(data?.regime_distribution?.range, 0)}</strong>
              <small>boosted</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">weight policy</span>
              <strong>{formatNullable(String(data?.regime_balance_policy?.weight_normalization || "pending"), "pending")}</strong>
              <small>{formatNullable(String(data?.regime_balance_policy?.validation_split || "pending"), "pending")}</small>
            </div>
          </div>
          <DataTable
            data={regimeRows(data)}
            emptyLabel="No v10 regime balance data"
            columns={[
              { key: "horizon", title: "Horizon" },
              { key: "regime", title: "Regime" },
              { key: "sample_count", title: "Samples", format: "number" },
              { key: "train_count", title: "Train", format: "number" },
              { key: "validation_count", title: "Validation", format: "number" },
              { key: "sample_weight", title: "Weight", format: "number" }
            ]}
          />
        </SectionCard>
      ) : null}

      {version === "v12" ? (
        <SectionCard title="v12 managed PIT dataset gate" subtitle="Feature Store v12 is the only allowed source; blocked state writes manifest only and never trains a candidate.">
          <div className="metric-grid compact">
            <div className="metric-card">
              <span className="metric-label">Feature Store v12 status</span>
              <strong>{formatNullable(data?.feature_store_status, "missing")}</strong>
              <small>{formatNullable(data?.feature_store_manifest_path, "no manifest")}</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">managed field coverage</span>
              <strong>{coverageLabel(data?.managed_field_coverage)}</strong>
              <small>required fundamentals</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">managed interaction feature coverage</span>
              <strong>{coverageLabel(data?.managed_interaction_feature_coverage)}</strong>
              <small>basis / inventory / carry</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">no-lookahead / PIT status</span>
              <strong>{data?.no_lookahead_pass && data?.point_in_time_join_ready ? "pass" : "blocked"}</strong>
              <small>PIT: {data?.point_in_time_join_ready ? "ready" : "blocked"}</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">candidate v12 allowed</span>
              <strong>{data?.candidate_v12_allowed ? "yes" : "no"}</strong>
              <small>no auto training</small>
            </div>
          </div>
          <StatusPill label={formatNullable(data?.status, "not_built")} tone={v12StatusTone(data?.status)} />
          <div className="two-column-grid">
            <DataTable
              data={flatRows(data?.horizon_row_counts, "rows")}
              emptyLabel="No v12 horizon rows"
              columns={[
                { key: "name", title: "Horizon" },
                { key: "rows", title: "Rows", format: "number" }
              ]}
            />
            <DataTable
              data={nestedRows(data?.train_validation_counts, "count")}
              emptyLabel="No v12 train/validation counts"
              columns={[
                { key: "group", title: "Horizon" },
                { key: "name", title: "Split" },
                { key: "count", title: "Count", format: "number" }
              ]}
            />
          </div>
          <div className="two-column-grid">
            <DataTable
              data={nestedRows(data?.managed_regime_counts, "count")}
              emptyLabel="No managed regime distribution"
              columns={[
                { key: "group", title: "Horizon" },
                { key: "name", title: "Managed regime distribution" },
                { key: "count", title: "Count", format: "number" }
              ]}
            />
            <DataTable
              data={nestedRows(data?.sample_weight_summary, "value")}
              emptyLabel="No sample weight summary"
              columns={[
                { key: "group", title: "Horizon" },
                { key: "name", title: "Sample weight summary" },
                { key: "value", title: "Value" }
              ]}
            />
          </div>
          <DataTable
            data={reasonRows(data?.blocked_reasons)}
            emptyLabel="No blocked reasons"
            columns={[{ key: "reason", title: "blocked reasons" }]}
          />
        </SectionCard>
      ) : null}

      <SectionCard title="Samples and labels" subtitle="Sample count, direction label distribution, and return summary by horizon.">
        <DataTable
          data={distributionRows(data)}
          emptyLabel="No training sample distribution"
          columns={[
            { key: "horizon", title: "Horizon" },
            { key: "sample_count", title: "Samples", format: "number" },
            { key: "label_distribution", title: "Label distribution" },
            { key: "return_summary", title: "Return summary" }
          ]}
        />
      </SectionCard>

      <SectionCard title="Dataset files" subtitle="Generated train_*.parquet or CSV artifact paths.">
        <DataTable
          data={datasetPathRows(data)}
          emptyLabel="No dataset files"
          columns={[
            { key: "horizon", title: "Horizon" },
            { key: "file_path", title: "Dataset path" }
          ]}
        />
      </SectionCard>
    </div>
  );
}
