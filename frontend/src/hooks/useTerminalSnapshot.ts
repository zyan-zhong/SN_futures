import { useCallback } from "react";
import { getTerminalSnapshotLite } from "../api/terminal";
import type { TerminalSnapshot } from "../api/types";
import { usePolling } from "./usePolling";

export function useTerminalSnapshot(intervalMs = 30000, enabled = true) {
  const loader = useCallback(() => getTerminalSnapshotLite(), []);
  return usePolling<TerminalSnapshot>(loader, intervalMs, enabled);
}
