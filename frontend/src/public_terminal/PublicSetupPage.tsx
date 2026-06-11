import { useEffect, useState } from "react";
import { getPublicSettingsStatus, resetPublicSettings, runPublicProviderSmoke, savePublicSettings } from "./api";
import type { PublicSettingsStatus, PublicSmokePayload } from "./types";
import { friendlyReason, friendlyStatus, maskOrEmpty, technicalSummary } from "./userCopy";

export function PublicSetupPage() {
  const [settings, setSettings] = useState<PublicSettingsStatus | null>(null);
  const [baseUrl, setBaseUrl] = useState("");
  const [token, setToken] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState("");
  const [smoke, setSmoke] = useState<PublicSmokePayload | null>(null);

  async function reload() {
    setSettings(await getPublicSettingsStatus());
  }

  useEffect(() => {
    reload().catch(() => setSettings({ configured: false, sources: [] }));
  }, []);

  async function save() {
    setBusy("save");
    setMessage("");
    try {
      const result = await savePublicSettings({ base_url: baseUrl.trim(), token: token.trim(), provider: "local_api_provider" });
      setSettings(result);
      setToken("");
      setMessage(`已保存。显示为：${maskOrEmpty(result.masked || result.local_api_provider_token_masked || result.tushare_token_masked)}`);
    } catch (exc) {
      setMessage(exc instanceof Error ? exc.message : "保存失败，请检查输入。");
    } finally {
      setBusy("");
    }
  }

  async function reset() {
    setBusy("reset");
    setMessage("");
    try {
      const result = await resetPublicSettings();
      setSettings(result);
      setMessage("已清除本机保存的 key。");
    } catch (exc) {
      setMessage(exc instanceof Error ? exc.message : "清除失败，请稍后重试。");
    } finally {
      setBusy("");
    }
  }

  async function checkDataSource() {
    setBusy("check");
    setMessage("");
    try {
      const result = await runPublicProviderSmoke({ allow_remote: false, provider: "local_api_provider" });
      setSmoke(result);
      setMessage(result.status === "success" || result.status === "pass" ? "数据源检查通过。" : friendlyReason(result.error_code || result.blocking_reasons?.[0]));
    } catch (exc) {
      setMessage(exc instanceof Error ? exc.message : "数据源检查失败。");
    } finally {
      setBusy("");
    }
  }

  const masked = maskOrEmpty(settings?.masked || settings?.local_api_provider_token_masked || settings?.tushare_token_masked);

  return (
    <div className="page-stack public-terminal-page">
      <section className="section-card">
        <div className="section-card__header">
          <div>
            <h1>设置数据源</h1>
            <p>没有 key 也可以继续浏览；有 key 时保存到本机，只显示打码后的结果。</p>
          </div>
        </div>
        <div className="settings-grid secret-form">
          <label>
            数据源地址
            <input aria-label="数据源地址" autoComplete="off" type="url" value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} placeholder="https://..." />
          </label>
          <label>
            访问密钥
            <input aria-label="访问密钥" autoComplete="off" type="password" value={token} onChange={(event) => setToken(event.target.value)} placeholder="只保存在本机" />
          </label>
        </div>
        <div className="button-row">
          <button className="primary-button" type="button" disabled={busy === "save"} onClick={() => void save()}>
            {busy === "save" ? "保存中" : "保存设置"}
          </button>
          <button className="secondary-button" type="button" disabled={busy === "check"} onClick={() => void checkDataSource()}>
            {busy === "check" ? "检查中" : "运行数据源检查"}
          </button>
          <button className="ghost-button" type="button" onClick={() => setMessage("已跳过配置。下一步：到 Data Status 查看数据完整度。")}>
            跳过，稍后配置
          </button>
          <button className="ghost-button" type="button" disabled={busy === "reset"} onClick={() => void reset()}>
            清除设置
          </button>
        </div>
        <div className="metric-grid compact">
          <div className="metric-card">
            <span className="metric-label">key 状态</span>
            <strong>{settings?.configured ? "已配置" : "未配置"}</strong>
            <small>{masked}</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">数据源检查</span>
            <strong>{friendlyStatus(smoke?.status, "尚未检查")}</strong>
            <small>{smoke?.error_code ? friendlyReason(smoke.error_code) : "默认不访问真实网络。"}</small>
          </div>
        </div>
        {message ? <p role="status" className="inline-warning">{message}</p> : null}
      </section>

      <details className="technical-details-drawer">
        <summary>诊断详情</summary>
        <pre className="diagnostics-pre">
{`provider smoke / manifest / source_statuses
${technicalSummary({ settings, smoke })}`}
        </pre>
      </details>
    </div>
  );
}
