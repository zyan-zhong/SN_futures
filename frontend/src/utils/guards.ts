import type { PredictionCard } from "../api/types";

export function isLowQuality(score?: number | null): boolean {
  return typeof score === "number" && Number.isFinite(score) && score < 0.55;
}

export function isDegraded(status?: string): boolean {
  return Boolean(status && (status.includes("降级") || status.toLowerCase().includes("degraded")));
}

export function isObserveSignal(signal?: string): boolean {
  return !signal || signal.includes("观望") || signal.toLowerCase().includes("neutral") || signal.toLowerCase().includes("observe");
}

export function hasTradePoints(card: PredictionCard): boolean {
  if (isObserveSignal(card.signal) || isDegraded(card.model_status) || isLowQuality(card.data_quality)) return false;
  return card.entry !== null && card.entry !== undefined && card.stop_loss !== null && card.stop_loss !== undefined && card.take_profit !== null && card.take_profit !== undefined;
}
