import { useCallback, useEffect, useRef, useState } from "react";

export function usePolling<T>(loader: () => Promise<T>, intervalMs: number, enabled = true) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const mounted = useRef(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const result = await loader();
      if (mounted.current) {
        setData(result);
        setError(null);
      }
    } catch (exc) {
      if (mounted.current) setError(exc instanceof Error ? exc.message : "请求失败");
    } finally {
      if (mounted.current) setLoading(false);
    }
  }, [loader]);

  useEffect(() => {
    mounted.current = true;
    if (!enabled) return undefined;
    void refresh();
    const id = window.setInterval(() => void refresh(), intervalMs);
    return () => {
      mounted.current = false;
      window.clearInterval(id);
    };
  }, [enabled, intervalMs, refresh]);

  return { data, error, loading, refresh };
}
