import { useCallback } from "react";
import { getTerminalSnapshotLite } from "../api/terminal";
import type { TerminalSnapshot } from "../api/types";
import { usePolling } from "./usePolling";

export function useTerminalSnapshot(intervalMs = 30000) {
  const loader = useCallback(() => getTerminalSnapshotLite(), []);
  return usePolling<TerminalSnapshot>(loader, intervalMs);
}
