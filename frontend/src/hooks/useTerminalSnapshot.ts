import { useCallback } from "react";
import { getTerminalSnapshot } from "../api/terminal";
import type { TerminalSnapshot } from "../api/types";
import { usePolling } from "./usePolling";

export function useTerminalSnapshot(intervalMs = 30000) {
  const loader = useCallback(() => getTerminalSnapshot(), []);
  return usePolling<TerminalSnapshot>(loader, intervalMs);
}
