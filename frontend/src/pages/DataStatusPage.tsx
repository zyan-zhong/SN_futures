import { useEffect, useState } from "react";
import type { TerminalSnapshot } from "../api/types";
import type { PageKey } from "../App";
import { exportDiagnosticsBundle, getOnlineDataSourcesStatus, getRefreshLastError, testProvider } from "../api/terminal";
import { ErrorBoundary } from "../components/common/ErrorBoundary";
import { DataTable } from "../components/common/DataTable";
import { DataSourceStatusPanel } from "../components/data/DataSourceStatusPanel";
import { RefreshTaskPanel } from "../components/data/RefreshTaskPanel";
import { RuntimeDiagnosticsPanel } from "../components/data/RuntimeDiagnosticsPanel";
import { SectionCard } from "../components/layout/SectionCard";

export function DataStatusPage({
  snapshot,
  onNavigate,
  onRefresh
}: {
  snapshot?: TerminalSnapshot | null;
  onNavigate?: (page: PageKey) => void;
  onRefresh?: () => void;
}) {
  const [providerResult, setProviderResult] = useState("尚未测试数据源。");
  const [lastError, setLastError] = useState("尚未查看最近错误。");
  const [diagnosticsPath, setDiagnosticsPath] = useState("");
  const [onlineSources, setOnlineSources] = useState<Array<Record<string, unknown>>>([]);

  useEffect(() => {
    void getOnlineDataSourcesStatus()
      .then((payload) => setOnlineSources((payload.sources || []) as Array<Record<string, unknown>>))
      .catch(() => setOnlineSources([]));
  }, []);

  async function handleProviderTest(provider: "market" | "newsapi" | "shfe_public" | "akshare_news" | "miit_policy") {
    try {
      const result = await testProvider(provider);
      setProviderResult(result.message_zh || "测试完成。");
    } catch (error) {
      setProviderResult(`测试数据源失败：${error instanceof Error ? error.message : "未知错误"}`);
    }
  }

  async function handleLastError() {
    try {
      const result = await getRefreshLastError();
      const message = String(result.latest_error?.message_zh || result.message_zh || "暂无刷新错误记录。");
      const actions = Array.isArray(result.next_actions_zh) ? result.next_actions_zh.join("；") : "";
      setLastError(actions ? `${message} 下一步：${actions}` : message);
    } catch (error) {
      setLastError(`查看最近错误失败：${error instanceof Error ? error.message : "未知错误"}`);
    }
  }

  async function handleExportDiagnostics() {
    try {
      const result = await exportDiagnosticsBundle();
      const text = JSON.stringify(result.bundle ?? result, null, 2);
      if (navigator.clipboard) {
        await navigator.clipboard.writeText(text);
      }
      setDiagnosticsPath(result.path || "诊断信息已复制。");
    } catch (error) {
      setDiagnosticsPath(`复制诊断信息失败：${error instanceof Error ? error.message : "未知错误"}`);
    }
  }

  return (
    <ErrorBoundary moduleName="数据源状态">
      <div className="page-stack">
        <SectionCard title="数据源可观测性" subtitle="刷新失败时可测试数据源、查看最近错误，并导出脱敏诊断信息。">
          <div className="button-row">
            <button className="ghost-button" type="button" onClick={() => handleProviderTest("market")}>
              测试数据源：行情
            </button>
            <button className="ghost-button" type="button" onClick={() => handleProviderTest("newsapi")}>
              测试数据源：NewsAPI
            </button>
            <button className="ghost-button" type="button" onClick={() => handleProviderTest("shfe_public")}>
              测试数据源：SHFE 公共数据
            </button>
            <button className="ghost-button" type="button" onClick={() => handleProviderTest("akshare_news")}>
              测试数据源：AKShare 新闻
            </button>
            <button className="ghost-button" type="button" onClick={() => handleProviderTest("miit_policy")}>
              测试数据源：工信部政策
            </button>
            <button className="ghost-button" type="button" onClick={handleLastError}>
              查看最近错误
            </button>
            <button className="primary-button" type="button" onClick={handleExportDiagnostics}>
              复制诊断信息
            </button>
          </div>
          <div className="reason-list">
            <span>网络失败：检查本机网络、代理或防火墙。</span>
            <span>key 未配置：前往设置页配置，或继续使用缓存/样例模式。</span>
            <span>key 无效：检查密钥是否复制完整。</span>
            <span>被限流：稍后重试，或降低刷新频率。</span>
            <span>返回为空：扩大时间窗口或检查关键词。</span>
            <span>字段不匹配：查看刷新日志中的 provider_attempts。</span>
            <span>非交易时段：等待下一交易窗口。</span>
            <span>缓存过期：点击一键刷新数据。</span>
          </div>
          <p className="muted">测试结果：{providerResult}</p>
          <p className="muted">最近错误：{lastError}</p>
          <p className="muted">打开日志目录提示：请查看本机用户目录下的 logs 文件夹；诊断导出位置：{diagnosticsPath || "尚未导出"}</p>
        </SectionCard>

        <DataSourceStatusPanel
          sources={snapshot?.data_status?.sources}
          logsDir={snapshot?.system_health?.health?.warnings?.find((item) => item.includes("logs"))}
          onSettings={() => onNavigate?.("settings")}
          onRefresh={onRefresh}
        />
        <SectionCard title="在线数据源矩阵" subtitle="客户不需要 CSV/Excel；系统自动尝试公开在线源、API key 源和可选托管源。">
          <DataTable
            data={onlineSources}
            columns={[
              { key: "category", title: "数据类别" },
              { key: "source_id", title: "当前来源" },
              { key: "provider", title: "provider" },
              { key: "requires_key", title: "是否需要 key", render: (row) => (row.requires_key ? "是" : "否") },
              { key: "requires_paid_account", title: "是否需要托管/付费源", render: (row) => (row.requires_paid_account ? "可能需要" : "否") },
              { key: "client_upload_required", title: "是否需要客户上传文件", render: () => "否" },
              { key: "status", title: "状态" },
              { key: "row_count", title: "行数" },
              { key: "from_cache", title: "缓存", render: (row) => (row.from_cache ? "使用缓存" : "否") },
              { key: "last_success_time", title: "最近成功时间" },
              { key: "cooldown_until", title: "下次重试", render: (row) => String(row.cooldown_until || "无") },
              { key: "legal_note", title: "当前阻断原因", render: (row) => String(row.legal_note || row.status || "暂无") },
              { key: "next_actions_zh", title: "下一步建议", render: (row) => Array.isArray(row.next_actions_zh) ? row.next_actions_zh.join("；") : "查看诊断" },
            ]}
          />
          <p className="muted">
            当前公开在线源未返回沪锡相关行时，系统不会伪造数据。完整 LME、现货、库存和基差可通过发行方托管数据服务补齐。
          </p>
          <div className="notice-card">
            <strong>Alpha Vantage cross-market refresh states</strong>
            <p>
              rate_limited / using_cache_rate_limited / cooldown_until / last_success_time 会用于说明 USD/CNY、US10Y 和 copper proxy
              是最新刷新、使用最近成功缓存，还是正在等待下一次重试窗口。
            </p>
          </div>
        </SectionCard>
        <RefreshTaskPanel initialStatus={snapshot?.refresh_status} onAfterRefresh={onRefresh} />
        <RuntimeDiagnosticsPanel />
      </div>
    </ErrorBoundary>
  );
}
