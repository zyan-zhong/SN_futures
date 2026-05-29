import { useState } from "react";
import { saveSettingsSecrets } from "../../api/terminal";
import type { DataSourceStatus, SystemHealth, TerminalSettingsStatus } from "../../api/types";
import { formatDateTime, formatNullable } from "../../utils/format";
import { StatusPill } from "../common/StatusPill";

const STEPS = ["欢迎", "合规边界", "Alpha Vantage", "NewsAPI", "完成"] as const;

export function FirstRunWizard({
  settings,
  dataSources,
  systemHealth,
  onRefresh,
  onComplete
}: {
  settings?: TerminalSettingsStatus;
  dataSources: DataSourceStatus[];
  systemHealth?: SystemHealth;
  onRefresh: () => Promise<void>;
  onComplete: () => void;
}) {
  const [step, setStep] = useState(0);
  const [alphaKey, setAlphaKey] = useState("");
  const [newsKey, setNewsKey] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const alphaReady = Boolean(settings?.alpha_vantage_configured);
  const newsReady = Boolean(settings?.newsapi_configured);
  const isLast = step === STEPS.length - 1;

  async function saveOne(kind: "alpha" | "news") {
    const payload =
      kind === "alpha" ? { SN_ALPHA_VANTAGE_KEY: alphaKey } : { SN_NEWSAPI_KEY: newsKey };
    setSaving(true);
    setMessage(null);
    try {
      const result = await saveSettingsSecrets(payload);
      if (kind === "alpha") setAlphaKey("");
      if (kind === "news") setNewsKey("");
      setMessage(result.message_zh || "密钥已保存到本机用户目录。");
      await onRefresh();
    } catch (exc) {
      setMessage(exc instanceof Error ? exc.message : "保存失败，请检查输入。");
    } finally {
      setSaving(false);
    }
  }

  function next() {
    if (isLast) {
      onComplete();
      return;
    }
    setStep((value) => Math.min(value + 1, STEPS.length - 1));
  }

  function skipAll() {
    onComplete();
  }

  return (
    <div className="onboarding-backdrop" role="dialog" aria-modal="true" aria-labelledby="first-run-title">
      <div className="onboarding-card">
        <div className="onboarding-steps" aria-label="首次启动步骤">
          {STEPS.map((label, index) => (
            <span className={index === step ? "active" : ""} key={label}>
              {index + 1}. {label}
            </span>
          ))}
        </div>

        {step === 0 ? (
          <section className="onboarding-panel">
            <p className="eyebrow">首次启动向导</p>
            <h2 id="first-run-title">欢迎使用 SNInsightTerminal</h2>
            <p>
              这是面向上海期货交易所沪锡 SN 的本地量化投研终端。你可以先跳过外部数据源配置，系统会以“未配置 / 本地缓存 / 研究观察”的方式继续运行。
            </p>
            <div className="metric-grid">
              <div className="mini-status-card">
                <span>Alpha Vantage</span>
                <strong>{alphaReady ? "已配置" : "未配置"}</strong>
              </div>
              <div className="mini-status-card">
                <span>NewsAPI</span>
                <strong>{newsReady ? "已配置" : "未配置"}</strong>
              </div>
              <div className="mini-status-card">
                <span>系统状态</span>
                <strong>{formatNullable(systemHealth?.health?.api_status, "可进入终端")}</strong>
              </div>
            </div>
          </section>
        ) : null}

        {step === 1 ? (
          <section className="onboarding-panel">
            <p className="eyebrow">用途与边界</p>
            <h2>先理解，再使用</h2>
            <ul className="check-list">
              <li>用于沪锡期货量化投研、事件监控、回测诊断和风险辅助。</li>
              <li>没有外部 key 时，数据源会显示“未配置”，终端不会崩溃。</li>
              <li>观望或降级状态不会显示交易点位。</li>
              <li>仅供沪锡期货量化投研参考，不构成投资建议，不承诺收益，不接实盘交易。</li>
            </ul>
          </section>
        ) : null}

        {step === 2 ? (
          <section className="onboarding-panel">
            <p className="eyebrow">可选数据源</p>
            <h2>配置 Alpha Vantage key</h2>
            <p>用于汇率、利率和跨市场宏观代理数据。可以稍后配置。</p>
            <label className="secret-input-line">
              <span>Alpha Vantage key</span>
              <input
                autoComplete="off"
                type="password"
                value={alphaKey}
                onChange={(event) => setAlphaKey(event.target.value)}
                placeholder={alphaReady ? "已配置，留空不修改" : "可留空跳过"}
              />
            </label>
            <button className="primary-button" disabled={saving || !alphaKey.trim()} type="button" onClick={() => void saveOne("alpha")}>
              保存 Alpha Vantage
            </button>
          </section>
        ) : null}

        {step === 3 ? (
          <section className="onboarding-panel">
            <p className="eyebrow">可选新闻源</p>
            <h2>配置 NewsAPI key</h2>
            <p>用于海外锡、FOMC、供应扰动和产业新闻补充。可以稍后配置。</p>
            <label className="secret-input-line">
              <span>NewsAPI key</span>
              <input
                autoComplete="off"
                type="password"
                value={newsKey}
                onChange={(event) => setNewsKey(event.target.value)}
                placeholder={newsReady ? "已配置，留空不修改" : "可留空跳过"}
              />
            </label>
            <button className="primary-button" disabled={saving || !newsKey.trim()} type="button" onClick={() => void saveOne("news")}>
              保存 NewsAPI
            </button>
          </section>
        ) : null}

        {step === 4 ? (
          <section className="onboarding-panel">
            <p className="eyebrow">准备就绪</p>
            <h2>完成并进入终端</h2>
            <p>你可以随时在“系统设置”中配置或重置密钥。</p>
            <div className="source-grid">
              {dataSources.slice(0, 4).map((source) => (
                <div className="source-card compact-source-card" key={source.source_name || source.message_zh}>
                  <strong>{formatNullable(source.source_name, "数据源")}</strong>
                  <span>{source.enabled ? source.message_zh || "已启用" : "未配置或未启用"}</span>
                  <em>{formatDateTime(source.last_update)}</em>
                </div>
              ))}
            </div>
          </section>
        ) : null}

        <p className="warning-text">密钥仅保存在本机用户目录，不会写入前端，不会上传。</p>
        {message ? <StatusPill label={message} tone={message.includes("失败") || message.includes("过短") ? "bad" : "good"} /> : null}

        <div className="onboarding-actions">
          <button className="ghost-button" type="button" onClick={skipAll}>
            稍后配置
          </button>
          <button className="ghost-button" type="button" onClick={skipAll}>
            不再自动弹出
          </button>
          {step > 0 ? (
            <button className="ghost-button" type="button" onClick={() => setStep((value) => Math.max(value - 1, 0))}>
              上一步
            </button>
          ) : null}
          <button className="primary-button" type="button" onClick={next}>
            {isLast ? "完成并进入终端" : "下一步"}
          </button>
        </div>
      </div>
    </div>
  );
}

