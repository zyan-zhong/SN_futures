import { useCallback, useEffect, useState } from "react";
import { getDataStatus, getSettingsStatus, getSystemHealth } from "../api/terminal";
import type { DataSourceStatus, SystemHealth, TerminalSettingsStatus } from "../api/types";
import { markFirstRunCompleted, shouldPromptForConfiguration } from "../utils/onboarding";

export interface FirstRunState {
  loading: boolean;
  shouldShow: boolean;
  settings?: TerminalSettingsStatus;
  dataSources: DataSourceStatus[];
  systemHealth?: SystemHealth;
  error?: string;
  refresh: () => Promise<void>;
  complete: () => void;
}

export function useFirstRun(): FirstRunState {
  const [loading, setLoading] = useState(true);
  const [shouldShow, setShouldShow] = useState(false);
  const [settings, setSettings] = useState<TerminalSettingsStatus | undefined>();
  const [dataSources, setDataSources] = useState<DataSourceStatus[]>([]);
  const [systemHealth, setSystemHealth] = useState<SystemHealth | undefined>();
  const [error, setError] = useState<string | undefined>();

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(undefined);
    const [settingsResult, dataResult, healthResult] = await Promise.allSettled([
      getSettingsStatus(),
      getDataStatus(),
      getSystemHealth()
    ]);

    const nextSettings = settingsResult.status === "fulfilled" ? settingsResult.value : undefined;
    const nextSources = dataResult.status === "fulfilled" ? dataResult.value : [];
    const nextHealth = healthResult.status === "fulfilled" ? healthResult.value : undefined;

    setSettings(nextSettings);
    setDataSources(nextSources);
    setSystemHealth(nextHealth);
    setShouldShow(
      shouldPromptForConfiguration(nextSettings?.alpha_vantage_configured, nextSettings?.newsapi_configured)
    );

    const firstError = [settingsResult, dataResult, healthResult].find((item) => item.status === "rejected");
    setError(firstError?.status === "rejected" ? (firstError.reason instanceof Error ? firstError.reason.message : "首次启动检查失败") : undefined);
    setLoading(false);
  }, []);

  const complete = useCallback(() => {
    markFirstRunCompleted();
    setShouldShow(false);
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { loading, shouldShow, settings, dataSources, systemHealth, error, refresh, complete };
}

