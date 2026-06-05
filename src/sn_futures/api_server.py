from __future__ import annotations

import json
import math
import mimetypes
import os
import pickle
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from .api.terminal_api import handle_terminal_api
from .config import ProjectPaths
from .bootstrap.runtime_guard import runtime_status, write_runtime_state
from .services.process_lifecycle_service import mark_server_shutdown, write_server_runtime_files
from .market_data_hub import build_live_snapshot, persist_live_snapshot
from .prediction_history import build_walk_forward_baseline_from_predictions
from .runtime import resource_path
from .trading_calendar import sn_trading_session_state
from .v2_api import (
    evaluate_decision_policy,
    get_backtest_diagnostics,
    get_contract_liquidity,
    get_data_watermark,
    get_events_audit,
    get_events_evidence,
    get_events_provider_status,
    get_events_recent,
    evaluate_position_scenario_api,
    get_factors_diagnostics,
    get_hardware_profile,
    get_learning_status,
    get_live_predictions,
    get_market_history,
    get_market_latest,
    get_models_health,
    get_models_registry,
    get_model_promotion_report,
    get_news_events,
    get_news_open_url,
    get_news_policy_impact,
    get_open_source_inspirations,
    get_price_forecast_chart,
    get_prediction_by_id,
    get_predictions_history,
    get_report_content,
    get_reports_manifest,
    get_system_truth_audit,
    get_trading_session,
    get_ui_bootstrap,
    run_predict_api,
    run_experiment_stub,
)


TASKS: dict[str, dict[str, Any]] = {}
TASK_LOCK = threading.Lock()
SCHEDULER_LOCK = threading.Lock()
SCHEDULER_STARTED = False
SCHEDULER_STATE_FILE = "sn_scheduler_state.json"


def _sanitize_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _sanitize_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize_json(item) for item in value]
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if hasattr(value, "item"):
        try:
            return _sanitize_json(value.item())
        except Exception:
            return str(value)
    return value


def _json_bytes(payload: Any) -> bytes:
    return json.dumps(_sanitize_json(payload), ensure_ascii=False, indent=2, default=str, allow_nan=False).encode("utf-8")


def _web_root() -> Path:
    return resource_path("ui_web")


def _frontend_dist_root() -> Path:
    return resource_path("frontend", "dist")


def _legacy_root() -> Path:
    return _web_root()


def _static_mime_type(path: Path) -> str:
    suffix = path.suffix.lower()
    explicit = {
        ".html": "text/html; charset=utf-8",
        ".js": "application/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".json": "application/json; charset=utf-8",
        ".svg": "image/svg+xml",
        ".png": "image/png",
        ".ico": "image/x-icon",
        ".woff": "font/woff",
        ".woff2": "font/woff2",
    }
    if suffix in explicit:
        return explicit[suffix]
    mime = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    charset = "; charset=utf-8" if mime.startswith("text/") or mime in {"application/javascript", "application/json"} else ""
    return mime + charset


def _safe_static_target(root: Path, relative_url_path: str) -> Path | None:
    root_resolved = root.resolve()
    decoded = unquote(relative_url_path).replace("\\", "/").lstrip("/")
    parts = [part for part in decoded.split("/") if part and part != "."]
    if any(part == ".." for part in parts):
        return None
    target = root_resolved.joinpath(*parts).resolve()
    try:
        target.relative_to(root_resolved)
    except ValueError:
        return None
    return target


def _is_private_bundle_static_path(request_path: str) -> bool:
    text = unquote(request_path).replace("\\", "/").lower()
    blocked = (
        "/private/",
        "/_internal/private/",
        "private_bundle_seed.json",
    )
    return any(item in text for item in blocked)


def _terminal_missing_build_page() -> str:
    return """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>SNInsightTerminal 专业终端尚未构建</title>
  <style>
    body{margin:0;min-height:100vh;display:grid;place-items:center;background:#07111f;color:#e6edf7;font-family:"Microsoft YaHei",sans-serif}
    main{max-width:760px;padding:36px;border:1px solid #1d314d;border-radius:24px;background:#0c1828;box-shadow:0 20px 70px rgba(0,0,0,.35)}
    h1{margin-top:0} code{color:#f7c948}.links{display:grid;gap:10px;margin-top:20px}a{color:#66d9ef}
  </style>
</head>
<body>
  <main>
    <h1>专业前端尚未构建</h1>
    <p>专业前端尚未构建，请先进入 <code>frontend</code> 目录运行 <code>npm install</code> 和 <code>npm run build</code>。</p>
    <ul>
      <li>后端 API 已启动。</li>
      <li>新终端构建状态：未构建。</li>
      <li>构建完成后可通过 <code>/terminal</code> 访问新专业终端。</li>
    </ul>
    <div class="links">
      <a href="/api/terminal/docs">查看 Terminal API 文档</a>
      <a href="/legacy">使用旧版终端</a>
    </div>
  </main>
</body>
</html>"""


def _worker_command(payload_path: Path, result_path: Path) -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, "--live-worker", str(payload_path), str(result_path)]
    return [sys.executable, str(resource_path("app_launcher.py")), "--live-worker", str(payload_path), str(result_path)]


def _finish_task(task_id: str, **fields: Any) -> None:
    with TASK_LOCK:
        TASKS[task_id].update(fields)


def _scheduler_state_path() -> Path:
    return ProjectPaths().output_dir / SCHEDULER_STATE_FILE


def _read_scheduler_state() -> dict[str, Any]:
    path = _scheduler_state_path()
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_scheduler_state(**updates: Any) -> None:
    state = _read_scheduler_state()
    state.update(
        {
            "auto_scheduler_enabled": True,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "rate_limit_state": "稳健高频：交易时段行情15秒轻刷新，完整预测约4分钟；非交易时段自动降频，验证/校准30分钟，训练收盘后执行。",
        }
    )
    state.update(updates)
    path = _scheduler_state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _has_running_task() -> bool:
    with TASK_LOCK:
        return any(task.get("status") in {"queued", "running"} for task in TASKS.values())


def _submit_background_task(task_type: str, payload: dict[str, Any] | None = None) -> str:
    payload = payload or {}
    task_id = uuid.uuid4().hex[:12]
    record = {
        "id": task_id,
        "type": task_type,
        "status": "queued",
        "stage": "后台调度排队",
        "progress": 0.0,
        "created_at": time.time(),
        "can_cancel": False,
    }
    with TASK_LOCK:
        TASKS[task_id] = record
    thread = threading.Thread(target=_task_worker, args=(task_id, task_type, payload), daemon=True)
    thread.start()
    return task_id


def _run_light_validation_task(task_id: str, task_type: str) -> None:
    paths = ProjectPaths()
    _finish_task(task_id, status="running", stage="重建历史验证基线", progress=0.35, started_at=time.time())
    baseline = build_walk_forward_baseline_from_predictions(paths.output_dir, force=task_type == "backtest")
    health = get_models_health()
    _write_scheduler_state(last_verification=datetime.now().isoformat(timespec="seconds"))
    _finish_task(
        task_id,
        status="completed",
        stage="完成",
        progress=1.0,
        finished_at=time.time(),
        summary={
            "baseline_rows": int(len(baseline)),
            "validation_mode": health.get("validation_mode"),
            "direction_sample_count": health.get("direction_sample_count"),
            "direction_hit_rate": health.get("direction_hit_rate"),
        },
    )


def _run_model_governance_task(task_id: str, task_type: str, payload: dict[str, Any]) -> None:
    horizon = str(payload.get("horizon", "tomorrow"))
    _finish_task(task_id, status="running", stage="方向优先候选模型治理检查", progress=0.35, started_at=time.time())
    report = get_model_promotion_report(horizon)
    now_text = datetime.now().isoformat(timespec="seconds")
    updates = {"last_model_governance": now_text}
    if task_type == "walk_forward":
        updates["last_walk_forward"] = now_text
    elif task_type == "event_ablation":
        updates["last_event_ablation"] = now_text
    elif task_type == "train_candidate":
        updates["last_training"] = now_text
    _write_scheduler_state(**updates)
    _finish_task(
        task_id,
        status="completed",
        stage="候选模型治理检查完成",
        progress=1.0,
        finished_at=time.time(),
        summary={
            "task_type": task_type,
            "horizon": horizon,
            "promotion_result": report.get("promotion_result"),
            "candidate_status": report.get("candidate_status"),
            "missing_metrics": report.get("missing_metrics", []),
            "note": "未通过真实 walk-forward / 事件消融 / 概率校准前，candidate 不会替换 active。",
        },
    )


def _run_gpu_smoke_test(task_id: str) -> None:
    _finish_task(task_id, status="running", stage="检测 CUDA Torch", progress=0.35, started_at=time.time())
    import torch  # type: ignore

    available = bool(torch.cuda.is_available())
    device = torch.device("cuda:0" if available else "cpu")
    x = torch.randn((512, 512), device=device)
    y = torch.mm(x, x)
    if available:
        torch.cuda.synchronize()
    _finish_task(
        task_id,
        status="completed",
        stage="完成",
        progress=1.0,
        finished_at=time.time(),
        summary={
            "torch": str(torch.__version__),
            "cuda_available": available,
            "device": str(device),
            "device_name": torch.cuda.get_device_name(0) if available else "CPU",
            "checksum": float(y.detach().cpu().mean().item()),
        },
    )


def _run_quote_refresh_task(task_id: str) -> None:
    _finish_task(task_id, status="running", stage="刷新实时行情快照", progress=0.35, started_at=time.time())
    snapshot = build_live_snapshot(raw=None, use_remote=True)
    persist_live_snapshot(snapshot)
    quotes = snapshot.get("quotes", []) if isinstance(snapshot.get("quotes"), list) else []
    meta = snapshot.get("contract_meta", {}) if isinstance(snapshot.get("contract_meta"), dict) else {}
    _write_scheduler_state(last_market_refresh=datetime.now().isoformat(timespec="seconds"))
    _finish_task(
        task_id,
        status="completed",
        stage="行情轻刷新完成",
        progress=1.0,
        finished_at=time.time(),
        summary={
            "quote_count": len(quotes),
            "active_contract": meta.get("active_contract", meta.get("target_contract", "SN")),
            "generated_at": snapshot.get("generated_at", ""),
        },
    )


def _run_news_refresh_task(task_id: str) -> None:
    _finish_task(task_id, status="running", stage="刷新新闻政策缓存", progress=0.30, started_at=time.time())
    snapshot = build_live_snapshot(raw=None, use_remote=True)
    persist_live_snapshot(snapshot)
    articles = snapshot.get("articles", []) if isinstance(snapshot.get("articles"), list) else []
    statuses = snapshot.get("source_status", []) if isinstance(snapshot.get("source_status"), list) else []
    now_text = datetime.now().isoformat(timespec="seconds")
    _write_scheduler_state(last_news_refresh=now_text)
    _finish_task(
        task_id,
        status="completed",
        stage="新闻政策刷新完成",
        progress=1.0,
        finished_at=time.time(),
        summary={
            "article_count": len(articles),
            "source_status": statuses,
            "generated_at": snapshot.get("generated_at", ""),
        },
    )


def _run_worker_task(task_id: str, payload: dict[str, Any]) -> None:
    paths = ProjectPaths()
    runtime_dir = paths.user_data_dir / "_runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    payload_path = runtime_dir / f"api_worker_payload_{task_id}.json"
    result_path = runtime_dir / f"api_worker_result_{task_id}.pkl"
    worker_payload = {
        "refresh_scope": str(payload.get("refresh_scope", "all")),
        "use_remote": bool(payload.get("use_remote", True)),
        "use_demo": False,
        "csv_path": payload.get("csv_path"),
        "optimization_level": str(payload.get("optimization_level", "auto")),
    }
    payload_path.write_text(json.dumps(worker_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _finish_task(task_id, stage="启动独立预测 worker", progress=0.18)

    timeout_seconds = int(payload.get("timeout_seconds", 360) or 360)
    process = subprocess.Popen(_worker_command(payload_path, result_path), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.time() + timeout_seconds
    while process.poll() is None:
        if time.time() > deadline:
            process.kill()
            raise TimeoutError(f"后台预测任务超过 {timeout_seconds} 秒未完成，已自动释放任务锁。")
        started_at = TASKS.get(task_id, {}).get("started_at", time.time())
        elapsed = max(0.0, time.time() - float(started_at))
        progress = min(0.88, 0.18 + elapsed / max(timeout_seconds, 1) * 0.7)
        _finish_task(task_id, stage="刷新真实数据并生成预测", progress=round(progress, 3))
        time.sleep(0.8)

    _finish_task(task_id, stage="读取预测结果", progress=0.92)
    if process.returncode != 0:
        raise RuntimeError(f"后台预测 worker 退出码异常：{process.returncode}")
    if not result_path.exists():
        raise RuntimeError("后台预测 worker 未生成结果文件。")
    with result_path.open("rb") as fh:
        result = pickle.load(fh)
    if not result.get("ok"):
        raise RuntimeError(str(result.get("error", "后台预测任务失败")))
    data = result.get("result", {}) if isinstance(result, dict) else {}
    raw = data.get("raw") if isinstance(data, dict) else None
    latest_daily = str(raw.index[-1].date()) if hasattr(raw, "index") and len(raw.index) else ""
    health = get_models_health()
    now_text = datetime.now().isoformat(timespec="seconds")
    task_type = str(payload.get("task_type", "refresh_prediction"))
    scheduler_updates = {"last_prediction_refresh": now_text}
    if task_type == "retrain":
        scheduler_updates["last_training"] = now_text
    _write_scheduler_state(**scheduler_updates)
    _finish_task(
        task_id,
        status="completed",
        stage="完成",
        progress=1.0,
        finished_at=time.time(),
        summary={"latest_daily": latest_daily, "model_health": health},
    )


def _task_worker(task_id: str, task_type: str, payload: dict[str, Any]) -> None:
    _finish_task(task_id, status="running", stage="初始化", started_at=time.time(), progress=0.05)
    try:
        if task_type not in {"refresh", "refresh_news", "refresh_quotes", "refresh_prediction", "verify", "calibrate", "retrain", "backtest", "report", "gpu_smoke_test", "train_candidate", "walk_forward", "event_ablation", "promotion_check", "position_scenario_refresh"}:
            _finish_task(task_id, status="completed", stage="无需执行", progress=1.0, finished_at=time.time())
            return
        if task_type == "position_scenario_refresh":
            _finish_task(
                task_id,
                status="completed",
                stage="持仓情景已刷新",
                progress=1.0,
                finished_at=time.time(),
                summary={"note": "持仓情景由前端输入实时计算，不生成交易指令。"},
            )
            return
        if task_type == "refresh_quotes":
            _run_quote_refresh_task(task_id)
            return
        if task_type == "refresh_news":
            _run_news_refresh_task(task_id)
            return
        if task_type == "gpu_smoke_test":
            _run_gpu_smoke_test(task_id)
            return
        if task_type in {"verify", "calibrate", "backtest"}:
            _run_light_validation_task(task_id, task_type)
            return
        if task_type in {"train_candidate", "walk_forward", "event_ablation", "promotion_check"}:
            _run_model_governance_task(task_id, task_type, payload)
            return
        payload = dict(payload)
        payload["task_type"] = task_type
        _run_worker_task(task_id, payload)
    except Exception as exc:
        _finish_task(task_id, status="failed", stage="失败", error=str(exc), finished_at=time.time(), progress=1.0)


def _next_close_training_time(now: datetime) -> datetime:
    target = now.replace(hour=15, minute=20, second=0, microsecond=0)
    if now >= target:
        target = target + timedelta(days=1)
    while target.weekday() >= 5:
        target = target + timedelta(days=1)
    return target


def _scheduler_loop() -> None:
    next_market = datetime.now()
    next_news = datetime.now() + timedelta(seconds=40)
    next_prediction = datetime.now() + timedelta(seconds=20)
    next_verification = datetime.now() + timedelta(minutes=2)
    next_training = _next_close_training_time(datetime.now())
    _write_scheduler_state(
        next_prediction_at=next_prediction.isoformat(timespec="seconds"),
        next_training_at=next_training.isoformat(timespec="seconds"),
    )
    while True:
        try:
            now = datetime.now()
            session = sn_trading_session_state()
            is_trading = bool(session.get("is_trading"))
            market_interval = timedelta(seconds=15 if is_trading else 300)
            news_interval = timedelta(minutes=5 if is_trading else 30)
            prediction_interval = timedelta(minutes=4 if is_trading else 30)
            if now >= next_market:
                if not _has_running_task():
                    _submit_background_task("refresh_quotes", {"source": "auto_scheduler"})
                else:
                    _write_scheduler_state(last_market_refresh=now.isoformat(timespec="seconds"))
                next_market = now + market_interval
            if not _has_running_task() and now >= next_news:
                _submit_background_task("refresh_news", {"source": "auto_scheduler"})
                next_news = now + news_interval
                _write_scheduler_state(
                    last_news_refresh=now.isoformat(timespec="seconds"),
                    next_news_refresh_at=next_news.isoformat(timespec="seconds"),
                )
            if not _has_running_task() and now >= next_verification:
                _submit_background_task("verify", {"source": "auto_scheduler"})
                next_verification = now + timedelta(minutes=30)
                _write_scheduler_state(last_verification=now.isoformat(timespec="seconds"))
            if not _has_running_task() and now >= next_prediction:
                _submit_background_task(
                    "refresh_prediction",
                    {
                        "source": "auto_scheduler",
                        "refresh_scope": "all",
                        "optimization_level": "auto",
                        "use_remote": True,
                        "timeout_seconds": 420,
                    },
                )
                next_prediction = now + prediction_interval
                _write_scheduler_state(
                    last_prediction_refresh=now.isoformat(timespec="seconds"),
                    next_prediction_at=next_prediction.isoformat(timespec="seconds"),
                    rate_limit_state=(
                        "交易时段：行情15秒轻刷新，完整预测约4分钟；新闻/宏观仍按免费API限频。"
                        if is_trading
                        else "非交易时段：行情5分钟轻刷新，完整预测降频，开盘前/收盘后优先。"
                    ),
                )
            if not _has_running_task() and now >= next_training:
                _submit_background_task(
                    "retrain",
                    {
                        "source": "auto_scheduler",
                        "refresh_scope": "all",
                        "optimization_level": "auto",
                        "use_remote": True,
                        "timeout_seconds": 900,
                    },
                )
                next_training = _next_close_training_time(now + timedelta(minutes=1))
                _write_scheduler_state(next_training_at=next_training.isoformat(timespec="seconds"))
        except Exception as exc:
            _write_scheduler_state(rate_limit_state=f"自动调度器异常，已保留上次成功结果：{exc}")
        time.sleep(20)


def start_scheduler_once() -> None:
    global SCHEDULER_STARTED
    with SCHEDULER_LOCK:
        if SCHEDULER_STARTED:
            return
        SCHEDULER_STARTED = True
    thread = threading.Thread(target=_scheduler_loop, name="sn-auto-scheduler", daemon=True)
    thread.start()


class V2ApiHandler(BaseHTTPRequestHandler):
    server_version = "SNInsightV2API/1.1"

    @staticmethod
    def _is_client_disconnect(exc: OSError) -> bool:
        return isinstance(exc, (BrokenPipeError, ConnectionAbortedError, ConnectionResetError)) or getattr(
            exc, "winerror", None
        ) in {10053, 10054}

    def _send_bytes(self, status: int, content_type: str, body: bytes) -> None:
        try:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except OSError as exc:
            if self._is_client_disconnect(exc):
                return
            raise

    def _send(self, status: int, payload: Any) -> None:
        self._send_bytes(status, "application/json; charset=utf-8", _json_bytes(payload))

    def _send_file(self, path: Path) -> None:
        if not path.exists() or not path.is_file():
            self._send(404, {"error": "not_found", "path": str(path)})
            return
        body = path.read_bytes()
        mime = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        charset = "; charset=utf-8" if mime.startswith("text/") or mime in {"application/javascript", "application/json"} else ""
        self._send_bytes(200, mime + charset, body)

    def _send_static_file(self, path: Path) -> None:
        body = path.read_bytes()
        self._send_bytes(200, _static_mime_type(path), body)

    def _send_html(self, status: int, html: str) -> None:
        body = html.encode("utf-8")
        self._send_bytes(status, "text/html; charset=utf-8", body)

    def _send_terminal_static(self, request_path: str) -> None:
        root = _frontend_dist_root()
        index = root / "index.html"
        if not index.exists():
            self._send_html(200, _terminal_missing_build_page())
            return
        relative = request_path[len("/terminal") :].lstrip("/")
        if not relative:
            self._send_static_file(index)
            return
        target = _safe_static_target(root, relative)
        if target is None:
            self._send(403, {"error": "forbidden", "message": "静态资源路径不合法"})
            return
        if target.exists() and target.is_file():
            self._send_static_file(target)
            return
        self._send_static_file(index)

    def _send_legacy_static(self, request_path: str) -> None:
        root = _legacy_root()
        relative = "index.html" if request_path in {"/legacy", "/legacy/"} else request_path[len("/legacy") :].lstrip("/")
        target = _safe_static_target(root, relative)
        if target is None:
            self._send(403, {"error": "forbidden", "message": "静态资源路径不合法"})
            return
        if target.exists() and target.is_file():
            self._send_static_file(target)
            return
        self._send(404, {"error": "not_found", "message": "旧版终端资源不存在"})

    def log_message(self, _format: str, *_args: Any) -> None:  # noqa: N802
        return

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        try:
            if _is_private_bundle_static_path(parsed.path):
                self._send(404, {"error": "not_found", "message": "静态资源不存在。"})
                return
            if parsed.path.startswith("/api/terminal/"):
                status, payload = handle_terminal_api(parsed.path, "GET", query, None)
                self._send(status, payload)
            elif parsed.path == "/api/open_source/inspirations":
                self._send(200, get_open_source_inspirations())
            elif parsed.path == "/api/ui/bootstrap":
                self._send(200, get_ui_bootstrap())
            elif parsed.path == "/api/predictions/live":
                self._send(200, get_live_predictions())
            elif parsed.path == "/api/market/latest":
                self._send(
                    200,
                    get_market_latest(
                        symbol=query.get("symbol", ["SN"])[0],
                        contract_type=query.get("contract_type", ["main"])[0],
                        force_refresh=query.get("force_refresh", ["0"])[0].lower() in {"1", "true", "yes"},
                    ),
                )
            elif parsed.path == "/api/market/history":
                self._send(
                    200,
                    get_market_history(
                        symbol=query.get("symbol", ["SN"])[0],
                        horizon=query.get("horizon", ["tomorrow"])[0],
                        contract_type=query.get("contract_type", ["main"])[0],
                        start=query.get("start", [None])[0],
                        end=query.get("end", [None])[0],
                    ),
                )
            elif parsed.path == "/api/predict":
                self._send(
                    200,
                    run_predict_api(
                        symbol=query.get("symbol", ["SN"])[0],
                        horizon=query.get("horizon", ["tomorrow"])[0],
                        contract_type=query.get("contract_type", ["main"])[0],
                        force_refresh=query.get("force_refresh", ["0"])[0].lower() in {"1", "true", "yes"},
                    ),
                )
            elif parsed.path == "/api/news/policy-impact":
                self._send(200, get_news_policy_impact())
            elif parsed.path == "/api/news":
                self._send(
                    200,
                    get_news_events(
                        symbol=query.get("symbol", ["SN"])[0],
                        limit=int(query.get("limit", ["20"])[0] or 20),
                        category=query.get("category", [""])[0],
                        min_impact_score=float(query.get("min_impact_score", ["0"])[0] or 0),
                    ),
                )
            elif parsed.path == "/api/news/open":
                self._send(200, get_news_open_url(query.get("event_id", [""])[0]))
            elif parsed.path == "/api/events/open":
                self._send(200, get_news_open_url(query.get("event_id", [""])[0]))
            elif parsed.path == "/api/events/recent":
                self._send(
                    200,
                    get_events_recent(
                        symbol=query.get("symbol", ["SN"])[0],
                        limit=int(query.get("limit", ["50"])[0] or 50),
                        category=query.get("category", [""])[0],
                        min_impact_score=float(query.get("min_impact_score", ["0"])[0] or 0),
                    ),
                )
            elif parsed.path == "/api/events/evidence":
                self._send(200, get_events_evidence(query.get("horizon", ["tomorrow"])[0]))
            elif parsed.path == "/api/events/provider-status":
                self._send(200, get_events_provider_status())
            elif parsed.path == "/api/events/audit":
                self._send(200, get_events_audit(query.get("horizon", ["tomorrow"])[0]))
            elif parsed.path == "/api/trading/session":
                self._send(200, get_trading_session())
            elif parsed.path == "/api/charts/price-forecast":
                self._send(200, get_price_forecast_chart(query.get("horizon", ["tomorrow"])[0]))
            elif parsed.path == "/api/backtest/diagnostics":
                self._send(200, get_backtest_diagnostics(query.get("horizon", [""])[0]))
            elif parsed.path == "/api/contracts/liquidity":
                self._send(200, get_contract_liquidity())
            elif parsed.path == "/api/hardware/profile":
                self._send(200, get_hardware_profile())
            elif parsed.path == "/api/learning/status":
                self._send(200, get_learning_status())
            elif parsed.path == "/api/reports/manifest":
                self._send(200, get_reports_manifest())
            elif parsed.path == "/api/reports/content":
                self._send(200, get_report_content(query.get("type", ["daily"])[0]))
            elif parsed.path == "/api/report/preview":
                self._send(200, get_report_content(query.get("type", ["daily"])[0]))
            elif parsed.path == "/api/report/export":
                payload = get_report_content(query.get("type", ["daily"])[0])
                payload["format"] = query.get("format", ["html"])[0]
                payload["export_note"] = "当前接口返回可打印 HTML/Markdown 内容；PDF 导出由前端打印或后续 Playwright 打包任务生成。"
                self._send(200, payload)
            elif parsed.path == "/api/models/registry":
                self._send(200, get_models_registry())
            elif parsed.path == "/api/models/health":
                self._send(200, get_models_health())
            elif parsed.path == "/api/model/promotion-report":
                self._send(200, get_model_promotion_report(query.get("horizon", ["tomorrow"])[0]))
            elif parsed.path == "/api/factors/diagnostics":
                self._send(200, get_factors_diagnostics())
            elif parsed.path in {"/api/diagnostics/truth-audit", "/api/diagnostics/system-truth"}:
                self._send(200, get_system_truth_audit())
            elif parsed.path == "/api/predictions/history":
                self._send(200, get_predictions_history(query.get("status", ["verified"])[0]))
            elif parsed.path.startswith("/api/predictions/"):
                prediction_id = parsed.path.rsplit("/", 1)[-1]
                self._send(200, get_prediction_by_id(prediction_id))
            elif parsed.path == "/api/data/watermark":
                self._send(200, get_data_watermark())
            elif parsed.path == "/api/runtime/status":
                self._send(200, runtime_status())
            elif parsed.path == "/api/tasks/status":
                task_id = query.get("id", [""])[0]
                with TASK_LOCK:
                    payload = TASKS.get(task_id, {"status": "not_found", "id": task_id})
                self._send(200, payload)
            elif parsed.path in {"/terminal", "/terminal/"} or parsed.path.startswith("/terminal/"):
                self._send_terminal_static(parsed.path)
            elif parsed.path in {"/legacy", "/legacy/"} or parsed.path.startswith("/legacy/"):
                self._send_legacy_static(parsed.path)
            else:
                requested = "index.html" if parsed.path == "/" else parsed.path.lstrip("/")
                root = _web_root().resolve()
                target = (root / requested).resolve()
                if str(target).startswith(str(root)):
                    self._send_file(target)
                else:
                    self._send(404, {"error": "not_found", "path": parsed.path})
        except Exception as exc:
            self._send(500, {"error": "internal_error", "message": str(exc)})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        if parsed.path.startswith("/api/terminal/"):
            query = parse_qs(parsed.query)
            try:
                status, payload = handle_terminal_api(parsed.path, "POST", query, raw)
                self._send(status, payload)
                if parsed.path == "/api/terminal/system/shutdown" and status == 200:
                    threading.Thread(target=self.server.shutdown, name="sn-http-shutdown", daemon=True).start()
            except Exception as exc:
                self._send(500, {"error": "internal_error", "message": str(exc)})
            return
        try:
            payload = json.loads(raw) if raw.strip() else {}
        except Exception:
            payload = {}
        try:
            if parsed.path == "/api/decision_policy/evaluate":
                self._send(200, evaluate_decision_policy())
            elif parsed.path == "/api/predict":
                self._send(
                    200,
                    run_predict_api(
                        symbol=str(payload.get("symbol", "SN")),
                        horizon=str(payload.get("horizon", "tomorrow")),
                        contract_type=str(payload.get("contract_type", "main")),
                        force_refresh=bool(payload.get("force_refresh", False)),
                    ),
                )
            elif parsed.path == "/api/tasks/run":
                task_id = uuid.uuid4().hex[:12]
                task_type = str(payload.get("type", "refresh"))
                record = {
                    "id": task_id,
                    "type": task_type,
                    "status": "queued",
                    "stage": "排队中",
                    "progress": 0.0,
                    "created_at": time.time(),
                    "can_cancel": False,
                }
                with TASK_LOCK:
                    TASKS[task_id] = record
                thread = threading.Thread(target=_task_worker, args=(task_id, task_type, payload), daemon=True)
                thread.start()
                self._send(202, record)
            elif parsed.path == "/api/position/scenario":
                self._send(200, evaluate_position_scenario_api(payload))
            elif parsed.path == "/api/events/open":
                self._send(200, get_news_open_url(str(payload.get("event_id", ""))))
            elif parsed.path == "/api/experiments/run":
                self._send(
                    202,
                    run_experiment_stub(
                        model_type=str(payload.get("model_type", "direction_first_stacking_pool")),
                        horizon=str(payload.get("horizon", "tomorrow")),
                        train_window=int(payload.get("train_window", 126) or 126),
                        compute_profile=str(payload.get("compute_profile", "fast")),
                    ),
                )
            else:
                self._send(404, {"error": "not_found", "path": parsed.path})
        except Exception as exc:
            self._send(500, {"error": "internal_error", "message": str(exc)})


def run_api_server(host: str = "127.0.0.1", port: int = 8765) -> None:
    env_port = os.environ.get("SN_TERMINAL_API_PORT")
    if env_port:
        try:
            port = int(env_port)
        except ValueError:
            port = 8765
    server = ThreadingHTTPServer((host, port), V2ApiHandler)
    write_runtime_state(api_port=port, frontend_port=port, message="本地 API 服务已启动")
    write_server_runtime_files(host=host, port=port)
    if os.environ.get("SN_DISABLE_AUTO_SCHEDULER", "").lower() not in {"1", "true", "yes"}:
        start_scheduler_once()
    try:
        server.serve_forever()
    finally:
        try:
            server.server_close()
        finally:
            mark_server_shutdown(reason="server_exit")


def main(argv: list[str] | None = None) -> None:
    args = list(sys.argv[1:] if argv is None else argv)
    host = "127.0.0.1"
    port = 8765
    if "--host" in args:
        index = args.index("--host")
        if index + 1 < len(args):
            host = args[index + 1]
    for flag in ("--api-port", "--port"):
        if flag in args:
            index = args.index(flag)
            if index + 1 < len(args):
                os.environ["SN_TERMINAL_API_PORT"] = args[index + 1]
                try:
                    port = int(args[index + 1])
                except ValueError:
                    port = 8765
                break
    run_api_server(host=host, port=port)


if __name__ == "__main__":
    main()
