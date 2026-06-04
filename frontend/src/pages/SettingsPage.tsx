import { useCallback, useState } from "react";
import {
  buildSystemRepairPlan,
  getDataStatus,
  generateFullSystemTxtReport,
  getKeyDiagnostics,
  getLatestFullSystemTxtReport,
  getProcessStatus,
  getSettingsStatus,
  getSystemHealth,
  resetSettingsSecrets,
  saveSettingsSecrets,
  shutdownBackend,
  testProvider
} from "../api/terminal";
import type { DataSourceStatus, KeyDiagnosticsPayload, ProcessStatusPayload, SystemHealth, SystemRepairPlanPayload, TerminalSettingsStatus } from "../api/types";
import { ErrorState } from "../components/common/ErrorState";
import { LoadingState } from "../components/common/LoadingState";
import { MetricCard } from "../components/common/MetricCard";
import { StatusPill } from "../components/common/StatusPill";
import { SectionCard } from "../components/layout/SectionCard";
import { TrainingDatasetStatusPanel } from "../components/model/TrainingDatasetStatusPanel";
import { useLocalSetting } from "../hooks/useLocalSetting";
import { usePolling } from "../hooks/usePolling";
import { useUIMode } from "../context/UIModeContext";
import { formatDateTime, formatNullable } from "../utils/format";

type SaveMode = "alpha" | "news" | "both";

export function SettingsPage() {
  const loader = useCallback(() => getSettingsStatus(), []);
  const { data: status, error, loading, refresh } = usePolling<TerminalSettingsStatus>(loader, 60000);
  const [refreshMs, setRefreshMs] = useLocalSetting("refreshInterval", 30000);
  const [showDebug, setShowDebug] = useLocalSetting("showDebug", false);
  const [showSampleData, setShowSampleData] = useLocalSetting("showSampleData", true);
  const [autoStopBackendOnClose, setAutoStopBackendOnClose] = useLocalSetting("autoStopBackendOnClose", true);
  const { uiMode, setUIMode } = useUIMode();
  const [alphaKey, setAlphaKey] = useState("");
  const [newsKey, setNewsKey] = useState("");
  const [managedToken, setManagedToken] = useState("");
  const [managedEndpoint, setManagedEndpoint] = useState("");
  const [tushareToken, setTushareToken] = useState("");
  const [showAlpha, setShowAlpha] = useState(false);
  const [showNews, setShowNews] = useState(false);
  const [showManagedToken, setShowManagedToken] = useState(false);
  const [showTushareToken, setShowTushareToken] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [confirmReset, setConfirmReset] = useState(false);
  const [dataSources, setDataSources] = useState<DataSourceStatus[]>([]);
  const [systemHealth, setSystemHealth] = useState<SystemHealth | null>(null);
  const [testing, setTesting] = useState(false);
  const [reportBusy, setReportBusy] = useState(false);
  const [fullReportPath, setFullReportPath] = useState("");
  const [fullReportJsonPath, setFullReportJsonPath] = useState("");
  const [diagnosticsBundlePath, setDiagnosticsBundlePath] = useState("");
  const [fullReportPreview, setFullReportPreview] = useState("");
  const [repairPlanBusy, setRepairPlanBusy] = useState(false);
  const [repairPlan, setRepairPlan] = useState<SystemRepairPlanPayload | null>(null);
  const [keyDiagnostics, setKeyDiagnostics] = useState<KeyDiagnosticsPayload | null>(null);
  const [testingProvider, setTestingProvider] = useState<string | null>(null);
  const [processStatus, setProcessStatus] = useState<ProcessStatusPayload | null>(null);
  const [shutdownBusy, setShutdownBusy] = useState(false);

  async function saveSecrets(mode: SaveMode) {
    const payload: { SN_ALPHA_VANTAGE_KEY?: string; SN_NEWSAPI_KEY?: string } = {};
    if ((mode === "alpha" || mode === "both") && alphaKey.trim()) payload.SN_ALPHA_VANTAGE_KEY = alphaKey.trim();
    if ((mode === "news" || mode === "both") && newsKey.trim()) payload.SN_NEWSAPI_KEY = newsKey.trim();

    setSaving(true);
    setMessage(null);
    try {
      const result = await saveSettingsSecrets(payload);
      if (result.success) {
        if (mode === "alpha" || mode === "both") setAlphaKey("");
        if (mode === "news" || mode === "both") setNewsKey("");
      }
      setMessage(result.message_zh || "密钥已保存到本机用户目录。");
      await refresh();
    } catch (exc) {
      setMessage(exc instanceof Error ? exc.message : "保存失败，请检查输入。");
    } finally {
      setSaving(false);
    }
  }

  async function saveManagedProxyToken() {
    setSaving(true);
    setMessage(null);
    try {
      const result = await saveSettingsSecrets({
        SN_MANAGED_DATA_PROXY_TOKEN: managedToken.trim(),
        SN_MANAGED_DATA_PROXY_URL: managedEndpoint.trim()
      });
      if (result.success) {
        setManagedToken("");
        setManagedEndpoint("");
      }
      setMessage(result.message_zh || "托管数据服务 token 已保存到本机用户目录。");
      await refresh();
    } catch (exc) {
      setMessage(exc instanceof Error ? exc.message : "保存托管数据服务 token 失败。");
    } finally {
      setSaving(false);
    }
  }

  async function saveTushareToken() {
    setSaving(true);
    setMessage(null);
    try {
      const result = await saveSettingsSecrets({ SN_TUSHARE_TOKEN: tushareToken.trim() });
      if (result.success) setTushareToken("");
      setMessage(result.message_zh || "Tushare token 已保存到本机用户目录。");
      await refresh();
    } catch (exc) {
      setMessage(exc instanceof Error ? exc.message : "保存 Tushare token 失败。");
    } finally {
      setSaving(false);
    }
  }

  async function resetSecrets() {
    if (!confirmReset) {
      setConfirmReset(true);
      setMessage("请再次点击确认清除本机密钥；其他用户数据不会删除。");
      return;
    }
    setSaving(true);
    setMessage(null);
    try {
      const result = await resetSettingsSecrets();
      setAlphaKey("");
      setNewsKey("");
      setConfirmReset(false);
      setMessage(result.message_zh || "密钥已清除。");
      await refresh();
    } catch (exc) {
      setMessage(exc instanceof Error ? exc.message : "重置失败，请稍后重试。");
    } finally {
      setSaving(false);
    }
  }

  async function testConnection() {
    setTesting(true);
    setMessage(null);
    try {
      const [sources, health, process] = await Promise.all([getDataStatus(), getSystemHealth(), getProcessStatus()]);
      setDataSources(sources);
      setSystemHealth(health);
      setProcessStatus(process);
      setMessage("连接检查完成；未配置的数据源会显示为未配置，不影响进入终端。");
    } catch (exc) {
      setMessage(exc instanceof Error ? exc.message : "连接检查失败，请确认后端正在运行。");
    } finally {
      setTesting(false);
    }
  }

  async function refreshProcessStatus() {
    const payload = await getProcessStatus();
    setProcessStatus(payload);
    return payload;
  }

  async function stopBackendService() {
    setShutdownBusy(true);
    setMessage(null);
    try {
      const result = await shutdownBackend("settings_page");
      setMessage(result.message_zh || "后台服务关闭请求已发送。");
      setProcessStatus((previous) => ({
        ...(previous || {}),
        shutdown_requested: true,
        pid_file_exists: false,
        pid_running: false,
        shutdown_at: result.shutdown_at
      }));
    } catch (exc) {
      setMessage(exc instanceof Error ? exc.message : "停止后台服务失败。");
    } finally {
      setShutdownBusy(false);
    }
  }

  async function generateFullReport() {
    setReportBusy(true);
    setMessage(null);
    try {
      const result = await generateFullSystemTxtReport();
      const latest = await getLatestFullSystemTxtReport();
      const path = String(result.latest_txt_path || result.txt_path || latest.txt_path || "");
      const jsonPath = String(result.json_path || latest.json_path || "");
      const bundlePath = String(result.diagnostics_bundle_path || latest.diagnostics_bundle_path || result.summary?.diagnostics_bundle_path || "");
      setFullReportPath(path);
      setFullReportJsonPath(jsonPath);
      setDiagnosticsBundlePath(bundlePath);
      setFullReportPreview(String(latest.text_preview || ""));
      setMessage(path ? "完整系统 TXT 报告已生成。" : "完整系统 TXT 报告已生成，路径见报告中心。");
    } catch (exc) {
      setMessage(exc instanceof Error ? exc.message : "完整系统 TXT 报告生成失败。");
    } finally {
      setReportBusy(false);
    }
  }

  async function copyFullReportSummary() {
    const text = fullReportPreview || `TXT: ${fullReportPath}\nZIP: ${diagnosticsBundlePath}`;
    try {
      await navigator.clipboard?.writeText(text);
      setMessage("报告摘要已复制。");
    } catch {
      setMessage("浏览器未允许复制；请直接使用页面显示的路径。");
    }
  }

  async function generateRepairPlan() {
    setRepairPlanBusy(true);
    setMessage(null);
    try {
      const result = await buildSystemRepairPlan();
      setRepairPlan(result);
      setMessage(result.status === "success" ? "系统修复计划已生成。" : result.message_zh || "系统修复计划已更新。");
    } catch (exc) {
      setMessage(exc instanceof Error ? exc.message : "系统修复计划生成失败。");
    } finally {
      setRepairPlanBusy(false);
    }
  }

  function repairPlanSummaryText() {
    const issues = repairPlan?.issues || [];
    const header = [
      `overall_status: ${repairPlan?.overall_status || "unknown"}`,
      `repair_plan_md: ${repairPlan?.markdown_path || "not_generated"}`,
      `active_updated: ${repairPlan?.active_updated ? "true" : "false"}`,
      `customer_prediction_generated: ${repairPlan?.customer_prediction_generated ? "true" : "false"}`
    ];
    const rows = issues.map((issue) => `${issue.priority || "P?"} ${issue.id || "ISSUE"} ${issue.title || "Untitled"} | ${issue.evidence || "No evidence"}`);
    return [...header, ...rows].join("\n");
  }

  async function copyRepairPlanSummary() {
    try {
      await navigator.clipboard?.writeText(repairPlanSummaryText());
      setMessage("修复摘要已复制。");
    } catch {
      setMessage("浏览器未允许复制；请直接使用页面显示的修复计划路径。");
    }
  }

  async function loadKeyDiagnostics() {
    const payload = await getKeyDiagnostics();
    setKeyDiagnostics(payload);
    return payload;
  }

  async function testOnlineKey(provider: "alpha_vantage" | "newsapi") {
    setTestingProvider(provider);
    setMessage(null);
    try {
      const result = await testProvider(provider);
      await loadKeyDiagnostics();
      setMessage(result.message_zh || "在线 key 验证完成。");
    } catch (exc) {
      setMessage(exc instanceof Error ? exc.message : "在线 key 验证失败。");
    } finally {
      setTestingProvider(null);
    }
  }

  async function testTushareKey() {
    setTestingProvider("tushare");
    setMessage(null);
    try {
      const result = await testProvider("tushare");
      await loadKeyDiagnostics();
      setMessage(result.message_zh || "Tushare token 验证完成。");
    } catch (exc) {
      setMessage(exc instanceof Error ? exc.message : "Tushare token 验证失败。");
    } finally {
      setTestingProvider(null);
    }
  }

  async function testManagedProxy() {
    setTestingProvider("managed_proxy");
    setMessage(null);
    try {
      const result = await testProvider("managed_proxy");
      await loadKeyDiagnostics();
      setMessage(result.message_zh || "托管数据服务连接测试完成。");
    } catch (exc) {
      setMessage(exc instanceof Error ? exc.message : "托管数据服务连接测试失败。");
    } finally {
      setTestingProvider(null);
    }
  }

  const apiAddress = status?.api_base_url || window.location.origin;
  const terminalAddress = status?.terminal_url || `${window.location.origin}/terminal`;
  const repairIssues = repairPlan?.issues || [];
  const repairIssueGroups = (["P0", "P1", "P2"] as const).map((priority) => ({
    priority,
    issues: repairIssues.filter((issue) => issue.priority === priority)
  }));
  const repairPlanTone = repairPlan?.overall_status === "research_ready" ? "good" : repairPlan?.overall_status === "blocked_for_prediction" ? "bad" : "warn";

  return (
    <div className="page-stack">
      <SectionCard title="显示模式" subtitle="默认启动模式：简洁；需要完整链路时切换专业。">
        <div className="button-row">
          <button className={uiMode === "simple" ? "secondary-button active" : "secondary-button"} type="button" onClick={() => setUIMode("simple")}>
            简洁
          </button>
          <button className={uiMode === "professional" ? "secondary-button active" : "secondary-button"} type="button" onClick={() => setUIMode("professional")}>
            专业
          </button>
        </div>
        <p className="muted">简洁模式只保留核心入口；专业模式显示完整工作台。</p>
      </SectionCard>

      <SectionCard
        title="发行方默认 key"
        subtitle="私有发行版可预配置 Alpha Vantage 与 NewsAPI；客户安装后可直接使用，也可以在本页替换为自己的 key。"
      >
        <div className="metric-grid">
          <MetricCard
            label="Alpha Vantage 来源"
            value={status?.alpha_vantage_source_label_zh || (status?.alpha_vantage_configured ? "已配置" : "未配置")}
            hint={status?.alpha_vantage_ui_message_zh || status?.alpha_vantage_masked || "公开版默认不内置发行方 key"}
            tone={status?.alpha_vantage_configured ? "good" : "warn"}
          />
          <MetricCard
            label="NewsAPI 来源"
            value={status?.newsapi_source_label_zh || (status?.newsapi_configured ? "已配置" : "未配置")}
            hint={status?.newsapi_ui_message_zh || status?.newsapi_masked || "公开版默认不内置发行方 key"}
            tone={status?.newsapi_configured ? "good" : "warn"}
          />
          <MetricCard
            label="客户替换能力"
            value="保留"
            hint="用户手动保存的 key 优先于发行方默认 key。"
            tone="good"
          />
          <MetricCard
            label="前端安全"
            value="不保存完整 key"
            hint="页面只显示 masked key 和 source，不写本地浏览器存储，不放 URL。"
            tone="good"
          />
        </div>
        <p className="warning-text">
          状态可为：已预配置 / 用户自定义 / 未配置。私有发行版内置 key 只适合内部离线交付；公开 GitHub release 不应包含发行方 key。高级用户可能逆向提取安装包内资源，长期方案仍是托管数据服务或 license token。
        </p>
      </SectionCard>

      <SectionCard title="系统设置" subtitle="配置本机数据源、启动路径和前端偏好；没有密钥也可以继续使用终端。">
        {loading && !status ? <LoadingState label="正在读取本机配置状态..." /> : null}
        {error && !status ? <ErrorState message={error} onRetry={refresh} /> : null}

        <div className="metric-grid">
          <MetricCard
            label="Alpha Vantage"
            value={status?.alpha_vantage_configured ? "已配置" : "未配置"}
            hint={`${status?.alpha_vantage_masked || "可稍后配置"} / ${status?.alpha_vantage_source_label_zh || status?.alpha_vantage_source || "none"}`}
            tone={status?.alpha_vantage_configured ? "good" : "warn"}
          />
          <MetricCard
            label="NewsAPI"
            value={status?.newsapi_configured ? "已配置" : "未配置"}
            hint={`${status?.newsapi_masked || "可稍后配置"} / ${status?.newsapi_source_label_zh || status?.newsapi_source || "none"}`}
            tone={status?.newsapi_configured ? "good" : "warn"}
          />
          <MetricCard label="本地配置目录" value={status?.config_path || "数据暂缺"} />
          <MetricCard label="最后更新时间" value={formatDateTime(status?.last_update_time)} />
        </div>
      </SectionCard>

      <SectionCard title="密钥配置" subtitle="密钥只保存在本机用户目录；保存后输入框会自动清空，页面只显示脱敏结果。">
        <div className="settings-grid secret-form">
          <label>
            Alpha Vantage 密钥
            <div className="inline-input-action">
              <input
                autoComplete="off"
                type={showAlpha ? "text" : "password"}
                value={alphaKey}
                onChange={(event) => setAlphaKey(event.target.value)}
                placeholder="留空则不修改"
              />
              <button className="ghost-button" type="button" onClick={() => setShowAlpha((value) => !value)}>
                {showAlpha ? "隐藏" : "显示"}
              </button>
            </div>
          </label>
          <label>
            NewsAPI 密钥
            <div className="inline-input-action">
              <input
                autoComplete="off"
                type={showNews ? "text" : "password"}
                value={newsKey}
                onChange={(event) => setNewsKey(event.target.value)}
                placeholder="留空则不修改"
              />
              <button className="ghost-button" type="button" onClick={() => setShowNews((value) => !value)}>
                {showNews ? "隐藏" : "显示"}
              </button>
            </div>
          </label>
        </div>
        <div className="button-row">
          <button className="primary-button" disabled={saving || !alphaKey.trim()} type="button" onClick={() => void saveSecrets("alpha")}>
            保存 Alpha Vantage
          </button>
          <button className="primary-button" disabled={saving || !newsKey.trim()} type="button" onClick={() => void saveSecrets("news")}>
            保存 NewsAPI
          </button>
          <button className="primary-button" disabled={saving || (!alphaKey.trim() && !newsKey.trim())} type="button" onClick={() => void saveSecrets("both")}>
            同时保存
          </button>
          <button className="ghost-button" disabled={saving} type="button" onClick={() => void resetSecrets()}>
            {confirmReset ? "确认重置本机密钥" : "重置为发行方默认"}
          </button>
        </div>
        <p className="warning-text">密钥仅保存在本机用户目录，不会写入前端，不会上传。私有发行版可在重置后恢复发行方默认 key；日志只显示脱敏信息。</p>
        {message ? <StatusPill label={message} tone={message.includes("失败") || message.includes("过短") ? "bad" : "good"} /> : null}
      </SectionCard>

      <SectionCard title="在线 API key 验证" subtitle="验证 Alpha Vantage 与 NewsAPI 的运行期读取链路；页面只显示脱敏 key 和状态。">
        <div className="button-row">
          <button className="primary-button" disabled={testingProvider === "alpha_vantage"} type="button" onClick={() => void testOnlineKey("alpha_vantage")}>
            {testingProvider === "alpha_vantage" ? "正在测试 Alpha Vantage..." : "测试 Alpha Vantage"}
          </button>
          <button className="primary-button" disabled={testingProvider === "newsapi"} type="button" onClick={() => void testOnlineKey("newsapi")}>
            {testingProvider === "newsapi" ? "正在测试 NewsAPI..." : "测试 NewsAPI"}
          </button>
          <button className="ghost-button" type="button" onClick={() => void loadKeyDiagnostics()}>
            刷新 key 诊断
          </button>
        </div>
        <div className="metric-grid">
          <MetricCard
            label="Alpha Vantage 验证"
            value={keyDiagnostics?.alpha_vantage?.last_validation_status || "尚未测试"}
            hint={`${keyDiagnostics?.alpha_vantage?.source_label_zh || keyDiagnostics?.alpha_vantage?.source || status?.alpha_vantage_source_label_zh || status?.alpha_vantage_source || "none"} / ${keyDiagnostics?.alpha_vantage?.masked || status?.alpha_vantage_masked || "未配置"}`}
            tone={keyDiagnostics?.alpha_vantage?.configured || status?.alpha_vantage_configured ? "good" : "warn"}
          />
          <MetricCard
            label="NewsAPI 验证"
            value={keyDiagnostics?.newsapi?.last_validation_status || "尚未测试"}
            hint={`${keyDiagnostics?.newsapi?.source_label_zh || keyDiagnostics?.newsapi?.source || status?.newsapi_source_label_zh || status?.newsapi_source || "none"} / ${keyDiagnostics?.newsapi?.masked || status?.newsapi_masked || "未配置"}`}
            tone={keyDiagnostics?.newsapi?.configured || status?.newsapi_configured ? "good" : "warn"}
          />
        </div>
        <p className="muted">如果出现 rate_limited、key_invalid 或 network_failed，请按状态提示处理；完整 key 不会返回到前端。</p>
      </SectionCard>

      <SectionCard title="Tushare 期货基础数据" subtitle="配置 SN_TUSHARE_TOKEN 后可刷新沪锡合约信息、日线、仓单、结算参数、持仓排名和交易日历；不用于实盘交易。">
        <div className="metric-grid">
          <MetricCard
            label="Tushare"
            value={status?.tushare_configured ? "已配置" : "未配置"}
            hint={`${status?.tushare_masked || "可稍后配置"} / ${status?.tushare_source_label_zh || status?.tushare_source || "none"}`}
            tone={status?.tushare_configured ? "good" : "warn"}
          />
          <MetricCard
            label="用途"
            value="期货基础数据"
            hint="用于 fut_basic / trade_cal / fut_daily / fut_wsr / fut_settle / fut_holding，不用于实盘交易。"
            tone="neutral"
          />
        </div>
        <div className="settings-grid secret-form">
          <label>
            Tushare token
            <div className="inline-input-action">
              <input
                autoComplete="off"
                type={showTushareToken ? "text" : "password"}
                value={tushareToken}
                onChange={(event) => setTushareToken(event.target.value)}
                placeholder="留空则不修改"
                aria-label="Tushare token"
              />
              <button className="ghost-button" type="button" onClick={() => setShowTushareToken((value) => !value)}>
                {showTushareToken ? "隐藏" : "显示"}
              </button>
            </div>
          </label>
        </div>
        <div className="button-row">
          <button className="primary-button" disabled={saving || !tushareToken.trim()} type="button" onClick={() => void saveTushareToken()}>
            保存 Tushare token
          </button>
          <button className="ghost-button" disabled={testingProvider === "tushare"} type="button" onClick={() => void testTushareKey()}>
            {testingProvider === "tushare" ? "正在测试 Tushare..." : "测试 Tushare"}
          </button>
        </div>
        <p className="warning-text">SN_TUSHARE_TOKEN 只保存在本机用户目录，API 和前端仅显示 masked/source/configured，不返回完整 token。</p>
      </SectionCard>

      <SectionCard title="托管数据服务" subtitle="客户无需 CSV/Excel；可选托管字段补齐通道默认关闭，不影响本地终端。">
        <div className="metric-grid">
          <MetricCard
            label="托管服务"
            value={status?.managed_data_proxy_configured && status?.managed_data_proxy_endpoint_configured ? "已配置" : "未配置"}
            hint={`${status?.managed_data_proxy_masked || "可稍后配置"} / endpoint: ${status?.managed_data_proxy_endpoint_configured ? "已配置" : "未配置"}`}
            tone={status?.managed_data_proxy_configured && status?.managed_data_proxy_endpoint_configured ? "good" : "warn"}
          />
          <MetricCard label="客户上传文件" value="否" hint="系统会优先尝试在线数据源。" tone="good" />
        </div>
        <div className="settings-grid secret-form">
          <label>
            托管数据服务 endpoint
            <div className="inline-input-action">
              <input
                autoComplete="off"
                type="text"
                value={managedEndpoint}
                onChange={(event) => setManagedEndpoint(event.target.value)}
                placeholder={status?.managed_data_proxy_endpoint || "https://issuer.example"}
                aria-label="托管数据服务 endpoint"
              />
            </div>
          </label>
          <label>
            托管数据服务 license token
            <div className="inline-input-action">
              <input
                autoComplete="off"
                type={showManagedToken ? "text" : "password"}
                value={managedToken}
                onChange={(event) => setManagedToken(event.target.value)}
                placeholder="留空则不修改"
                aria-label="托管数据服务 license token"
              />
              <button className="ghost-button" type="button" onClick={() => setShowManagedToken((value) => !value)}>
                {showManagedToken ? "隐藏" : "显示"}
              </button>
            </div>
          </label>
        </div>
        <div className="button-row">
          <button className="primary-button" disabled={saving || (!managedToken.trim() && !managedEndpoint.trim())} type="button" onClick={() => void saveManagedProxyToken()}>
            保存托管服务 token / endpoint
          </button>
          <button
            className="ghost-button"
            disabled={testingProvider === "managed_proxy"}
            type="button"
            onClick={() => void testManagedProxy()}
          >
            {testingProvider === "managed_proxy" ? "正在测试托管服务..." : "测试托管服务"}
          </button>
        </div>
        <p className="warning-text">
          托管数据服务用于后续补齐 LME、现货、基差、库存和仓单等机构级字段；第三方 API key 由发行方服务器维护，不会写入公开安装包。
        </p>
      </SectionCard>

      <SectionCard title="连接检查" subtitle="用于确认后端、数据源和本地缓存状态；未配置外部 key 时会给出中文说明。">
        <button className="primary-button" disabled={testing} type="button" onClick={() => void testConnection()}>
          {testing ? "正在测试连接..." : "测试连接"}
        </button>
        {systemHealth ? (
          <div className="status-table settings-status-table">
            <div className="status-row">
              <span>API 状态</span>
              <strong>{formatNullable(systemHealth.health?.api_status, "数据暂缺")}</strong>
            </div>
            <div className="status-row">
              <span>数据状态</span>
              <strong>{formatNullable(systemHealth.health?.data_status, "数据暂缺")}</strong>
            </div>
            <div className="status-row">
              <span>模型状态</span>
              <strong>{formatNullable(systemHealth.health?.model_status, "数据暂缺")}</strong>
            </div>
          </div>
        ) : null}
        {dataSources.length ? (
          <div className="source-grid">
            {dataSources.map((source) => (
              <div className="source-card" key={source.source_name || source.message_zh}>
                <div>
                  <strong>{formatNullable(source.source_name, "数据源")}</strong>
                  <StatusPill
                    label={source.success ? (source.from_cache ? "使用缓存" : "正常") : source.enabled ? "数据源失败" : "未配置"}
                    tone={source.success ? "good" : source.enabled ? "bad" : "warn"}
                  />
                </div>
                <span>{formatNullable(source.message_zh, source.enabled ? "本周期未更新" : "未配置")}</span>
                <em>{formatDateTime(source.last_update)}</em>
              </div>
            ))}
          </div>
        ) : (
          <p className="muted">点击“测试连接”后会显示 Sina/本地行情、Alpha Vantage、NewsAPI 和本地缓存状态。</p>
        )}
      </SectionCard>

      <SectionCard title="启动和路径" subtitle="这些路径用于排查问题；安装目录只读时，运行数据仍写入本机用户目录。">
        <div className="status-table">
          <div className="status-row">
            <span>当前 API 地址</span>
            <strong>{apiAddress}</strong>
          </div>
          <div className="status-row">
            <span>当前终端地址</span>
            <strong>{terminalAddress}</strong>
          </div>
          <div className="status-row">
            <span>用户数据目录</span>
            <strong>{formatNullable(status?.user_data_dir)}</strong>
          </div>
          <div className="status-row">
            <span>日志目录</span>
            <strong>{formatNullable(status?.logs_dir)}</strong>
          </div>
          <div className="status-row">
            <span>报告目录</span>
            <strong>{formatNullable(status?.reports_dir)}</strong>
          </div>
        </div>
      </SectionCard>

      <SectionCard title="后台服务生命周期" subtitle="关闭终端时默认停止本机后台服务；不会关闭浏览器，也不会杀无关 Python 进程。">
        <div className="metric-grid">
          <MetricCard
            label="后台 PID"
            value={processStatus?.pid ? String(processStatus.pid) : "未读取"}
            hint={processStatus?.pid_running ? "运行中" : processStatus?.shutdown_requested ? "已请求关闭" : "点击刷新状态"}
            tone={processStatus?.pid_running ? "good" : "warn"}
          />
          <MetricCard
            label="后台端口"
            value={processStatus?.port ? String(processStatus.port) : "未读取"}
            hint={processStatus?.host || "127.0.0.1"}
            tone="neutral"
          />
          <MetricCard
            label="Session"
            value={processStatus?.session_id || "未读取"}
            hint={processStatus?.started_at ? `启动：${formatDateTime(processStatus.started_at)}` : "后台启动后写入 runtime/session"}
            tone="neutral"
          />
          <MetricCard
            label="关闭设置"
            value={autoStopBackendOnClose ? "已开启" : "已关闭"}
            hint="关闭终端时自动停止后台服务"
            tone={autoStopBackendOnClose ? "good" : "warn"}
          />
        </div>
        <div className="settings-grid">
          <label className="checkbox-line">
            <input checked={autoStopBackendOnClose} type="checkbox" onChange={(event) => setAutoStopBackendOnClose(event.target.checked)} />
            关闭终端时自动停止后台服务
          </label>
        </div>
        <div className="button-row">
          <button className="secondary-button" type="button" onClick={() => void refreshProcessStatus()}>
            刷新后台状态
          </button>
          <button className="danger-button" disabled={shutdownBusy} type="button" onClick={() => void stopBackendService()}>
            {shutdownBusy ? "正在停止后台服务..." : "停止后台服务"}
          </button>
        </div>
        <p className="muted">停止后台服务会释放本机 API 端口；如需继续使用终端，请重新启动 SNInsightTerminal。</p>
      </SectionCard>

      <SectionCard title="前端偏好" subtitle="只保存界面偏好，不保存任何数据源密钥。">
        <div className="settings-grid">
          <label>
            自动刷新间隔（毫秒）
            <input type="number" min={5000} step={5000} value={refreshMs} onChange={(event) => setRefreshMs(Number(event.target.value))} />
          </label>
          <label className="checkbox-line">
            <input checked={showDebug} type="checkbox" onChange={(event) => setShowDebug(event.target.checked)} />
            显示技术明细
          </label>
          <label className="checkbox-line">
            <input checked={showSampleData} type="checkbox" onChange={(event) => setShowSampleData(event.target.checked)} />
            是否显示样例数据（默认开启；关闭后无真实数据时显示空状态）
          </label>
        </div>
        <p className="warning-text">样例数据仅用于演示界面结构，不代表真实行情或预测；点击一键刷新数据后，真实缓存优先显示。</p>
      </SectionCard>

      <SectionCard title="完整系统 TXT 报告" subtitle="生成系统运行、数据、模型、回测、性能、错误和建议摘要；不包含完整 key。">
        <div className="button-row">
          <button className="primary-button" disabled={reportBusy} type="button" onClick={() => void generateFullReport()}>
            {reportBusy ? "正在生成完整 TXT 报告..." : "生成完整系统 TXT 报告"}
          </button>
          <button className="secondary-button" disabled={!fullReportPath} type="button" onClick={() => setMessage(fullReportPath ? `下载 TXT：${fullReportPath}` : "请先生成报告。")}>
            下载 TXT
          </button>
          <button className="secondary-button" disabled={!diagnosticsBundlePath} type="button" onClick={() => setMessage(diagnosticsBundlePath ? `下载诊断包：${diagnosticsBundlePath}` : "请先生成报告。")}>
            下载诊断包
          </button>
          <button className="ghost-button" disabled={!fullReportPath && !fullReportPreview} type="button" onClick={() => void copyFullReportSummary()}>
            复制摘要
          </button>
          {fullReportPath ? <StatusPill label="已生成" tone="good" /> : null}
        </div>
        {fullReportPath ? (
          <div className="status-table">
            <div className="status-row">
              <span>最新 TXT 报告</span>
              <strong>{fullReportPath}</strong>
            </div>
            <div className="status-row">
              <span>JSON 报告</span>
              <strong>{fullReportJsonPath || "待生成"}</strong>
            </div>
            <div className="status-row">
              <span>诊断包 ZIP</span>
              <strong>{diagnosticsBundlePath || "待生成"}</strong>
            </div>
          </div>
        ) : (
          <p className="muted">报告会写入 outputs/reports；报告中心可展示和下载 latest 版本。</p>
        )}
      </SectionCard>

      <SectionCard title="系统修复计划" subtitle="读取最新 full_system_report 和诊断产物生成 P0/P1/P2 修复清单；不训练、不发布 active、不生成客户预测。">
        <div className="button-row">
          <button className="primary-button" disabled={repairPlanBusy} type="button" onClick={() => void generateRepairPlan()}>
            {repairPlanBusy ? "正在生成系统修复计划..." : "生成系统修复计划"}
          </button>
          <button
            className="secondary-button"
            disabled={!repairPlan?.markdown_path}
            type="button"
            onClick={() => setMessage(repairPlan?.markdown_path ? `下载 repair_plan.md：${repairPlan.markdown_path}` : "请先生成系统修复计划。")}
          >
            下载 repair_plan.md
          </button>
          <button className="ghost-button" disabled={!repairIssues.length} type="button" onClick={() => void copyRepairPlanSummary()}>
            复制修复摘要
          </button>
          {repairPlan ? <StatusPill label={repairPlan.overall_status || "已生成"} tone={repairPlanTone} /> : null}
        </div>

        {repairPlan?.markdown_path ? (
          <div className="status-table">
            <div className="status-row">
              <span>Markdown 修复计划</span>
              <strong>{repairPlan.markdown_path}</strong>
            </div>
            <div className="status-row">
              <span>JSON 修复计划</span>
              <strong>{repairPlan.json_path || "待生成"}</strong>
            </div>
            <div className="status-row">
              <span>安全边界</span>
              <strong>
                active_updated={repairPlan.active_updated ? "true" : "false"} / customer_prediction_generated=
                {repairPlan.customer_prediction_generated ? "true" : "false"}
              </strong>
            </div>
          </div>
        ) : (
          <p className="muted">生成后会写入 outputs/diagnostics/system_repair_plan.md 和 system_repair_plan.json。</p>
        )}

        {repairIssues.length ? (
          <div className="two-column">
            {repairIssueGroups.map((group) => (
              <div className="explain-block" key={group.priority}>
                <h4>{group.priority}</h4>
                {group.issues.length ? (
                  <ul>
                    {group.issues.map((issue) => (
                      <li key={issue.id || `${group.priority}-${issue.title}`}>
                        <strong>{issue.id || "ISSUE"}</strong> {issue.title || "未命名问题"}
                        <br />
                        <span>{issue.evidence || "暂无证据摘要"}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="muted">暂无 {group.priority} 问题。</p>
                )}
              </div>
            ))}
          </div>
        ) : null}
      </SectionCard>

      <SectionCard title="训练数据集状态" subtitle="基于真实行情和可用因子构建训练样本；不训练模型、不生成预测、不生成回测。">
        <TrainingDatasetStatusPanel />
      </SectionCard>

      <SectionCard title="数据源说明与故障排查" subtitle="首次使用时可以先跳过外部数据源配置，终端仍会展示可用状态。">
        <div className="two-column">
          <div className="explain-block">
            <h4>数据源说明</h4>
            <ul>
              <li>Sina/本地行情：用于基础行情和本地缓存状态。</li>
              <li>Alpha Vantage：用于汇率、利率和跨市场宏观代理数据。</li>
              <li>NewsAPI：用于海外锡、FOMC、供应扰动和产业新闻补充。</li>
              <li>本地缓存：外部数据失败时保留上一版可用数据，不伪装为最新。</li>
            </ul>
          </div>
          <div className="explain-block">
            <h4>常见问题</h4>
            <ul>
              <li>数据源未配置：进入本页填写密钥，也可以跳过。</li>
              <li>API 连接失败：确认后端已启动，端口未被占用。</li>
              <li>浏览器未自动打开：手动访问当前终端地址。</li>
              <li>查找日志：打开上方“日志目录”，查看 launcher.log。</li>
            </ul>
          </div>
        </div>
        <p className="disclaimer-line">仅供沪锡期货量化投研参考，不构成投资建议，不承诺收益，不接实盘交易。</p>
      </SectionCard>
    </div>
  );
}
