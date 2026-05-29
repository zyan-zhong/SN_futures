import { useCallback, useState } from "react";
import { getResearchArtifacts } from "../../api/terminal";
import type { ResearchArtifactsPayload } from "../../api/types";
import { usePolling } from "../../hooks/usePolling";
import { formatDateTime, formatNullable, formatNumber } from "../../utils/format";
import { DataTable } from "../common/DataTable";
import { ErrorState } from "../common/ErrorState";
import { LoadingState } from "../common/LoadingState";
import { StatusPill } from "../common/StatusPill";
import { SectionCard } from "../layout/SectionCard";

function artifactRows(payload?: ResearchArtifactsPayload | null) {
  return (payload?.artifacts || []).map((filePath) => {
    const ext = filePath.split(".").pop()?.toLowerCase() || "";
    return {
      file_path: filePath,
      type: ext || "file",
      downloadable: ["json", "csv", "md", "parquet"].includes(ext) ? "yes" : "path_only"
    };
  });
}

function runRows(payload?: ResearchArtifactsPayload | null) {
  return (payload?.runs || []).map((row) => row as Record<string, unknown>);
}

export function ArtifactCenter() {
  const [version, setVersion] = useState("v4");
  const [copyMessage, setCopyMessage] = useState("");
  const loader = useCallback(() => getResearchArtifacts(undefined, version), [version]);
  const { data, error, loading, refresh } = usePolling<ResearchArtifactsPayload>(loader, 60000);

  async function copySummary() {
    const summary = {
      version,
      status: data?.status,
      artifact_dir: data?.artifact_dir,
      run_id: data?.run_id,
      artifact_count: data?.count ?? data?.artifacts?.length ?? 0,
      generated_at: new Date().toISOString(),
    };
    if (navigator.clipboard) {
      await navigator.clipboard.writeText(JSON.stringify(summary, null, 2));
      setCopyMessage("诊断摘要已复制。");
    } else {
      setCopyMessage(JSON.stringify(summary));
    }
  }

  return (
    <SectionCard
      title="资料归档 Artifact Center"
      subtitle="统一列出 research_runs、feature manifests、training manifests、candidate registries、OOF traces、validation reports、equity curves、trades 和 release reports。"
      actions={
        <select aria-label="artifact version selector" value={version} onChange={(event) => setVersion(event.target.value)}>
          <option value="v4">v4</option>
          <option value="v3">v3</option>
          <option value="v2">v2</option>
          <option value="v1">v1</option>
        </select>
      }
    >
      {loading && !data ? <LoadingState label="正在读取研究资料归档..." /> : null}
      {error && !data ? <ErrorState title="Artifact Center 暂时无法加载" message={error} actionLabel="重新加载" onAction={refresh} /> : null}
      <div className="button-row">
        <button className="secondary-button" type="button" onClick={() => void refresh()}>
          刷新 artifacts
        </button>
        <button className="ghost-button" type="button" onClick={() => void copySummary()}>
          复制诊断摘要
        </button>
        {copyMessage ? <StatusPill label={copyMessage} tone="info" /> : null}
      </div>
      <div className="metric-grid compact">
        <div className="metric-card">
          <span className="metric-label">Artifact 状态</span>
          <strong>{formatNullable(data?.status, "not_ready")}</strong>
          <small>run_id: {formatNullable(data?.run_id, "暂无")}</small>
        </div>
        <div className="metric-card">
          <span className="metric-label">Artifact 数量</span>
          <strong>{formatNumber(data?.count ?? data?.artifacts?.length, 0)}</strong>
          <small>JSON / CSV / Markdown / Parquet</small>
        </div>
        <div className="metric-card">
          <span className="metric-label">Research runs</span>
          <strong>{formatNumber(data?.runs?.length, 0)}</strong>
          <small>{formatDateTime(runRows(data)[0]?.created_at)}</small>
        </div>
        <div className="metric-card">
          <span className="metric-label">Active/Prediction</span>
          <strong>{data?.active_updated || data?.customer_prediction_generated ? "unexpected" : "not generated"}</strong>
          <small>资料归档不发布 active</small>
        </div>
      </div>
      <div className="notice-card">
        <strong>Artifact directory</strong>
        <p>{formatNullable(data?.artifact_dir, "暂无归档目录")}</p>
      </div>
      <DataTable
        data={artifactRows(data)}
        emptyLabel="暂无 artifacts；请先运行研究回测或 candidate 研究流程。"
        columns={[
          { key: "type", title: "类型" },
          { key: "downloadable", title: "下载形态" },
          { key: "file_path", title: "文件路径" },
        ]}
      />
      <DataTable
        data={runRows(data)}
        emptyLabel="暂无 research_runs 记录"
        columns={[
          { key: "run_id", title: "Run ID", render: (row) => formatNullable(row.run_id || row.id) },
          { key: "candidate_version", title: "Candidate", render: (row) => formatNullable(row.candidate_version || row.version) },
          { key: "status", title: "状态", render: (row) => formatNullable(row.status) },
          { key: "created_at", title: "创建时间", render: (row) => formatDateTime(row.created_at || row.generated_at) },
          { key: "artifact_dir", title: "目录", render: (row) => formatNullable(row.artifact_dir || row.path) },
        ]}
      />
    </SectionCard>
  );
}
