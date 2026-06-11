import { useCallback, useEffect, useRef, useState } from "react";

export function usePolling<T>(loader: () => Promise<T>, intervalMs: number, enabled = true) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(enabled);
  const mounted = useRef(true);
  const backoff = useRef(intervalMs);
  const timer = useRef<number | null>(null);

  const refresh = useCallback(async () => {
    if (typeof document !== "undefined" && document.hidden) {
      return;
    }
    setLoading(true);
    try {
      const result = await loader();
      if (mounted.current) {
        setData(result);
        setError(null);
        backoff.current = intervalMs;
      }
    } catch (exc) {
      if (mounted.current) {
        setError(exc instanceof Error ? exc.message : "请求失败");
        backoff.current = Math.min(Math.max(backoff.current * 2, 2000), 30000);
      }
    } finally {
      if (mounted.current) setLoading(false);
    }
  }, [intervalMs, loader]);

  useEffect(() => {
    mounted.current = true;
    if (!enabled) {
      setLoading(false);
      setError(null);
      return undefined;
    }

    const schedule = (delay: number) => {
      if (timer.current !== null) window.clearTimeout(timer.current);
      timer.current = window.setTimeout(() => {
        void refresh().finally(() => {
          if (mounted.current && enabled) schedule(backoff.current);
        });
      }, delay);
    };

    const handleVisibility = () => {
      if (!document.hidden && mounted.current) {
        void refresh();
      }
    };

    void refresh().finally(() => schedule(backoff.current));
    document.addEventListener("visibilitychange", handleVisibility);
    return () => {
      mounted.current = false;
      if (timer.current !== null) window.clearTimeout(timer.current);
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [enabled, refresh]);

  return { data, error, loading, refresh };
}
