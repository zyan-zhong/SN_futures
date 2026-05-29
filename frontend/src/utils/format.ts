import type { NullableNumber } from "../api/types";
import { COPY } from "./copy";

export function formatNullable(value: unknown, fallback: string = COPY.missingData): string {
  if (value === null || value === undefined) return fallback;
  if (typeof value === "number" && !Number.isFinite(value)) return fallback;
  const text = String(value).trim();
  if (!text || ["nan", "none", "null", "undefined"].includes(text.toLowerCase())) return fallback;
  return text;
}

export function formatNumber(value: NullableNumber, digits = 2, fallback: string = COPY.missingData): string {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return fallback;
  return Number(value).toLocaleString("zh-CN", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits
  });
}

export function formatPercent(value: NullableNumber, digits = 2, fallback: string = COPY.missingData): string {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return fallback;
  const number = Math.abs(Number(value)) <= 1 ? Number(value) * 100 : Number(value);
  return `${number.toLocaleString("zh-CN", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits
  })}%`;
}

export function formatPrice(value: NullableNumber, fallback: string = COPY.missingData): string {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return fallback;
  return `${Number(value).toLocaleString("zh-CN", { maximumFractionDigits: 0 })} 元/吨`;
}

export function toFiniteNumber(value: unknown): number | null {
  if (value === null || value === undefined) return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

export function formatDateTime(value: unknown, fallback: string = "本周期未更新"): string {
  const text = formatNullable(value, "");
  if (!text) return fallback;
  const date = new Date(text);
  if (Number.isNaN(date.getTime())) return text;
  return date.toLocaleString("zh-CN", { hour12: false });
}

export function formatDirection(value: unknown): string {
  const text = formatNullable(value, "观望");
  const normalized = text.toLowerCase();
  if (["up", "long", "bullish", "上涨", "偏多"].includes(normalized) || text.includes("多")) return "上涨";
  if (["down", "short", "bearish", "下跌", "偏空"].includes(normalized) || text.includes("空")) return "下跌";
  return "观望";
}

export function formatSignal(value: unknown): string {
  const text = formatNullable(value, "观望");
  const normalized = text.toLowerCase();
  if (normalized.includes("long") || text.includes("多头")) return "多头研究观察";
  if (normalized.includes("short") || text.includes("空头")) return "空头研究观察";
  if (text.includes("降级")) return "已降级为研究观察";
  return "观望";
}

export function formatSignalStrength(value: unknown, confidence?: NullableNumber): string {
  const text = formatNullable(value, "").toLowerCase();
  if (text.includes("strong") || text.includes("强")) return "强";
  if (text.includes("medium") || text.includes("中")) return "中";
  if (text.includes("weak") || text.includes("弱")) return "弱";
  if (confidence === null || confidence === undefined || !Number.isFinite(Number(confidence))) return "数据不足";
  const score = Number(confidence);
  if (score >= 0.75) return "强";
  if (score >= 0.6) return "中";
  if (score >= 0.45) return "弱";
  return "数据不足";
}

export function formatRange(range?: Array<NullableNumber>): string {
  if (!range || range.length < 2) return "数据暂缺";
  return `${formatPrice(range[0])} - ${formatPrice(range[1])}`;
}
