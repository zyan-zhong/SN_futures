from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, asdict
from typing import Any

import pandas as pd

from .api_clients import AlphaVantageClient, NewsApiClient, RateLimitedCacheClient, SinaFinanceClient
from .contracts import resolve_target_contract
from .multimodal import article_feature_frame, build_historical_event_matches, summarize_articles
from .runtime import get_user_output_dir
from .settings_store import load_api_keys
from .news_store import upsert_articles
from .event_store import ingest_articles, update_provider_status


def _safe_float(values: list[str], index: int) -> float | None:
    try:
        raw = str(values[index]).replace(",", "").strip()
        return float(raw)
    except Exception:
        return None


def _normalize_sina_quote(row: dict[str, Any]) -> dict[str, Any]:
    fields = row.get("raw_fields", [])
    symbol = str(row.get("symbol", "") or "")
    if symbol.startswith("nf_"):
        open_price = _safe_float(fields, 2)
        high = _safe_float(fields, 3)
        low = _safe_float(fields, 4)
        latest = _safe_float(fields, 8) or _safe_float(fields, 6) or _safe_float(fields, 3)
        prev_close = _safe_float(fields, 10) or _safe_float(fields, 27) or _safe_float(fields, 2)
        volume = _safe_float(fields, 13)
        open_interest = _safe_float(fields, 14)
    else:
        open_price = _safe_float(fields, 1)
        prev_close = _safe_float(fields, 2)
        latest = _safe_float(fields, 3)
        high = _safe_float(fields, 4)
        low = _safe_float(fields, 5)
        volume = _safe_float(fields, 8)
        open_interest = _safe_float(fields, 9)
    return {
        "symbol": symbol,
        "name": row.get("name", ""),
        "open": open_price,
        "prev_close": prev_close,
        "latest": latest,
        "high": high,
        "low": low,
        "volume": volume,
        "open_interest": open_interest,
        "raw_text": row.get("raw_text", ""),
    }


def _extract_alpha_latest(payload: dict[str, Any], value_key: str) -> tuple[str | None, float | None]:
    data = payload.get("data", [])
    if isinstance(data, list) and data:
        first = data[0]
        if isinstance(first, dict):
            return str(first.get("date")), float(first.get(value_key)) if first.get(value_key) not in (None, "") else None
    if isinstance(payload, dict):
        for key, value in payload.items():
            if isinstance(value, dict):
                latest_key = sorted(value.keys())[-1] if value else None
                if latest_key is not None and isinstance(value[latest_key], dict):
                    latest_val = value[latest_key]
                    numeric = next((float(v) for v in latest_val.values() if str(v).replace(".", "", 1).replace("-", "", 1).isdigit()), None)
                    return str(latest_key), numeric
    return None, None


def _alpha_feed_to_articles(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    feed = payload.get("feed", []) if isinstance(payload, dict) else []
    if not isinstance(feed, list):
        return []
    direct_terms = {
        "tin",
        "lme",
        "shfe",
        "solder",
        "myanmar",
        "indonesia",
        "smelter",
        "mine",
        "mining",
        "ore",
        "concentrate",
        "metal",
        "metals",
        "commodity",
        "commodities",
        "china",
        "manufacturing",
        "pmi",
        "solar",
        "semiconductor",
        "electronics",
        "chip",
        "chips",
        "fed",
        "dollar",
        "yield",
        "tariff",
    }
    macro_terms = {"dollar", "fed", "rate", "yield", "inflation", "tariff", "pmi"}
    macro_context_terms = {"china", "manufacturing", "semiconductor", "solar", "commodity", "commodities", "metal", "metals", "electronics", "chip", "chips"}
    commodity_core_terms = {
        "tin",
        "lme",
        "shfe",
        "solder",
        "myanmar",
        "indonesia",
        "smelter",
        "mine",
        "mining",
        "ore",
        "concentrate",
        "metal",
        "metals",
        "commodity",
        "commodities",
        "china",
        "manufacturing",
        "pmi",
        "solar",
        "semiconductor",
        "electronics",
    }
    stock_noise_terms = {"earnings", "dividend", "stocks", "stock", "shares", "clients", "ai push"}
    rows: list[dict[str, Any]] = []
    for item in feed:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "") or "")
        summary = str(item.get("summary", "") or "")
        text = f"{title} {summary}".lower()
        title_tokens = set(re.findall(r"[a-z]+", title.lower()))
        tokens = set(re.findall(r"[a-z]+", text))
        direct_match = any((term in tokens) if " " not in term else (term in text) for term in direct_terms)
        commodity_core_match = any((term in tokens) if " " not in term else (term in text) for term in commodity_core_terms)
        title_core_match = any((term in title_tokens) if " " not in term else (term in title.lower()) for term in commodity_core_terms)
        title_macro_match = any((term in title_tokens) if " " not in term else (term in title.lower()) for term in macro_terms)
        noisy_stock_story = any((term in tokens) if " " not in term else (term in text) for term in stock_noise_terms)
        macro_context_match = any((term in tokens) if " " not in term else (term in text) for term in macro_context_terms) and any(
            (term in tokens) if " " not in term else (term in text) for term in macro_terms
        )
        if not commodity_core_match and not macro_context_match:
            continue
        if not title_core_match and not title_macro_match and not macro_context_match:
            continue
        if noisy_stock_story and not commodity_core_match:
            continue
        if not direct_match and not macro_context_match:
            continue
        rows.append(
            {
                "title": title,
                "description": summary,
                "content": summary,
                "url": item.get("url", ""),
                "publishedAt": item.get("time_published", ""),
                "source": {"name": item.get("source", "Alpha Vantage")},
            }
        )
    return rows


PUBLIC_POLICY_SOURCES = [
    ("shfe_public", "https://www.shfe.com.cn/news/notice/"),
    ("ndrc_policy", "https://www.ndrc.gov.cn/"),
    ("miit_policy", "https://www.miit.gov.cn/"),
]


def _contains_policy_keyword(text: str) -> bool:
    lower = text.lower()
    keywords = {
        "tin",
        "shfe",
        "lme",
        "myanmar",
        "indonesia",
        "semiconductor",
        "photovoltaic",
        "solar",
        "solder",
        "inventory",
        "warehouse",
        "\u9521",
        "\u6caa\u9521",
        "\u4e0a\u671f\u6240",
        "\u7f05\u7538",
        "\u5370\u5c3c",
        "\u9521\u77ff",
        "\u534a\u5bfc\u4f53",
        "\u5149\u4f0f",
        "\u710a\u9521",
        "\u5e93\u5b58",
        "\u4ed3\u5355",
    }
    return any(keyword.lower() in lower for keyword in keywords)


def _public_policy_articles() -> tuple[list[dict[str, Any]], list[SourceStatus]]:
    client = RateLimitedCacheClient()
    headers = {"User-Agent": "SNInsightTerminal/2.8"}
    rows: list[dict[str, Any]] = []
    statuses: list[SourceStatus] = []
    for source_name, url in PUBLIC_POLICY_SOURCES:
        try:
            resp = client.fetch_text(
                source=source_name,
                url=url,
                headers=headers,
                ttl_seconds=1800,
                min_interval_seconds=300,
                daily_limit=20,
                encoding="utf-8",
            )
            html = str(resp.payload or "")
            title_match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
            page_title = re.sub(r"\s+", " ", title_match.group(1)).strip() if title_match else source_name
            plain = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.IGNORECASE | re.DOTALL)
            plain = re.sub(r"<[^>]+>", " ", plain)
            plain = re.sub(r"\s+", " ", plain).strip()
            if _contains_policy_keyword(plain):
                hit_pos = min([pos for kw in ("\u9521", "tin", "semiconductor", "\u5149\u4f0f", "shfe") if (pos := plain.lower().find(kw.lower())) >= 0] or [0])
                snippet = plain[max(0, hit_pos - 80) : hit_pos + 260]
                rows.append(
                    {
                        "title": page_title[:160],
                        "description": snippet,
                        "content": snippet,
                        "url": url,
                        "publishedAt": pd.Timestamp.now(tz="Asia/Hong_Kong").isoformat(),
                        "source": {"name": source_name},
                        "provider": "public_policy" if source_name != "shfe_public" else "shfe_public",
                    }
                )
                statuses.append(
                    SourceStatus(
                        name=source_name,
                        enabled=True,
                        success=True,
                        from_cache=resp.from_cache,
                        fetched_at=resp.fetched_at,
                        message="\u516c\u5f00\u653f\u7b56/\u516c\u544a\u9875\u9762\u5df2\u547d\u4e2d\u6caa\u9521\u76f8\u5173\u5173\u952e\u8bcd\u3002",
                    )
                )
            else:
                statuses.append(
                    SourceStatus(
                        name=source_name,
                        enabled=True,
                        success=False,
                        from_cache=resp.from_cache,
                        fetched_at=resp.fetched_at,
                        message="\u516c\u5f00\u653f\u7b56/\u516c\u544a\u9875\u9762\u6682\u672a\u547d\u4e2d\u6caa\u9521\u76f8\u5173\u5173\u952e\u8bcd\u3002",
                    )
                )
        except Exception as exc:
            statuses.append(
                SourceStatus(
                    name=source_name,
                    enabled=True,
                    success=False,
                    from_cache=False,
                    fetched_at=None,
                    message=str(exc),
                )
            )
    return rows, statuses


def _akshare_news_articles() -> tuple[list[dict[str, Any]], list[SourceStatus]]:
    rows: list[dict[str, Any]] = []
    statuses: list[SourceStatus] = []
    try:
        import akshare as ak  # type: ignore
    except Exception as exc:
        return [], [
            SourceStatus(
                name="akshare_news",
                enabled=True,
                success=False,
                from_cache=False,
                fetched_at=None,
                message=f"akshare 新闻接口不可用：{exc}",
            )
        ]

    def _row_to_article(row: dict[str, Any], *, source: str, url: str) -> dict[str, Any] | None:
        title = str(row.get("标题") or row.get("title") or row.get("内容") or "")[:180]
        body = str(row.get("内容") or row.get("摘要") or row.get("summary") or title)
        text = f"{title} {body}"
        if not _contains_policy_keyword(text):
            return None
        date = str(row.get("发布日期") or row.get("date") or pd.Timestamp.now(tz="Asia/Hong_Kong").date())
        tm = str(row.get("发布时间") or row.get("time") or "00:00:00")
        published = date if "T" in date else f"{date}T{tm}"
        return {
            "title": title or body[:120],
            "description": body[:420],
            "content": body[:800],
            "url": url,
            "publishedAt": published,
            "source": {"name": source},
            "provider": source,
        }

    try:
        shmet_rows = []
        for symbol in ("锡", "小金属", "财经"):
            try:
                frame = ak.futures_news_shmet(symbol=symbol)
            except Exception:
                continue
            if hasattr(frame, "to_dict"):
                shmet_rows.extend(frame.head(30).to_dict(orient="records"))
        seen = set()
        for row in shmet_rows:
            article = _row_to_article(
                row,
                source="akshare_shmet",
                url="https://www.shmet.com/newsFlash/newsFlash.html?searchKeyword=%E9%94%A1",
            )
            if not article:
                continue
            key = article["title"]
            if key in seen:
                continue
            seen.add(key)
            rows.append(article)
        statuses.append(
            SourceStatus(
                name="akshare_shmet_news",
                enabled=True,
                success=bool(seen),
                from_cache=False,
                fetched_at=pd.Timestamp.now(tz="Asia/Hong_Kong").isoformat(),
                message=f"上海金属网/akshare 快讯命中 {len(seen)} 条沪锡相关记录。" if seen else "上海金属网/akshare 快讯暂未命中沪锡关键词。",
            )
        )
    except Exception as exc:
        statuses.append(SourceStatus("akshare_shmet_news", True, False, False, None, str(exc)))

    try:
        frame = ak.stock_info_global_cls(symbol="全部")
        cls_count = 0
        if hasattr(frame, "to_dict"):
            for row in frame.head(50).to_dict(orient="records"):
                article = _row_to_article(row, source="akshare_cls", url="https://www.cls.cn/telegraph")
                if article:
                    rows.append(article)
                    cls_count += 1
        statuses.append(
            SourceStatus(
                name="akshare_cls_news",
                enabled=True,
                success=cls_count > 0,
                from_cache=False,
                fetched_at=pd.Timestamp.now(tz="Asia/Hong_Kong").isoformat(),
                message=f"财联社/akshare 快讯命中 {cls_count} 条沪锡相关记录。" if cls_count else "财联社/akshare 快讯暂未命中沪锡关键词。",
            )
        )
    except Exception as exc:
        statuses.append(SourceStatus("akshare_cls_news", True, False, False, None, str(exc)))

    return rows, statuses


def _select_active_contract(quotes: list[dict[str, Any]], contract_meta: dict[str, Any]) -> dict[str, Any]:
    table = pd.DataFrame(quotes)
    candidates = contract_meta.get("candidates", []) if isinstance(contract_meta, dict) else []
    if table.empty or not isinstance(candidates, list) or not candidates:
        return contract_meta

    candidate_df = pd.DataFrame(candidates)
    if candidate_df.empty or "sina_symbol" not in candidate_df.columns:
        return contract_meta

    merged = candidate_df.merge(table, left_on="sina_symbol", right_on="symbol", how="left")
    if merged.empty:
        return contract_meta

    for col in ("latest", "volume", "open_interest"):
        merged[col] = pd.to_numeric(merged[col], errors="coerce")
    merged["month_rank"] = range(len(merged))
    merged = merged[merged["latest"].fillna(0) > 0].copy()
    if merged.empty:
        return contract_meta

    def _norm(series: pd.Series) -> pd.Series:
        if series.notna().sum() <= 1:
            return pd.Series(0.5, index=series.index)
        lo = float(series.min())
        hi = float(series.max())
        if hi <= lo:
            return pd.Series(0.5, index=series.index)
        return (series - lo) / (hi - lo)

    merged["oi_score"] = _norm(merged["open_interest"].fillna(0))
    merged["vol_score"] = _norm(merged["volume"].fillna(0))
    merged["near_score"] = 1.0 - merged["month_rank"] / max(len(merged) - 1, 1)
    merged["liquidity_score"] = 0.60 * merged["oi_score"] + 0.30 * merged["vol_score"] + 0.10 * merged["near_score"]
    best = merged.sort_values(["liquidity_score", "open_interest", "volume"], ascending=False).iloc[0]

    enriched = dict(contract_meta)
    enriched["active_contract"] = str(best.get("contract_code", contract_meta.get("target_contract", "")))
    enriched["active_contract_symbol"] = str(best.get("sina_symbol", contract_meta.get("target_contract_symbol", "")))
    enriched["active_contract_month"] = str(best.get("contract_month", contract_meta.get("target_contract_month", "")))
    enriched["active_contract_label"] = str(best.get("label", contract_meta.get("target_contract_label", "")))
    enriched["selection_rule"] = "liquidity_rank_open_interest_volume"
    enriched["liquidity_table"] = merged[
        ["contract_code", "contract_month", "sina_symbol", "latest", "volume", "open_interest", "liquidity_score"]
    ].sort_values("liquidity_score", ascending=False).to_dict(orient="records")
    return enriched


def history_symbol_from_snapshot(snapshot: dict[str, Any] | None) -> str:
    meta = snapshot.get("contract_meta", {}) if isinstance(snapshot, dict) else {}
    if not isinstance(meta, dict):
        return "SN0"
    contract_code = str(meta.get("active_contract", "") or meta.get("target_contract", "") or "").strip()
    if contract_code:
        return contract_code.upper()
    symbol = str(meta.get("active_contract_symbol", "") or meta.get("target_contract_symbol", "") or "").strip()
    if symbol.startswith("nf_"):
        return symbol.replace("nf_", "").upper()
    return symbol.upper() if symbol else "SN0"


def enrich_live_snapshot_with_history(
    snapshot: dict[str, Any] | None,
    raw: pd.DataFrame | None = None,
) -> dict[str, Any]:
    work = dict(snapshot or {})
    article_frame = article_feature_frame(work.get("articles", []) if isinstance(work.get("articles", []), list) else [])
    article_summary = summarize_articles(article_frame)
    work["text_summary"] = article_summary.to_dict()
    if raw is not None and not raw.empty:
        work["historical_matches"] = build_historical_event_matches(raw, article_summary)
    contract_meta = dict(work.get("contract_meta", {}) if isinstance(work.get("contract_meta", {}), dict) else {})
    requested_symbol = history_symbol_from_snapshot(work)
    actual_symbol = requested_symbol
    if raw is not None and not raw.empty:
        actual_symbol = str(raw.iloc[-1].get("history_symbol", requested_symbol) or requested_symbol)
        contract_meta["requested_history_symbol"] = str(raw.iloc[-1].get("requested_history_symbol", requested_symbol) or requested_symbol)
    contract_meta["history_symbol"] = actual_symbol
    work["contract_meta"] = contract_meta
    return work


@dataclass(frozen=True)
class SourceStatus:
    name: str
    enabled: bool
    success: bool
    from_cache: bool
    fetched_at: str | None
    message: str


def build_live_snapshot(
    raw: pd.DataFrame | None = None,
    symbols: list[str] | None = None,
    use_remote: bool = True,
) -> dict[str, Any]:
    contract_meta = resolve_target_contract()
    contract_meta.setdefault("active_contract", contract_meta.get("target_contract", ""))
    contract_meta.setdefault("active_contract_symbol", contract_meta.get("target_contract_symbol", ""))
    contract_meta.setdefault("active_contract_month", contract_meta.get("target_contract_month", ""))
    contract_meta.setdefault("active_contract_label", contract_meta.get("target_contract_label", ""))
    contract_meta.setdefault("selection_rule", contract_meta.get("roll_rule", "calendar_next_month"))
    candidate_symbols = [str(item.get("sina_symbol", "") or "") for item in contract_meta.get("candidates", []) if isinstance(item, dict)]
    default_symbols = candidate_symbols + [str(contract_meta.get("continuous_symbol", "nf_SN0") or "nf_SN0")]
    combined_symbols = [sym for sym in (symbols or []) if sym]
    for sym in default_symbols:
        if sym and sym not in combined_symbols:
            combined_symbols.insert(0, sym)
    symbols = combined_symbols or ["nf_SN0"]
    stored_keys = load_api_keys()
    alpha_key = os.environ.get("SN_ALPHA_VANTAGE_KEY") or stored_keys.get("SN_ALPHA_VANTAGE_KEY")
    news_key = os.environ.get("SN_NEWSAPI_KEY") or stored_keys.get("SN_NEWSAPI_KEY")

    sina_client = SinaFinanceClient()
    alpha_client = AlphaVantageClient(alpha_key)
    news_client = NewsApiClient(news_key)

    statuses: list[SourceStatus] = []
    quotes: list[dict[str, Any]] = []
    macro_summary: dict[str, Any] = {}
    article_rows: list[dict[str, Any]] = []
    historical_matches: list[dict[str, Any]] = []

    if use_remote:
        try:
            sina_resp = sina_client.fetch_quotes(symbols)
            quotes = [_normalize_sina_quote(row) for row in sina_client.parse_quotes(str(sina_resp.payload))]
            contract_meta = _select_active_contract(quotes, contract_meta)
            statuses.append(
                SourceStatus(
                    name="sina_finance",
                    enabled=True,
                    success=True,
                    from_cache=sina_resp.from_cache,
                    fetched_at=sina_resp.fetched_at,
                    message=f"已刷新 {contract_meta.get('active_contract', contract_meta.get('target_contract', 'sn'))} 的实时报价（短缓存保护）。",
                )
            )
        except Exception as exc:
            statuses.append(
                SourceStatus(
                    name="sina_finance",
                    enabled=True,
                    success=False,
                    from_cache=False,
                    fetched_at=None,
                    message=str(exc),
                )
            )

        if alpha_client.enabled():
            try:
                fx_resp = alpha_client.fetch_usd_cny_daily()
                yld_resp = alpha_client.fetch_treasury_10y()
                fx_date, fx_value = _extract_alpha_latest(fx_resp.payload, "4. close")
                yld_date, yld_value = _extract_alpha_latest(yld_resp.payload, "value")
                macro_summary = {
                    "usd_cny_date": fx_date,
                    "usd_cny": fx_value,
                    "us10y_date": yld_date,
                    "us10y": yld_value,
                }
                statuses.append(
                    SourceStatus(
                        name="alphavantage",
                        enabled=True,
                        success=True,
                        from_cache=fx_resp.from_cache and yld_resp.from_cache,
                        fetched_at=max(fx_resp.fetched_at, yld_resp.fetched_at),
                        message="宏观序列已刷新，并已按免费额度做保守限频。",
                    )
                )
            except Exception as exc:
                statuses.append(
                    SourceStatus(
                        name="alphavantage",
                        enabled=True,
                        success=False,
                        from_cache=False,
                        fetched_at=None,
                        message=str(exc),
                    )
                )
        else:
            statuses.append(
                SourceStatus(
                    name="alphavantage",
                    enabled=False,
                    success=False,
                    from_cache=False,
                    fetched_at=None,
                    message="未配置 SN_ALPHA_VANTAGE_KEY。",
                )
            )

        if news_client.enabled():
            try:
                news_resp = news_client.fetch_sn_news()
                payload = news_resp.payload if isinstance(news_resp.payload, dict) else {}
                article_rows = payload.get("articles", []) if isinstance(payload.get("articles", []), list) else []
                for row in article_rows:
                    if isinstance(row, dict):
                        row.setdefault("provider", "newsapi")
                statuses.append(
                    SourceStatus(
                        name="newsapi",
                        enabled=True,
                        success=True,
                        from_cache=news_resp.from_cache,
                        fetched_at=news_resp.fetched_at,
                        message="沪锡相关新闻已刷新，并已按免费额度做保守限频。",
                    )
                )
                if not article_rows and alpha_client.enabled():
                    try:
                        alpha_news_resp = alpha_client.fetch_macro_news()
                        alpha_payload = alpha_news_resp.payload if isinstance(alpha_news_resp.payload, dict) else {}
                        fallback_rows = _alpha_feed_to_articles(alpha_payload)
                        if fallback_rows:
                            for row in fallback_rows:
                                if isinstance(row, dict):
                                    row.setdefault("provider", "alphavantage_news_fallback")
                            article_rows = fallback_rows
                            statuses.append(
                                SourceStatus(
                                    name="alphavantage_news_fallback",
                                    enabled=True,
                                    success=True,
                                    from_cache=alpha_news_resp.from_cache,
                                    fetched_at=alpha_news_resp.fetched_at,
                                    message="NewsAPI 未返回锡相关结果，已补充 Alpha Vantage 新闻源。",
                                )
                            )
                    except Exception as fallback_exc:
                        statuses.append(
                            SourceStatus(
                                name="alphavantage_news_fallback",
                                enabled=True,
                                success=False,
                                from_cache=False,
                                fetched_at=None,
                                message=str(fallback_exc),
                            )
                        )
            except Exception as exc:
                statuses.append(
                    SourceStatus(
                        name="newsapi",
                        enabled=True,
                        success=False,
                        from_cache=False,
                        fetched_at=None,
                        message=str(exc),
                    )
                )
                if alpha_client.enabled():
                    try:
                        alpha_news_resp = alpha_client.fetch_macro_news()
                        alpha_payload = alpha_news_resp.payload if isinstance(alpha_news_resp.payload, dict) else {}
                        fallback_rows = _alpha_feed_to_articles(alpha_payload)
                        if fallback_rows:
                            for row in fallback_rows:
                                if isinstance(row, dict):
                                    row.setdefault("provider", "alphavantage_news_fallback")
                            article_rows = fallback_rows
                            statuses.append(
                                SourceStatus(
                                    name="alphavantage_news_fallback",
                                    enabled=True,
                                    success=True,
                                    from_cache=alpha_news_resp.from_cache,
                                    fetched_at=alpha_news_resp.fetched_at,
                                    message="NewsAPI 不可用，已自动回退到 Alpha Vantage 新闻源。",
                                )
                            )
                    except Exception as fallback_exc:
                        statuses.append(
                            SourceStatus(
                                name="alphavantage_news_fallback",
                                enabled=True,
                                success=False,
                                from_cache=False,
                                fetched_at=None,
                                message=str(fallback_exc),
                            )
                        )
        else:
            statuses.append(
                SourceStatus(
                    name="newsapi",
                    enabled=False,
                    success=False,
                    from_cache=False,
                    fetched_at=None,
                    message="未配置 SN_NEWSAPI_KEY。",
                )
            )
            if alpha_client.enabled():
                try:
                    alpha_news_resp = alpha_client.fetch_macro_news()
                    alpha_payload = alpha_news_resp.payload if isinstance(alpha_news_resp.payload, dict) else {}
                    fallback_rows = _alpha_feed_to_articles(alpha_payload)
                    if fallback_rows:
                        for row in fallback_rows:
                            if isinstance(row, dict):
                                row.setdefault("provider", "alphavantage_news_fallback")
                        article_rows = fallback_rows
                        statuses.append(
                            SourceStatus(
                                name="alphavantage_news_fallback",
                                enabled=True,
                                success=True,
                                from_cache=alpha_news_resp.from_cache,
                                fetched_at=alpha_news_resp.fetched_at,
                                message="未配置 NewsAPI，已自动使用 Alpha Vantage 新闻源。",
                            )
                        )
                except Exception as fallback_exc:
                    statuses.append(
                        SourceStatus(
                            name="alphavantage_news_fallback",
                            enabled=True,
                            success=False,
                            from_cache=False,
                            fetched_at=None,
                            message=str(fallback_exc),
                        )
                    )

        try:
            ak_news_rows, ak_news_statuses = _akshare_news_articles()
            if ak_news_rows:
                article_rows.extend(ak_news_rows)
            statuses.extend(ak_news_statuses)
        except Exception as exc:
            statuses.append(SourceStatus("akshare_news", True, False, False, None, str(exc)))

        try:
            policy_rows, policy_statuses = _public_policy_articles()
            if policy_rows:
                article_rows.extend(policy_rows)
            statuses.extend(policy_statuses)
        except Exception as exc:
            statuses.append(
                SourceStatus(
                    name="public_policy",
                    enabled=True,
                    success=False,
                    from_cache=False,
                    fetched_at=None,
                    message=str(exc),
                )
            )
    else:
        statuses.extend(
            [
                SourceStatus("sina_finance", True, False, False, None, "Remote refresh disabled."),
                SourceStatus("alphavantage", bool(alpha_key), False, False, None, "Remote refresh disabled."),
                SourceStatus("newsapi", bool(news_key), False, False, None, "Remote refresh disabled."),
            ]
        )

    article_frame = article_feature_frame(article_rows)
    article_summary = summarize_articles(article_frame)
    article_records: list[dict[str, Any]] = []
    if not article_frame.empty:
        article_records = article_frame.assign(
            published_at=article_frame["published_at"].astype(str)
        ).to_dict(orient="records")
    if raw is not None and not raw.empty:
        historical_matches = build_historical_event_matches(raw, article_summary)

    snapshot = {
        "generated_at": pd.Timestamp.now(tz="Asia/Hong_Kong").isoformat(),
        "contract_meta": contract_meta,
        "quotes": quotes,
        "macro_summary": macro_summary,
        "articles": article_records,
        "text_summary": article_summary.to_dict(),
        "historical_matches": historical_matches,
        "source_status": [asdict(item) for item in statuses],
        "rate_limit_policy": {
            "sina_finance": "cache 2s, interval 2s, daily cap 2000",
            "alphavantage": "cache 1800s, interval 60s, daily cap 20",
            "newsapi": "cache 300s, interval 90s, daily cap 90",
            "public_policy": "cache 1800s, interval 300s, daily cap 20 per source",
        },
    }
    return snapshot


def apply_live_snapshot_overlay(
    raw: pd.DataFrame,
    live_snapshot: dict[str, Any] | None = None,
) -> pd.DataFrame:
    if raw.empty or not isinstance(live_snapshot, dict) or not live_snapshot:
        return raw

    work = raw.copy()
    quotes = pd.DataFrame(live_snapshot.get("quotes", []))
    valid_quotes = pd.DataFrame()
    if not quotes.empty and "latest" in quotes.columns:
        valid_quotes = quotes[pd.to_numeric(quotes["latest"], errors="coerce").notna()].copy()

    overlay_info: dict[str, Any] = {}
    if not valid_quotes.empty:
        contract_meta = live_snapshot.get("contract_meta", {}) if isinstance(live_snapshot, dict) else {}
        preferred_symbol = str(contract_meta.get("active_contract_symbol", "") or contract_meta.get("target_contract_symbol", "") or "")
        preferred = valid_quotes[valid_quotes["symbol"] == preferred_symbol] if preferred_symbol else pd.DataFrame()
        quote_row = preferred.iloc[0] if not preferred.empty else valid_quotes.iloc[0]
        live_latest = float(quote_row.get("latest", 0.0) or 0.0)
        last_close = float(work["close"].iloc[-1]) if "close" in work.columns else 0.0
        if live_latest > 0 and last_close > 0:
            scale = live_latest / last_close
            for col in ("open", "high", "low", "close", "spot_price"):
                if col in work.columns:
                    work[col] = pd.to_numeric(work[col], errors="coerce") * scale
            overlay_info.update(
                {
                    "quote_symbol": str(quote_row.get("symbol", "")),
                    "quote_name": str(quote_row.get("name", "")),
                    "live_latest": live_latest,
                    "scale_factor": scale,
                }
            )
        last_idx = work.index[-1]
        for col, src in (("volume", "volume"), ("open_interest", "open_interest")):
            value = quote_row.get(src)
            if col in work.columns and value not in (None, ""):
                numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
                if pd.notna(numeric) and float(numeric) > 0:
                    work.at[last_idx, col] = float(numeric)

    macro_summary = live_snapshot.get("macro_summary", {})
    if isinstance(macro_summary, dict):
        last_idx = work.index[-1]
        if "usd_cny" in work.columns and macro_summary.get("usd_cny") not in (None, ""):
            work.at[last_idx, "usd_cny"] = float(macro_summary["usd_cny"])
        if "us10y" in work.columns and macro_summary.get("us10y") not in (None, ""):
            work.at[last_idx, "us10y"] = float(macro_summary["us10y"])

    if overlay_info:
        work.attrs["live_overlay"] = overlay_info
        if "data_source_mode" in work.columns:
            current_mode = str(work["data_source_mode"].iloc[-1] or "").strip()
            merged_mode = f"{current_mode}+live_quote_overlay" if current_mode else "live_quote_overlay"
            work["data_source_mode"] = merged_mode
        else:
            work["data_source_mode"] = "live_quote_overlay"
    return work


TICK_HISTORY_FILE = "sn_realtime_ticks.jsonl"


def _snapshot_active_quote(snapshot: dict[str, Any]) -> dict[str, Any]:
    meta = snapshot.get("contract_meta", {}) if isinstance(snapshot.get("contract_meta"), dict) else {}
    active_symbol = str(meta.get("active_contract_symbol", "") or meta.get("target_contract_symbol", ""))
    quotes = snapshot.get("quotes", []) if isinstance(snapshot.get("quotes"), list) else []
    quote_rows = [row for row in quotes if isinstance(row, dict)]
    if active_symbol:
        for row in quote_rows:
            if str(row.get("symbol", "")) == active_symbol and _safe_float([str(row.get("latest", ""))], 0):
                return row
    for row in quote_rows:
        latest = row.get("latest")
        try:
            if latest is not None and float(latest) > 0:
                return row
        except Exception:
            continue
    return {}


def _append_realtime_tick(snapshot: dict[str, Any], output_dir: Any) -> list[dict[str, Any]]:
    quote = _snapshot_active_quote(snapshot)
    if not quote:
        return []
    latest = quote.get("latest")
    try:
        latest_float = float(latest)
    except Exception:
        return []
    if latest_float <= 0:
        return []

    meta = snapshot.get("contract_meta", {}) if isinstance(snapshot.get("contract_meta"), dict) else {}
    ts = str(snapshot.get("generated_at", pd.Timestamp.now(tz="Asia/Hong_Kong").isoformat()))
    row = {
        "ts": ts,
        "symbol": str(quote.get("symbol", "")),
        "contract_code": str(meta.get("active_contract", meta.get("target_contract", ""))),
        "latest": latest_float,
        "volume": quote.get("volume"),
        "open_interest": quote.get("open_interest"),
        "source": "sina_finance",
    }
    path = output_dir / TICK_HISTORY_FILE
    rows: list[dict[str, Any]] = []
    if path.exists():
        try:
            lines = path.read_text(encoding="utf-8").splitlines()[-3000:]
            for line in lines:
                try:
                    item = json.loads(line)
                except Exception:
                    continue
                if isinstance(item, dict):
                    rows.append(item)
        except OSError:
            rows = []

    duplicate = bool(rows and str(rows[-1].get("ts")) == ts and str(rows[-1].get("symbol")) == row["symbol"])
    if not duplicate:
        rows.append(row)
    rows = rows[-3000:]
    try:
        path.write_text("\n".join(json.dumps(item, ensure_ascii=False, default=str) for item in rows) + "\n", encoding="utf-8")
    except OSError:
        pass
    active_rows = [item for item in rows if str(item.get("symbol", "")) == row["symbol"]]
    return active_rows[-500:]


def persist_live_snapshot(snapshot: dict[str, Any]) -> None:
    output_dir = get_user_output_dir()
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        recent_ticks = _append_realtime_tick(snapshot, output_dir)
        if recent_ticks:
            snapshot["recent_ticks"] = recent_ticks
        (output_dir / "sn_live_snapshot.json").write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
    except OSError:
        return

    articles = snapshot.get("articles", [])
    if isinstance(articles, list) and articles:
        try:
            pd.DataFrame(articles).to_csv(output_dir / "sn_live_articles.csv", index=False, encoding="utf-8-sig")
        except OSError:
            pass
        try:
            upsert_articles(articles, fetch_batch_id=str(snapshot.get("generated_at", "")))
        except Exception:
            pass
        try:
            ingest_articles(articles, batch_id=str(snapshot.get("generated_at", "")))
        except Exception:
            pass
    statuses = snapshot.get("source_status", [])
    if isinstance(statuses, list) and statuses:
        try:
            update_provider_status([row for row in statuses if isinstance(row, dict)])
        except Exception:
            pass
