from __future__ import annotations

import json
import os
import pickle
import shutil
import subprocess
import sys
import traceback
import warnings
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path
from queue import Empty, Queue
from threading import Thread

import pandas as pd
import tkinter as tk
from tkinter import filedialog, ttk

from .api_server import run_api_server
from .api_clients import test_alpha_vantage_key, test_newsapi_key
from .config import AppSettings, ProjectPaths, available_presets, available_risk_profiles, get_preset, get_risk_profile
from .local_assistant import answer_question
from .pipeline import run_live_prediction_pipeline, run_pipeline
from .prediction_history import load_prediction_history, model_memory_path, prediction_evaluation_path
from .research_v2 import load_v2_artifacts
from .reporting import build_prediction_detail_report
from .runtime import APP_NAME, get_bundled_docs, get_user_output_dir
from .scenario import build_position_risk_snapshot, build_scenario_matrix
from .settings_store import (
    create_backup,
    list_backups,
    load_api_keys,
    load_settings,
    missing_api_keys,
    save_api_keys,
    save_settings,
)
from .text_tables import dataframe_to_text
from .worker_entry import run_live_worker_from_argv


warnings.filterwarnings("ignore")

LIGHT = {
    "bg": "#F5F7FA",
    "panel": "#FFFFFF",
    "side": "#E9EDF5",
    "text": "#1D2129",
    "muted": "#4E5969",
    "primary": "#165DFF",
    "bull": "#FDEEEE",
    "bear": "#E9F8EC",
    "neutral": "#F2F3F5",
}
DARK = {
    "bg": "#121212",
    "panel": "#1B1F24",
    "side": "#171A1F",
    "text": "#F2F3F5",
    "muted": "#B6BEC9",
    "primary": "#4C8DFF",
    "bull": "#3A2020",
    "bear": "#17311F",
    "neutral": "#22252B",
}
DISPLAY_NAME = "沪锡期货预测预警终端"
DISCLAIMER = "本软件仅用于沪锡期货量化投研。预测、信号、报告与回测结果仅供研究参考，不构成任何投资建议。"
COMPLIANCE_SMALL = "本内容仅为期货投研参考，不构成任何投资建议，期货交易有风险，投资需谨慎。"
HORIZON_ORDER = [
    ("next_5m", "5分钟"),
    ("next_15m", "15分钟"),
    ("next_30m", "30分钟"),
    ("next_hour", "下一小时"),
    ("tomorrow", "下一个交易日"),
    ("one_to_two_weeks", "未来1-2周"),
    ("one_to_three_months", "未来1-3个月"),
]
CRITICAL_FREE_SPACE_MB = 64
LOW_FREE_SPACE_MB = 512


class SNInsightTerminal(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.paths = ProjectPaths()
        self.settings = load_settings()
        self.api_keys = load_api_keys()
        self.output_dir = get_user_output_dir()
        self.doc_paths = get_bundled_docs()

        self.current_result: dict[str, object] | None = None
        self.current_csv_path: str | None = None
        self.current_live_snapshot: dict[str, object] | None = None
        self.current_live_predictions: dict[str, object] | None = None
        self.current_scenario_matrix = pd.DataFrame()
        self.current_position_risk: dict[str, float] = {}
        self.current_optimization_summary: dict[str, object] | None = None
        self.current_bandit_summary: dict[str, object] | None = None
        self.current_prediction_history = pd.DataFrame()
        self.current_prediction_evaluation = pd.DataFrame()
        self.current_prediction_evaluation_summary: dict[str, object] | None = None
        self.current_calibration_profile: dict[str, object] | None = None
        self.current_backtest_diagnostics: dict[str, object] | None = None
        self.current_model_memory: dict[str, object] | None = None
        self.current_v2_artifacts: dict[str, object] | None = None
        self.report_manifest: list[dict[str, str]] = []

        self.queue: Queue[tuple[str, object]] = Queue()
        self.pipeline_busy = False
        self.pipeline_process: subprocess.Popen[str] | None = None
        self.pipeline_payload_path: Path | None = None
        self.pipeline_result_path: Path | None = None
        self.pipeline_existing_path: Path | None = None
        self.pipeline_started_at: datetime | None = None
        self.pipeline_timeout_seconds: int = 0
        self.startup_modal: tk.Toplevel | None = None
        self.generic_modal: tk.Toplevel | None = None
        self.short_refresh_job: str | None = None
        self.daily_refresh_job: str | None = None
        self.api_server_started = False
        self.web_terminal_opened = False

        self.title(DISPLAY_NAME)
        self.geometry("1440x900")
        self.minsize(980, 700)
        self.protocol("WM_DELETE_WINDOW", self._shutdown_app)

        self.theme_var = tk.StringVar(value=self.settings.theme)
        self.mode_var = tk.StringVar(value=self.settings.user_mode)
        self.preset_var = tk.StringVar(value=self.settings.selected_preset)
        self.profile_var = tk.StringVar(value=self.settings.selected_risk_profile)
        self.compute_profile_var = tk.StringVar(value=self.settings.compute_profile)
        self.report_type_var = tk.StringVar(value=self.settings.default_report_type)
        self.live_enabled_var = tk.BooleanVar(value=self.settings.live_data_enabled)
        self.cache_only_var = tk.BooleanVar(value=self.settings.cache_only_mode)
        self.auto_backup_var = tk.BooleanVar(value=self.settings.auto_backup)
        self.qna_enabled_var = tk.BooleanVar(value=self.settings.qna_enabled)
        self.voice_alerts_var = tk.BooleanVar(value=self.settings.voice_alerts)
        self.font_scale_var = tk.IntVar(value=self.settings.font_scale)
        self.stress_contracts_var = tk.IntVar(value=self.settings.stress_test_contracts)
        self.refresh_minutes_var = tk.IntVar(value=max(10, int(self.settings.live_refresh_seconds // 60)))
        self.preset_detail_var = tk.StringVar(value="")
        self.profile_detail_var = tk.StringVar(value="")
        self.compute_detail_var = tk.StringVar(value="")

        self.alpha_key_var = tk.StringVar(value=self.api_keys.get("SN_ALPHA_VANTAGE_KEY", ""))
        self.news_key_var = tk.StringVar(value=self.api_keys.get("SN_NEWSAPI_KEY", ""))
        self.show_alpha_var = tk.BooleanVar(value=False)
        self.show_news_var = tk.BooleanVar(value=False)
        self.api_status_var = tk.StringVar(value="API 状态：尚未测试")

        self.status_var = tk.StringVar(value="系统已就绪。完成 API 配置后将自动刷新实时预测。")
        self.summary_var = tk.StringVar(value="最新预测：尚未加载")
        self.regime_var = tk.StringVar(value="市场状态：尚未加载")
        self.risk_var = tk.StringVar(value="风险快照：尚未加载")
        self.signal_var = tk.StringVar(value="信号快照：尚未加载")

        self.model_var = tk.StringVar(value="模型状态：待刷新")
        self.data_var = tk.StringVar(value="数据链路：尚未加载")

        self.forecast_vars = {
            key: {
                "confidence": tk.StringVar(value="置信度：--"),
                "target": tk.StringVar(value="目标窗口：--"),
                "range": tk.StringVar(value="价格区间：--"),
                "prob": tk.StringVar(value="上涨：-- | 下跌：--"),
                "driver": tk.StringVar(value="核心驱动：尚未加载"),
            }
            for key, _ in HORIZON_ORDER
        }

        self.forecast_cards: dict[str, dict[str, object]] = {}
        self.views: dict[str, ttk.Frame] = {}
        self.nav_buttons: dict[str, ttk.Button] = {}

        self._configure_style()
        self._build_shell()
        self._apply_theme()
        self._load_existing_outputs()
        self._apply_mode()
        self._refresh_settings_text()

        self.after(200, self._poll_queue)
        self.after(260, self._ensure_api_server)
        self.after(350, self._startup_sequence)
        self.after(1400, self._open_web_terminal_once)

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Hero.TLabel", font=("Microsoft YaHei UI", 18, "bold"))
        style.configure("Metric.TLabel", font=("Microsoft YaHei UI", 11, "bold"))
        style.configure("Muted.TLabel", font=("Microsoft YaHei UI", 9))
        style.configure("App.TButton", font=("Microsoft YaHei UI", 10, "bold"), padding=8)
        style.configure("Section.TLabel", font=("Microsoft YaHei UI", 12, "bold"))

    def _build_shell(self) -> None:
        root = ttk.Frame(self)
        root.pack(fill="both", expand=True)

        header = ttk.Frame(root, padding=(14, 14, 14, 10))
        header.pack(fill="x")
        ttk.Label(header, text=DISPLAY_NAME, style="Hero.TLabel").pack(side="left")
        ttk.Label(header, text=DISCLAIMER, style="Muted.TLabel", wraplength=920, justify="left").pack(side="left", padx=(16, 0))

        toolbar = ttk.Frame(root, padding=(14, 0, 14, 10))
        toolbar.pack(fill="x")
        for label, command in (
            ("运行演示数据", self._run_demo),
            ("导入CSV", self._run_csv),
            ("刷新实时预测", self._manual_full_refresh),
            ("打开专业Web终端", self._open_web_terminal),
            ("生成报告", self._load_reports),
            ("重跑当前回测", self._rerun_current),
            ("运行压力测试", self._run_stress_test),
            ("切换最优参数", self._switch_best_preset),
            ("备份数据", self._backup_data),
            ("盯盘模式", self._toggle_focus),
        ):
            ttk.Button(toolbar, text=label, command=command, style="App.TButton").pack(side="left", padx=(0, 8))

        ttk.Label(toolbar, text="模式").pack(side="right", padx=(8, 4))
        mode_combo = ttk.Combobox(toolbar, textvariable=self.mode_var, values=["ordinary", "professional"], width=11, state="readonly")
        mode_combo.pack(side="right")
        mode_combo.bind("<<ComboboxSelected>>", lambda _e: self._save_ui_settings())

        ttk.Label(toolbar, text="主题").pack(side="right", padx=(8, 4))
        theme_combo = ttk.Combobox(toolbar, textvariable=self.theme_var, values=["light", "dark"], width=8, state="readonly")
        theme_combo.pack(side="right")
        theme_combo.bind("<<ComboboxSelected>>", lambda _e: self._save_ui_settings())

        ttk.Label(toolbar, text="风险").pack(side="right", padx=(8, 4))
        profile_combo = ttk.Combobox(toolbar, textvariable=self.profile_var, values=[p.key for p in available_risk_profiles()], width=12, state="readonly")
        profile_combo.pack(side="right")
        profile_combo.bind("<<ComboboxSelected>>", lambda _e: self._save_ui_settings())

        ttk.Label(toolbar, text="参数模板").pack(side="right", padx=(8, 4))
        preset_combo = ttk.Combobox(toolbar, textvariable=self.preset_var, values=[p.key for p in available_presets()], width=12, state="readonly")
        preset_combo.pack(side="right")
        preset_combo.bind("<<ComboboxSelected>>", lambda _e: self._save_ui_settings())

        self.progress = ttk.Progressbar(root, mode="indeterminate", length=260)
        self.progress.pack(anchor="e", padx=14)

        body = ttk.Frame(root)
        body.pack(fill="both", expand=True, padx=14, pady=(10, 0))

        side = ttk.Frame(body, width=200, padding=10)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        for key, text in (("dashboard", "首页总览"), ("reports", "报告中心"), ("assistant", "AI问答"), ("docs", "文档资料"), ("settings", "系统设置")):
            btn = ttk.Button(side, text=text, command=lambda view=key: self._show_view(view))
            btn.pack(fill="x", pady=4)
            self.nav_buttons[key] = btn
        ttk.Label(side, text="普通模式下会收起部分高阶能力；切换专业模式后可查看 AI 问答和更多参数。", style="Muted.TLabel", wraplength=170, justify="left").pack(side="bottom", anchor="w")

        self.content = ttk.Frame(body)
        self.content.pack(side="left", fill="both", expand=True)
        self.content.rowconfigure(0, weight=1)
        self.content.columnconfigure(0, weight=1)

        for key in ("dashboard", "reports", "assistant", "docs", "settings"):
            frame = ttk.Frame(self.content)
            frame.grid(row=0, column=0, sticky="nsew")
            self.views[key] = frame

        self._build_dashboard(self.views["dashboard"])
        self._build_reports_view(self.views["reports"])
        self._build_assistant_view(self.views["assistant"])
        self._build_docs_view(self.views["docs"])
        self._build_settings_view(self.views["settings"])
        self._show_view("dashboard")

        status = ttk.Frame(root, padding=(14, 8))
        status.pack(fill="x")
        ttk.Label(status, textvariable=self.status_var, style="Muted.TLabel").pack(side="left")

    def _build_dashboard(self, parent: ttk.Frame) -> None:
        canvas = tk.Canvas(parent, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)
        window_id = canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        scroll_frame.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window_id, width=event.width))

        def _wheel(event: tk.Event) -> None:
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind("<Enter>", lambda _e: canvas.bind_all("<MouseWheel>", _wheel))
        canvas.bind("<Leave>", lambda _e: canvas.unbind_all("<MouseWheel>"))
        parent = scroll_frame

        forecast_frame = ttk.LabelFrame(parent, text="沪锡实时预测看板", padding=10)
        forecast_frame.pack(fill="x")

        top_row = ttk.Frame(forecast_frame)
        top_row.pack(fill="x", pady=(0, 8))
        ttk.Label(top_row, text="启动后会自动展示四个周期的实时预测，并按设定频率更新。", style="Muted.TLabel").pack(side="left")
        self.forecast_refresh_button = ttk.Button(top_row, text="手动刷新", command=self._manual_full_refresh)
        self.forecast_refresh_button.pack(side="right")

        cards_row = tk.Frame(forecast_frame, bd=0, highlightthickness=0)
        cards_row.pack(fill="x")
        self.forecast_cards_container = cards_row
        for col in range(4):
            cards_row.grid_columnconfigure(col, weight=1)

        for idx, (key, label) in enumerate(HORIZON_ORDER):
            frame = tk.Frame(cards_row, bd=0, relief="flat", highlightthickness=1, padx=12, pady=12)
            frame.grid(row=0, column=idx, sticky="nsew", padx=(0 if idx == 0 else 8, 0))
            title = tk.Label(frame, text=label, font=("Microsoft YaHei UI", 12, "bold"), anchor="w")
            title.pack(fill="x")
            conf = tk.Label(frame, textvariable=self.forecast_vars[key]["confidence"], anchor="w")
            conf.pack(fill="x", pady=(4, 4))
            target = tk.Label(frame, textvariable=self.forecast_vars[key]["target"], anchor="w", justify="left", wraplength=280)
            target.pack(fill="x", pady=(0, 4))
            price = tk.Label(frame, textvariable=self.forecast_vars[key]["range"], font=("Microsoft YaHei UI", 13, "bold"), anchor="w", justify="left")
            price.pack(fill="x")
            prob = tk.Label(frame, textvariable=self.forecast_vars[key]["prob"], anchor="w", justify="left")
            prob.pack(fill="x", pady=(6, 4))
            driver = tk.Label(frame, textvariable=self.forecast_vars[key]["driver"], anchor="w", justify="left", wraplength=280)
            driver.pack(fill="x")
            button = tk.Button(frame, text="查看详细归因", bd=0, cursor="hand2", command=lambda horizon=key: self._show_forecast_detail(horizon))
            button.pack(anchor="w", pady=(8, 6))
            disclaimer = tk.Label(frame, text=COMPLIANCE_SMALL, justify="left", wraplength=280)
            disclaimer.pack(fill="x", side="bottom")
            self.forecast_cards[key] = {
                "frame": frame,
                "title": title,
                "confidence": conf,
                "target": target,
                "price": price,
                "prob": prob,
                "driver": driver,
                "button": button,
                "disclaimer": disclaimer,
                "index": idx,
            }
        cards_row.bind("<Configure>", lambda event: self._relayout_forecast_cards(event.width))

        chart_frame = ttk.LabelFrame(parent, text="价格走势与预测校准可视化", padding=10)
        chart_frame.pack(fill="x", pady=(12, 0))
        chart_frame.columnconfigure(0, weight=1)
        chart_frame.columnconfigure(1, weight=1)
        chart_frame.columnconfigure(2, weight=1)
        self.price_chart = tk.Canvas(chart_frame, height=210, highlightthickness=1, highlightbackground="#D8DDE8")
        self.price_chart.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.forecast_chart = tk.Canvas(chart_frame, height=210, highlightthickness=1, highlightbackground="#D8DDE8")
        self.forecast_chart.grid(row=0, column=1, sticky="nsew", padx=(0, 8))
        self.health_chart = tk.Canvas(chart_frame, height=210, highlightthickness=1, highlightbackground="#D8DDE8")
        self.health_chart.grid(row=0, column=2, sticky="nsew")
        self.price_chart.bind("<Configure>", lambda _e: self._render_visual_charts(self.current_result or {}))
        self.forecast_chart.bind("<Configure>", lambda _e: self._render_visual_charts(self.current_result or {}))
        self.health_chart.bind("<Configure>", lambda _e: self._render_visual_charts(self.current_result or {}))

        grid = ttk.Frame(parent)
        grid.pack(fill="x", pady=(12, 0))
        for i in range(2):
            grid.columnconfigure(i, weight=1)
        self._metric_card(grid, "最新预测摘要", self.summary_var, 0, 0)
        self._metric_card(grid, "市场状态", self.regime_var, 0, 1)
        self._metric_card(grid, "风险快照", self.risk_var, 1, 0)
        self._metric_card(grid, "信号与绩效", self.signal_var, 1, 1)

        self._metric_card(grid, "模型状态", self.model_var, 2, 0)
        self._metric_card(grid, "数据链路", self.data_var, 2, 1)

        lower = ttk.Panedwindow(parent, orient="horizontal")
        lower.pack(fill="both", expand=True, pady=(12, 0))
        left = ttk.Frame(lower)
        right = ttk.Frame(lower)
        lower.add(left, weight=3)
        lower.add(right, weight=2)

        pred_box = ttk.LabelFrame(left, text="历史验证时间线", padding=10)
        pred_box.pack(fill="both", expand=True)
        cols = ("anchor", "target", "regime", "conf", "prob", "ret", "low", "high")
        pred_tree_holder = ttk.Frame(pred_box)
        pred_tree_holder.pack(fill="both", expand=True)
        self.pred_tree = ttk.Treeview(pred_tree_holder, columns=cols, show="headings", height=18)
        pred_tree_scroll = ttk.Scrollbar(pred_tree_holder, orient="vertical", command=self.pred_tree.yview)
        self.pred_tree.configure(yscrollcommand=pred_tree_scroll.set)
        headings = {"anchor": "生成/锚点", "target": "目标窗口", "regime": "周期/状态", "conf": "置信度", "prob": "上涨概率", "ret": "预期收益", "low": "下沿", "high": "上沿"}
        for col, width in zip(cols, (145, 150, 125, 90, 90, 100, 110, 110)):
            self.pred_tree.heading(col, text=headings[col])
            self.pred_tree.column(col, width=width, anchor="center")
        self.pred_tree.pack(side="left", fill="both", expand=True)
        pred_tree_scroll.pack(side="right", fill="y")

        upper = ttk.LabelFrame(right, text="参数与核心因子", padding=10)
        upper.pack(fill="both", expand=True)
        self.factor_text = self._create_scrolled_text(upper, height=14)

        lower_right = ttk.Panedwindow(right, orient="vertical")
        lower_right.pack(fill="both", expand=True, pady=(8, 0))

        live_box = ttk.LabelFrame(lower_right, text="实时多模态快照", padding=10)
        lower_right.add(live_box, weight=2)
        self.live_text = self._create_scrolled_text(live_box, height=9)

        bandit_box = ttk.LabelFrame(lower_right, text="Bandit动作与模型健康", padding=10)
        lower_right.add(bandit_box, weight=1)
        self.bandit_text = self._create_scrolled_text(bandit_box, height=7)

        stress_box = ttk.LabelFrame(lower_right, text="情景压力测试矩阵", padding=10)
        lower_right.add(stress_box, weight=2)
        self.scenario_text = self._create_scrolled_text(stress_box, height=9)

    def _build_reports_view(self, parent: ttk.Frame) -> None:
        paned = ttk.Panedwindow(parent, orient="horizontal")
        paned.pack(fill="both", expand=True)
        left = ttk.Frame(paned)
        right = ttk.Frame(paned)
        paned.add(left, weight=2)
        paned.add(right, weight=5)

        report_tree_holder = ttk.Frame(left)
        report_tree_holder.pack(fill="both", expand=True)
        self.report_tree = ttk.Treeview(report_tree_holder, columns=("type", "generated"), show="headings")
        report_tree_scroll = ttk.Scrollbar(report_tree_holder, orient="vertical", command=self.report_tree.yview)
        self.report_tree.configure(yscrollcommand=report_tree_scroll.set)
        self.report_tree.heading("type", text="报告类型")
        self.report_tree.heading("generated", text="生成时间")
        self.report_tree.column("type", width=110, anchor="center")
        self.report_tree.column("generated", width=180, anchor="center")
        self.report_tree.pack(side="left", fill="both", expand=True)
        report_tree_scroll.pack(side="right", fill="y")
        self.report_tree.bind("<<TreeviewSelect>>", lambda _e: self._preview_report())
        ttk.Button(left, text="打开报告目录", command=lambda: self._open_path(self.paths.report_dir)).pack(fill="x", pady=(8, 0))

        self.report_text = self._create_scrolled_text(right, height=22)

    def _build_assistant_view(self, parent: ttk.Frame) -> None:
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=(0, 10))
        self.question_entry = ttk.Entry(row)
        self.question_entry.pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="提问", command=self._ask).pack(side="left", padx=(8, 0))
        for prompt in ("最新沪锡预测是什么？", "当前风险指标如何？", "概括实时新闻影响", "显示情景压力矩阵"):
            ttk.Button(parent, text=prompt, command=lambda q=prompt: self._ask(q)).pack(anchor="w", pady=2)
        self.answer_text = self._create_scrolled_text(parent, height=20, pady=(10, 0))

    def _build_docs_view(self, parent: ttk.Frame) -> None:
        row = ttk.Frame(parent)
        row.pack(fill="x")
        self.doc_choice = tk.StringVar(value=next(iter(self.doc_paths)))
        combo = ttk.Combobox(row, textvariable=self.doc_choice, state="readonly", values=list(self.doc_paths.keys()), width=28)
        combo.pack(side="left")
        combo.bind("<<ComboboxSelected>>", lambda _e: self._load_docs())
        ttk.Button(row, text="打开文档目录", command=lambda: self._open_path(next(iter(self.doc_paths.values())).parent)).pack(side="left", padx=(8, 0))
        self.docs_text = self._create_scrolled_text(parent, height=24, pady=(10, 0))

    def _build_settings_view(self, parent: ttk.Frame) -> None:
        left = ttk.LabelFrame(parent, text="当前控制项", padding=12)
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))
        right = ttk.LabelFrame(parent, text="备份管理", padding=12)
        right.pack(side="left", fill="both", expand=True)

        controls = ttk.LabelFrame(left, text="可视化参数面板", padding=10)
        controls.pack(fill="x", pady=(0, 8))
        controls.grid_columnconfigure(1, weight=1)
        controls.grid_columnconfigure(3, weight=1)

        ttk.Label(controls, text="参数模板").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        preset_combo = ttk.Combobox(controls, textvariable=self.preset_var, values=[p.key for p in available_presets()], width=16, state="readonly")
        preset_combo.grid(row=0, column=1, sticky="ew", pady=4)
        preset_combo.bind("<<ComboboxSelected>>", lambda _e: self._save_ui_settings())
        ttk.Label(controls, text="风险画像").grid(row=0, column=2, sticky="w", padx=(14, 8), pady=4)
        profile_combo = ttk.Combobox(controls, textvariable=self.profile_var, values=[p.key for p in available_risk_profiles()], width=16, state="readonly")
        profile_combo.grid(row=0, column=3, sticky="ew", pady=4)
        profile_combo.bind("<<ComboboxSelected>>", lambda _e: self._save_ui_settings())

        ttk.Label(controls, text="界面模式").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        mode_combo = ttk.Combobox(controls, textvariable=self.mode_var, values=["ordinary", "professional"], width=16, state="readonly")
        mode_combo.grid(row=1, column=1, sticky="ew", pady=4)
        mode_combo.bind("<<ComboboxSelected>>", lambda _e: self._save_ui_settings())
        ttk.Label(controls, text="主题").grid(row=1, column=2, sticky="w", padx=(14, 8), pady=4)
        theme_combo = ttk.Combobox(controls, textvariable=self.theme_var, values=["light", "dark"], width=16, state="readonly")
        theme_combo.grid(row=1, column=3, sticky="ew", pady=4)
        theme_combo.bind("<<ComboboxSelected>>", lambda _e: self._save_ui_settings())

        ttk.Label(controls, text="算力档位").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=4)
        compute_combo = ttk.Combobox(controls, textvariable=self.compute_profile_var, values=["auto", "fast", "balanced", "full", "gpu_full"], width=16, state="readonly")
        compute_combo.grid(row=2, column=1, sticky="ew", pady=4)
        compute_combo.bind("<<ComboboxSelected>>", lambda _e: self._save_ui_settings())
        ttk.Label(controls, text="默认报告").grid(row=2, column=2, sticky="w", padx=(14, 8), pady=4)
        report_combo = ttk.Combobox(controls, textvariable=self.report_type_var, values=["daily", "weekly", "monthly", "event"], width=16, state="readonly")
        report_combo.grid(row=2, column=3, sticky="ew", pady=4)
        report_combo.bind("<<ComboboxSelected>>", lambda _e: self._save_ui_settings())

        ttk.Label(controls, text="短周期刷新").grid(row=3, column=0, sticky="w", padx=(0, 8), pady=4)
        refresh_combo = ttk.Combobox(controls, textvariable=self.refresh_minutes_var, values=[10, 15, 30], width=16, state="readonly")
        refresh_combo.grid(row=3, column=1, sticky="ew", pady=4)
        refresh_combo.bind("<<ComboboxSelected>>", lambda _e: self._save_ui_settings())
        ttk.Label(controls, text="压力测试手数").grid(row=3, column=2, sticky="w", padx=(14, 8), pady=4)
        ttk.Spinbox(controls, from_=1, to=20, textvariable=self.stress_contracts_var, width=8, command=self._refresh_settings_text).grid(row=3, column=3, sticky="w", pady=4)

        ttk.Label(controls, text="字体缩放").grid(row=4, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Spinbox(controls, from_=90, to=130, increment=5, textvariable=self.font_scale_var, width=8, command=self._refresh_settings_text).grid(row=4, column=1, sticky="w", pady=4)
        check_row = ttk.Frame(controls)
        check_row.grid(row=5, column=0, columnspan=4, sticky="ew", pady=(8, 0))
        ttk.Checkbutton(check_row, text="启用实时数据", variable=self.live_enabled_var, command=self._save_ui_settings).pack(side="left", padx=(0, 12))
        ttk.Checkbutton(check_row, text="仅缓存模式", variable=self.cache_only_var, command=self._save_ui_settings).pack(side="left", padx=(0, 12))
        ttk.Checkbutton(check_row, text="自动备份", variable=self.auto_backup_var, command=self._save_ui_settings).pack(side="left", padx=(0, 12))
        ttk.Checkbutton(check_row, text="AI问答", variable=self.qna_enabled_var, command=self._save_ui_settings).pack(side="left", padx=(0, 12))
        ttk.Checkbutton(check_row, text="语音预警", variable=self.voice_alerts_var, command=self._save_ui_settings).pack(side="left")

        ttk.Label(controls, textvariable=self.preset_detail_var, style="Muted.TLabel", wraplength=650, justify="left").grid(row=6, column=0, columnspan=4, sticky="w", pady=(8, 0))
        ttk.Label(controls, textvariable=self.profile_detail_var, style="Muted.TLabel", wraplength=650, justify="left").grid(row=7, column=0, columnspan=4, sticky="w", pady=(2, 0))
        ttk.Label(controls, textvariable=self.compute_detail_var, style="Muted.TLabel", wraplength=650, justify="left").grid(row=8, column=0, columnspan=4, sticky="w", pady=(2, 0))

        api_box = ttk.LabelFrame(left, text="API Key 配置", padding=12)
        api_box.pack(fill="x", pady=(8, 8))

        alpha_row = ttk.Frame(api_box)
        alpha_row.pack(fill="x", pady=(0, 6))
        ttk.Label(alpha_row, text="Alpha Vantage").pack(side="left")
        self.alpha_entry = ttk.Entry(alpha_row, textvariable=self.alpha_key_var, show="*")
        self.alpha_entry.pack(side="left", fill="x", expand=True, padx=(8, 8))
        ttk.Checkbutton(alpha_row, text="显示", variable=self.show_alpha_var, command=self._toggle_secret_entries).pack(side="left")
        ttk.Button(alpha_row, text="测试", command=lambda: self._start_api_test("alpha")).pack(side="left", padx=(8, 0))

        news_row = ttk.Frame(api_box)
        news_row.pack(fill="x", pady=(0, 6))
        ttk.Label(news_row, text="NewsAPI").pack(side="left")
        self.news_entry = ttk.Entry(news_row, textvariable=self.news_key_var, show="*")
        self.news_entry.pack(side="left", fill="x", expand=True, padx=(30, 8))
        ttk.Checkbutton(news_row, text="显示", variable=self.show_news_var, command=self._toggle_secret_entries).pack(side="left")
        ttk.Button(news_row, text="测试", command=lambda: self._start_api_test("news")).pack(side="left", padx=(8, 0))

        info = (
            "Alpha Vantage 注册地址：https://www.alphavantage.co/\n"
            "NewsAPI 注册地址：https://newsapi.org/\n"
            "密钥会以本地加密方式保存，并同步到当前终端环境变量。"
        )
        ttk.Label(api_box, text=info, style="Muted.TLabel", justify="left").pack(anchor="w", pady=(4, 8))

        actions = ttk.Frame(api_box)
        actions.pack(fill="x")
        ttk.Button(actions, text="全部测试", command=lambda: self._start_api_test("all")).pack(side="left")
        ttk.Button(actions, text="保存配置", command=self._save_api_configuration).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="保存并启动实时预测", command=self._save_api_and_start).pack(side="left", padx=(8, 0))
        ttk.Label(api_box, textvariable=self.api_status_var, style="Muted.TLabel").pack(anchor="w", pady=(8, 0))
        ttk.Label(api_box, text=COMPLIANCE_SMALL, style="Muted.TLabel", wraplength=620, justify="left").pack(anchor="w", pady=(6, 0))

        summary_box = ttk.LabelFrame(left, text="只读状态摘要", padding=8)
        summary_box.pack(fill="both", expand=True, pady=(8, 0))
        self.settings_text = self._create_scrolled_text(summary_box, height=8)
        action_row = ttk.Frame(left)
        action_row.pack(fill="x", pady=(8, 0))
        ttk.Button(action_row, text="应用设置", command=self._save_ui_settings).pack(side="left")
        ttk.Button(action_row, text="应用并刷新预测", command=self._save_settings_and_refresh).pack(side="left", padx=(8, 0))
        ttk.Button(action_row, text="恢复默认", command=self._restore_defaults).pack(side="left", padx=(8, 0))

        self.backup_list = tk.Listbox(right)
        self.backup_list.pack(fill="both", expand=True)
        ttk.Button(right, text="立即备份", command=self._backup_data).pack(anchor="w", pady=(8, 0))

    def _metric_card(self, parent: ttk.Frame, title: str, variable: tk.StringVar, row: int, col: int) -> None:
        box = ttk.LabelFrame(parent, text=title, padding=10)
        box.grid(row=row, column=col, sticky="nsew", padx=(0 if col == 0 else 8, 0), pady=(0 if row == 0 else 8, 0))
        ttk.Label(box, textvariable=variable, style="Metric.TLabel", wraplength=560, justify="left").pack(anchor="w")

    def _create_scrolled_text(
        self,
        parent: tk.Widget,
        *,
        height: int = 8,
        pady: tuple[int, int] | int = 0,
    ) -> tk.Text:
        holder = ttk.Frame(parent)
        holder.pack(fill="both", expand=True, pady=pady)
        text = tk.Text(holder, wrap="word", relief="flat", height=height)
        scroll = ttk.Scrollbar(holder, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        return text

    def _relayout_forecast_cards(self, width: int | None = None) -> None:
        container = getattr(self, "forecast_cards_container", None)
        if not isinstance(container, tk.Frame):
            return
        width = int(width or container.winfo_width() or 1200)
        columns = 2 if width < 1180 else 4
        for col in range(4):
            container.grid_columnconfigure(col, weight=1 if col < columns else 0)
        wrap = max(210, min(360, width // columns - 46))
        for key, _label in HORIZON_ORDER:
            card = self.forecast_cards.get(key, {})
            frame = card.get("frame")
            idx = int(card.get("index", 0) or 0)
            if not isinstance(frame, tk.Frame):
                continue
            row = idx // columns
            col = idx % columns
            frame.grid_configure(row=row, column=col, sticky="nsew", padx=(0 if col == 0 else 8, 0), pady=(0 if row == 0 else 8, 0))
            for name in ("target", "driver", "disclaimer"):
                widget = card.get(name)
                if isinstance(widget, tk.Label):
                    widget.configure(wraplength=wrap)

    def _apply_theme(self) -> None:
        theme = LIGHT if self.theme_var.get() == "light" else DARK
        style = ttk.Style(self)
        scale = max(0.90, min(1.30, self._safe_int_var(self.font_scale_var, 100) / 100.0))
        base_font = ("Microsoft YaHei UI", max(9, int(10 * scale)))
        metric_font = ("Microsoft YaHei UI", max(10, int(11 * scale)))
        self.configure(bg=theme["bg"])
        style.configure("TFrame", background=theme["bg"])
        style.configure("TLabelframe", background=theme["panel"], foreground=theme["text"])
        style.configure("TLabelframe.Label", background=theme["panel"], foreground=theme["text"])
        style.configure("TLabel", background=theme["bg"], foreground=theme["text"], font=base_font)
        style.configure("Muted.TLabel", background=theme["bg"], foreground=theme["muted"], font=("Microsoft YaHei UI", max(8, int(9 * scale))))
        style.configure("Hero.TLabel", background=theme["bg"], foreground=theme["primary"], font=("Microsoft YaHei UI", max(13, int(16 * scale)), "bold"))
        style.configure("Metric.TLabel", background=theme["panel"], foreground=theme["text"], font=metric_font)
        style.configure("Section.TLabel", background=theme["bg"], foreground=theme["text"], font=base_font)
        style.configure("TButton", background=theme["panel"], foreground=theme["text"])
        style.configure("App.TButton", background=theme["primary"], foreground="#FFFFFF")
        style.configure("Treeview", background=theme["panel"], fieldbackground=theme["panel"], foreground=theme["text"], font=base_font, rowheight=max(22, int(24 * scale)))

        for widget in (self.factor_text, self.live_text, self.bandit_text, self.scenario_text, self.report_text, self.answer_text, self.docs_text, self.settings_text):
            widget.configure(bg=theme["panel"], fg=theme["text"], insertbackground=theme["text"], selectbackground=theme["primary"])
        for canvas_name in ("price_chart", "forecast_chart", "health_chart"):
            canvas = getattr(self, canvas_name, None)
            if isinstance(canvas, tk.Canvas):
                canvas.configure(bg=theme["panel"])

        payload = (self.current_live_predictions or {}).get("cards", {}) if isinstance(self.current_live_predictions, dict) else {}
        for key, card in self.forecast_cards.items():
            direction = "neutral"
            if isinstance(payload, dict) and key in payload and isinstance(payload[key], dict):
                direction = str(payload[key].get("direction_key", payload[key].get("direction_label", "neutral")))
            bg = theme["neutral"] if direction == "neutral" else theme["bull"] if direction == "bullish" else theme["bear"]
            for name in ("frame", "title", "confidence", "target", "price", "prob", "driver", "disclaimer"):
                widget = card[name]
                if isinstance(widget, tk.Frame):
                    widget.configure(bg=bg, highlightbackground=theme["primary"], highlightcolor=theme["primary"])
                elif isinstance(widget, tk.Label):
                    widget.configure(bg=bg, fg=theme["text"])
            if isinstance(card["button"], tk.Button):
                card["button"].configure(bg=theme["primary"], fg="#FFFFFF", activebackground=theme["primary"], activeforeground="#FFFFFF")

    def _toggle_secret_entries(self) -> None:
        self.alpha_entry.configure(show="" if self.show_alpha_var.get() else "*")
        self.news_entry.configure(show="" if self.show_news_var.get() else "*")

    def _live_predictions_generated_at(self) -> datetime | None:
        if not isinstance(self.current_live_predictions, dict):
            return None
        value = self.current_live_predictions.get("generated_at")
        stamp = pd.to_datetime(value, errors="coerce")
        if pd.isna(stamp):
            return None
        if getattr(stamp, "tzinfo", None) is None:
            stamp = stamp.tz_localize("Asia/Hong_Kong")
        else:
            stamp = stamp.tz_convert("Asia/Hong_Kong")
        return stamp.to_pydatetime()

    def _should_force_full_refresh(self) -> bool:
        if not isinstance(self.current_result, dict):
            return True
        if not isinstance(self.current_result.get("predictions"), pd.DataFrame):
            return True
        generated = self._live_predictions_generated_at()
        if generated is None:
            return True
        now = pd.Timestamp.now(tz="Asia/Hong_Kong").to_pydatetime()
        age_seconds = max(0.0, (now - generated).total_seconds())
        if age_seconds > 30 * 60:
            return True
        if generated.date() != now.date():
            return True
        return False

    def _free_disk_mb(self) -> float:
        try:
            usage = shutil.disk_usage(self.paths.user_data_dir)
            return float(usage.free) / (1024 * 1024)
        except Exception:
            return 0.0

    def _disk_space_note(self) -> str:
        free_mb = self._free_disk_mb()
        return f"磁盘可用空间约 {free_mb:.0f} MB" if free_mb > 0 else ""

    def _disk_space_is_critical(self) -> bool:
        return self._free_disk_mb() < CRITICAL_FREE_SPACE_MB

    def _disk_space_is_low(self) -> bool:
        return self._free_disk_mb() < LOW_FREE_SPACE_MB

    def _startup_sequence(self) -> None:
        missing = missing_api_keys()
        if missing:
            self._show_api_required_modal(missing)
            self.status_var.set("缺少宏观或新闻 API Key，系统将先以仅报价模式运行实时预测。")
            if self.live_enabled_var.get():
                self._schedule_refresh_jobs()
            return
        if self.live_enabled_var.get():
            self._schedule_refresh_jobs()
            refresh_scope = "all" if self._should_force_full_refresh() else "short"
            self._start_live_prediction_pipeline(refresh_scope=refresh_scope, reason="startup", optimization_level="auto")

    def _show_api_required_modal(self, missing: list[str]) -> None:
        if self.startup_modal is not None and self.startup_modal.winfo_exists():
            self.startup_modal.lift()
            return
        modal = tk.Toplevel(self)
        modal.title("配置 API Key 以启用实时预测")
        modal.transient(self)
        modal.geometry("720x360")
        modal.resizable(False, False)

        body = tk.Frame(modal, padx=18, pady=18)
        body.pack(fill="both", expand=True)
        tk.Label(body, text="配置 API Key 以启用实时预测", font=("Microsoft YaHei UI", 14, "bold"), anchor="w", justify="left").pack(fill="x")
        missing_text = "\n".join(f"- {item}" for item in missing)
        message = (
            "当前仍有部分增强数据源未配置。\n\n"
            "缺失项：\n"
            f"{missing_text}\n\n"
            "Alpha Vantage：https://www.alphavantage.co/\n"
            "NewsAPI：https://newsapi.org/\n\n"
            "你现在可以先配置密钥，也可以先继续使用内置免费报价源，进入仅报价模式的实时预测。"
        )
        tk.Label(body, text=message, justify="left", anchor="w", wraplength=660).pack(fill="both", expand=True, pady=(12, 12))
        tk.Label(body, text=COMPLIANCE_SMALL, justify="left", wraplength=660).pack(fill="x", pady=(0, 12))

        actions = tk.Frame(body)
        actions.pack(fill="x")
        tk.Button(actions, text="去配置 API", command=self._focus_api_configuration).pack(side="left")
        tk.Button(actions, text="继续仅报价模式", command=self._continue_quote_only).pack(side="left", padx=(8, 0))
        tk.Button(actions, text="退出软件", command=self.destroy).pack(side="right")
        self.startup_modal = modal

    def _focus_api_configuration(self) -> None:
        self._show_view("settings")
        self.alpha_entry.focus_set()
        if self.startup_modal is not None and self.startup_modal.winfo_exists():
            self.startup_modal.lift()

    def _continue_quote_only(self) -> None:
        if self.startup_modal is not None and self.startup_modal.winfo_exists():
            self.startup_modal.destroy()
            self.startup_modal = None
        self.status_var.set("正在以仅报价模式运行实时预测；后续可随时补充 Alpha Vantage 和 NewsAPI 密钥。")
        if self.live_enabled_var.get() and not self.pipeline_busy:
            self._schedule_refresh_jobs()
            self._start_live_prediction_pipeline(refresh_scope="all", reason="startup", optimization_level="auto")

    def _save_api_configuration(self) -> None:
        save_api_keys(self.alpha_key_var.get(), self.news_key_var.get())
        self.api_keys = load_api_keys()
        self.api_status_var.set("API 配置已保存到本地。")
        self.status_var.set("API 配置已保存。")

    def _save_api_and_start(self) -> None:
        self._save_api_configuration()
        still_missing = missing_api_keys()
        if still_missing:
            self.api_status_var.set("保存完成，但仍有必需的 Key 缺失。")
            return
        if self.startup_modal is not None and self.startup_modal.winfo_exists():
            self.startup_modal.destroy()
            self.startup_modal = None
        self._schedule_refresh_jobs()
        self._start_live_prediction_pipeline(refresh_scope="all", reason="startup", optimization_level="auto")

    def _start_api_test(self, which: str) -> None:
        self.api_status_var.set(f"正在测试 {which} 连接...")
        Thread(target=self._api_test_worker, args=(which,), daemon=True).start()

    def _api_test_worker(self, which: str) -> None:
        try:
            if which == "alpha":
                result = ("alpha",) + test_alpha_vantage_key(self.alpha_key_var.get())
            elif which == "news":
                result = ("news",) + test_newsapi_key(self.news_key_var.get())
            else:
                alpha_ok, alpha_msg = test_alpha_vantage_key(self.alpha_key_var.get())
                news_ok, news_msg = test_newsapi_key(self.news_key_var.get())
                result = ("all", alpha_ok and news_ok, f"Alpha: {alpha_msg} | News: {news_msg}")
        except Exception:
            self.queue.put(("api_test_error", traceback.format_exc()))
        else:
            self.queue.put(("api_test_done", result))

    def _show_view(self, name: str) -> None:
        if name == "assistant" and self.mode_var.get() != "professional":
            self.status_var.set("请先切换到专业模式，再打开这个面板。")
            return
        if name == "docs" and not self.docs_text.get("1.0", "end").strip():
            self._load_docs()
        if name == "reports" and not self.report_manifest:
            self._load_reports()
        self.views[name].tkraise()

    def _run_demo(self) -> None:
        self.current_csv_path = None
        self._start_live_prediction_pipeline(refresh_scope="all", reason="manual", use_demo=True, optimization_level="fast")

    def _run_csv(self) -> None:
        path = filedialog.askopenfilename(title="选择沪锡 CSV 数据", filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if not path:
            return
        self.current_csv_path = path
        self._start_live_prediction_pipeline(refresh_scope="all", reason="manual", csv_path=path, optimization_level="full")

    def _rerun_current(self) -> None:
        self._start_live_prediction_pipeline(refresh_scope="all", reason="manual", csv_path=self.current_csv_path, optimization_level=self._selected_optimization_level())

    def _manual_full_refresh(self) -> None:
        self._start_live_prediction_pipeline(refresh_scope="all", reason="manual", csv_path=self.current_csv_path, optimization_level=self._selected_optimization_level())

    def _ensure_api_server(self) -> None:
        if self.api_server_started:
            return
        self.api_server_started = True

        def _serve() -> None:
            try:
                run_api_server()
            except OSError:
                # Port is probably already occupied by another terminal instance.
                return
            except Exception:
                return

        Thread(target=_serve, daemon=True).start()
        self.status_var.set("本地 Web API 已启动，专业 Web 终端可通过 http://127.0.0.1:8765 打开。")

    def _open_web_terminal(self) -> None:
        self._ensure_api_server()
        webbrowser.open("http://127.0.0.1:8765/")
        self.web_terminal_opened = True
        self.status_var.set("已打开专业 Web 终端；如浏览器未自动弹出，请访问 http://127.0.0.1:8765/")

    def _open_web_terminal_once(self) -> None:
        if self.web_terminal_opened:
            return
        self._open_web_terminal()

    def _start_live_prediction_pipeline(
        self,
        *,
        refresh_scope: str,
        reason: str,
        csv_path: str | None = None,
        use_demo: bool = False,
        optimization_level: str = "full",
    ) -> None:
        if self.pipeline_busy:
            self.status_var.set("已有预测刷新任务正在运行，请等待本轮完成；系统不会重复启动以避免界面卡顿。")
            return
        if self._disk_space_is_critical():
            note = self._disk_space_note()
            self.status_var.set("磁盘空间过低，已暂停刷新。请先清理空间后重试。")
            self._show_text_modal(
                "磁盘空间不足",
                f"当前磁盘空间过低，刷新结果可能无法完整写入。\n{note}\n\n建议先释放至少 {CRITICAL_FREE_SPACE_MB} MB 可用空间，再重新刷新。\n\n{COMPLIANCE_SMALL}",
            )
            return

        self.pipeline_busy = True
        self.progress.start(10)
        self.forecast_refresh_button.configure(text="刷新中...", state="disabled")
        reason_label = "启动刷新" if reason == "startup" else "手动刷新" if reason == "manual" else "定时刷新"
        missing = missing_api_keys()
        mode_label = "仅报价" if missing else "完整多模态"
        disk_note = self._disk_space_note()
        disk_text = f" | {disk_note}" if disk_note else ""
        self.status_var.set(f"正在执行{reason_label}，范围：{refresh_scope}，模式：{mode_label}{disk_text}。")
        self._launch_pipeline_process(
            refresh_scope=refresh_scope,
            csv_path=csv_path,
            use_remote=bool(self.live_enabled_var.get()) and not bool(self.cache_only_var.get()),
            use_demo=use_demo,
            optimization_level=optimization_level,
        )

    def _launch_pipeline_process(
        self,
        *,
        refresh_scope: str,
        csv_path: str | None,
        use_remote: bool,
        use_demo: bool,
        optimization_level: str,
    ) -> None:
        runtime_dir = self.paths.user_data_dir / "_runtime"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        self.pipeline_payload_path = runtime_dir / f"live_payload_{stamp}.json"
        self.pipeline_result_path = runtime_dir / f"live_result_{stamp}.pkl"
        self.pipeline_existing_path = None

        payload = {
            "csv_path": csv_path,
            "preset_name": self.preset_var.get(),
            "risk_profile_name": self.profile_var.get(),
            "refresh_scope": refresh_scope,
            "use_remote": use_remote,
            "symbols": list(self.settings.sina_symbols),
            "use_demo": use_demo,
            "optimization_level": optimization_level,
        }
        if refresh_scope == "short" and isinstance(self.current_result, dict):
            self.pipeline_existing_path = runtime_dir / f"existing_result_{stamp}.pkl"
            with self.pipeline_existing_path.open("wb") as handle:
                pickle.dump(self.current_result, handle, protocol=pickle.HIGHEST_PROTOCOL)
            payload["existing_result_path"] = str(self.pipeline_existing_path)

        self.pipeline_payload_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        if getattr(sys, "frozen", False):
            command = [sys.executable, "--live-worker", str(self.pipeline_payload_path), str(self.pipeline_result_path)]
        else:
            command = [sys.executable, str(self.paths.root / "app_launcher.py"), "--live-worker", str(self.pipeline_payload_path), str(self.pipeline_result_path)]

        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self.pipeline_process = subprocess.Popen(command, creationflags=creationflags)
        self.pipeline_started_at = datetime.now()
        self.pipeline_timeout_seconds = 180 if optimization_level == "fast" else 420

    def _poll_queue(self) -> None:
        self._poll_pipeline_process()
        try:
            while True:
                status, payload = self.queue.get_nowait()
                if status == "live_pipeline_success":
                    self.progress.stop()
                    self.pipeline_busy = False
                    self.forecast_refresh_button.configure(text="手动刷新", state="normal")
                    self.current_result = payload if isinstance(payload, dict) else None
                    if isinstance(payload, dict):
                        self._render_result(payload)
                    self.status_var.set("实时预测已刷新完成。")
                    if self.settings.auto_backup and self.mode_var.get() == "professional":
                        self._backup_data(silent=True)
                elif status == "live_pipeline_error":
                    self.progress.stop()
                    self.pipeline_busy = False
                    self.forecast_refresh_button.configure(text="手动刷新", state="normal")
                    self.status_var.set("预测刷新失败，界面已保留上一次成功结果。")
                    self._show_text_modal(
                        "预测刷新失败",
                        str(payload) + "\n\n系统会保留上一次成功的预测结果，并在下一次定时刷新时自动重试。\n\n" + COMPLIANCE_SMALL,
                    )
                elif status == "api_test_done":
                    which, ok, message = payload  # type: ignore[misc]
                    prefix = {"alpha": "Alpha Vantage", "news": "NewsAPI", "all": "全部测试"}.get(which, which)
                    self.api_status_var.set(f"{prefix}：{'通过' if ok else '失败'} | {message}")
                elif status == "api_test_error":
                    self.api_status_var.set("API 测试失败。")
                    self._show_text_modal("API 测试失败", str(payload) + "\n\n" + COMPLIANCE_SMALL)
        except Empty:
            pass
        self.after(200, self._poll_queue)

    def _poll_pipeline_process(self) -> None:
        if self.pipeline_process is None:
            return
        if self.pipeline_started_at is not None:
            elapsed = (datetime.now() - self.pipeline_started_at).total_seconds()
            if elapsed > self.pipeline_timeout_seconds:
                try:
                    self.pipeline_process.kill()
                except Exception:
                    pass
                self._finish_pipeline_error("实时预测子进程执行超时，系统已自动中止本次刷新并保留上一次成功结果。")
                return
        if self.pipeline_process.poll() is None:
            return

        result_path = self.pipeline_result_path
        if result_path is None or not result_path.exists():
            self._finish_pipeline_error("实时预测子进程已结束，但没有生成结果文件。")
            return
        try:
            with result_path.open("rb") as handle:
                payload = pickle.load(handle)
        except Exception:
            self._finish_pipeline_error(traceback.format_exc())
            return

        if isinstance(payload, dict) and payload.get("ok") is True and isinstance(payload.get("result"), dict):
            self._finish_pipeline_success(payload["result"])
            return
        error_text = payload.get("error") if isinstance(payload, dict) else "未知错误。"
        self._finish_pipeline_error(str(error_text))

    def _finish_pipeline_success(self, payload: dict[str, object]) -> None:
        self.progress.stop()
        self.pipeline_busy = False
        self.forecast_refresh_button.configure(text="手动刷新", state="normal")
        self.current_result = payload
        self._render_result(payload)
        generated = self._live_predictions_generated_at()
        disk_note = self._disk_space_note()
        if generated is not None:
            status = f"实时预测已刷新完成，最新数据时间：{generated.strftime('%Y-%m-%d %H:%M:%S')}"
        else:
            status = "实时预测已刷新完成。"
        if disk_note:
            status = f"{status} | {disk_note}"
        if self._disk_space_is_low():
            status = f"{status} | 空间偏低，已优先保证刷新结果。"
        self.status_var.set(status)
        if self.settings.auto_backup and self.mode_var.get() == "professional" and not self._disk_space_is_low():
            try:
                self._backup_data(silent=True)
            except Exception:
                pass
        self._cleanup_pipeline_files()

    def _finish_pipeline_error(self, error_text: str) -> None:
        self.progress.stop()
        self.pipeline_busy = False
        self.forecast_refresh_button.configure(text="手动刷新", state="normal")
        self.status_var.set("预测刷新失败，界面已保留上一次成功结果。")
        self._show_text_modal(
            "预测刷新失败",
            str(error_text) + "\n\n系统会保留上一次成功的预测结果，并在下一次定时刷新时自动重试。\n\n" + COMPLIANCE_SMALL,
        )
        self._cleanup_pipeline_files()

    def _cleanup_pipeline_files(self) -> None:
        self.pipeline_process = None
        self.pipeline_started_at = None
        self.pipeline_timeout_seconds = 0
        for path in (self.pipeline_payload_path, self.pipeline_result_path, self.pipeline_existing_path):
            if isinstance(path, Path) and path.exists():
                try:
                    path.unlink()
                except Exception:
                    pass
        self.pipeline_payload_path = None
        self.pipeline_result_path = None
        self.pipeline_existing_path = None

    def _render_result(self, result: dict[str, object]) -> None:
        preds = result.get("predictions")
        metrics = result.get("metrics", {})
        signals = result.get("signals")
        features = result.get("selected_features", [])
        self.current_live_snapshot = result.get("live_snapshot") if isinstance(result.get("live_snapshot"), dict) else self.current_live_snapshot
        self.current_live_predictions = result.get("live_predictions") if isinstance(result.get("live_predictions"), dict) else self.current_live_predictions
        self.current_scenario_matrix = result.get("scenario_matrix") if isinstance(result.get("scenario_matrix"), pd.DataFrame) else self.current_scenario_matrix
        self.current_position_risk = result.get("position_risk") if isinstance(result.get("position_risk"), dict) else self.current_position_risk
        self.current_optimization_summary = result.get("optimization_summary") if isinstance(result.get("optimization_summary"), dict) else self.current_optimization_summary
        self.current_bandit_summary = result.get("bandit_summary") if isinstance(result.get("bandit_summary"), dict) else self.current_bandit_summary
        self.current_prediction_history = result.get("prediction_history") if isinstance(result.get("prediction_history"), pd.DataFrame) else self.current_prediction_history
        self.current_prediction_evaluation = result.get("prediction_evaluation") if isinstance(result.get("prediction_evaluation"), pd.DataFrame) else self.current_prediction_evaluation
        self.current_prediction_evaluation_summary = result.get("prediction_evaluation_summary") if isinstance(result.get("prediction_evaluation_summary"), dict) else self.current_prediction_evaluation_summary
        self.current_calibration_profile = result.get("calibration_profile") if isinstance(result.get("calibration_profile"), dict) else self.current_calibration_profile
        self.current_backtest_diagnostics = result.get("backtest_diagnostics") if isinstance(result.get("backtest_diagnostics"), dict) else self.current_backtest_diagnostics
        self.current_model_memory = result.get("model_memory") if isinstance(result.get("model_memory"), dict) else self.current_model_memory
        self.current_v2_artifacts = result.get("v2_artifacts") if isinstance(result.get("v2_artifacts"), dict) else self.current_v2_artifacts
        self.report_manifest = result.get("report_manifest", []) if isinstance(result.get("report_manifest"), list) else self.report_manifest
        opt_level = str(result.get("optimization_level", self.settings.compute_profile))
        active_contract = ""
        source_mode = ""
        if isinstance(self.current_live_snapshot, dict):
            contract_meta = self.current_live_snapshot.get("contract_meta", {})
            if isinstance(contract_meta, dict):
                active_contract = str(contract_meta.get("active_contract", "") or contract_meta.get("target_contract", "") or "")
        if isinstance(result.get("raw"), pd.DataFrame) and not result["raw"].empty:
            source_mode = str(result["raw"].iloc[-1].get("data_source_mode", "") or "")
        self.model_var.set(f"计算档位 {opt_level} | 主力 {active_contract or 'SN'}")
        self.data_var.set(f"数据模式 {source_mode or 'unknown'} | {'联网' if self.live_enabled_var.get() and not self.cache_only_var.get() else '缓存/离线'}")

        if isinstance(preds, pd.DataFrame) and not preds.empty:
            latest = preds.iloc[-1]
            live_cards = (self.current_live_predictions or {}).get("cards", {}) if isinstance(self.current_live_predictions, dict) else {}
            tomorrow_card = live_cards.get("tomorrow", {}) if isinstance(live_cards, dict) else {}
            if isinstance(tomorrow_card, dict) and tomorrow_card:
                self.summary_var.set(
                    f"{tomorrow_card.get('contract_code', 'SN')} | 目标 {tomorrow_card.get('target_label', 'n/a')} | 中枢 {float(tomorrow_card.get('price_center', 0.0) or 0.0):.0f} | 上涨 {float(tomorrow_card.get('prob_up', 0.0) or 0.0):.2%}"
                )
            else:
                self.summary_var.set(f"历史锚点 {preds.index[-1].date()} | 预测收益 {latest['predicted_return']:.2%} | 上涨概率 {latest.get('prob_up_multimodal', latest['prob_up']):.2%}")
            target_date = (pd.Timestamp(preds.index[-1]) + pd.offsets.BDay(1)).date()
            self.regime_var.set(f"锚点 {preds.index[-1].date()} -> 目标 {target_date} | {latest['regime']} | 区间 [{latest['pred_low']:.0f}, {latest['pred_high']:.0f}]")
            self.risk_var.set(f"置信度 {latest.get('confidence_multimodal', latest['confidence']):.1f} | 技术 {latest['technical_score']:.1f} | 基本面 {latest['fundamental_score']:.1f}")
            self._fill_tree(preds.tail(60))

        if isinstance(metrics, dict):
            self.signal_var.set(f"夏普 {metrics.get('sharpe', 0.0):.2f} | 胜率 {metrics.get('win_rate', 0.0):.2%} | 回撤 {metrics.get('max_drawdown', 0.0):.2%}")
        if isinstance(signals, pd.DataFrame) and not signals.empty:
            latest_signal = signals.iloc[-1]
            self.signal_var.set(f"{latest_signal['signal_label']} | 参考开仓 {latest_signal['entry_reference']:.0f} | 止损 {latest_signal['stop_loss']:.0f} | 止盈 {latest_signal['take_profit']:.0f}")

        self.factor_text.delete("1.0", "end")
        factor_summary = self._factor_summary(features, self.current_optimization_summary, self.current_bandit_summary, self.current_backtest_diagnostics)
        if isinstance(self.current_v2_artifacts, dict) and self.current_v2_artifacts:
            v2_diag = self.current_v2_artifacts.get("factor_diagnostics", {})
            if isinstance(v2_diag, dict):
                factor_summary += (
                    "\n\nV2 因子研究面板："
                    f"\n- 特征版本：{v2_diag.get('feature_version', 'n/a')}"
                    f"\n- 入选因子数：{v2_diag.get('selected_count', 0)}"
                    f"\n- 平均覆盖率：{float(v2_diag.get('coverage_mean', 0.0) or 0.0):.1%}"
                    f"\n- 平均 |IC|：{float(v2_diag.get('ic_abs_mean', 0.0) or 0.0):.3f}"
                    f"\n- 最大 VIF：{float(v2_diag.get('max_vif', 0.0) or 0.0):.2f}"
                    "\n- 规则：时间序列切分、滚动标准化、禁止随机切分和全样本标准化。"
                )
        self.factor_text.insert("1.0", factor_summary)
        self._render_live_predictions()
        self._render_visual_charts(result)
        self._render_live_snapshot()
        self._render_bandit_panel()
        self._render_scenarios()
        self._load_reports(self.report_manifest)
        self._refresh_settings_text()
        self._apply_theme()

    def _chart_theme(self) -> dict[str, str]:
        return LIGHT if self.theme_var.get() == "light" else DARK

    @staticmethod
    def _series_points(values: list[float], width: int, height: int, pad: int = 32) -> list[tuple[float, float]]:
        clean = [float(v) for v in values if pd.notna(v)]
        if not clean:
            return []
        lo = min(clean)
        hi = max(clean)
        if abs(hi - lo) < 1e-9:
            lo -= 1.0
            hi += 1.0
        usable_w = max(20, width - pad * 2)
        usable_h = max(20, height - pad * 2)
        points: list[tuple[float, float]] = []
        n = max(1, len(values) - 1)
        for idx, value in enumerate(values):
            if pd.isna(value):
                continue
            x = pad + usable_w * idx / n
            y = height - pad - usable_h * (float(value) - lo) / (hi - lo)
            points.append((x, y))
        return points

    def _draw_line_chart(
        self,
        canvas: tk.Canvas,
        *,
        title: str,
        primary_values: list[float],
        primary_label: str,
        secondary_values: list[float] | None = None,
        secondary_label: str | None = None,
        footer: str = "",
    ) -> None:
        theme = self._chart_theme()
        canvas.delete("all")
        width = max(int(canvas.winfo_width() or 560), 320)
        height = max(int(canvas.winfo_height() or 210), 180)
        canvas.create_rectangle(0, 0, width, height, fill=theme["panel"], outline=theme["panel"])
        canvas.create_text(14, 16, text=title, anchor="w", fill=theme["text"], font=("Microsoft YaHei UI", 11, "bold"))
        if not primary_values:
            canvas.create_text(width / 2, height / 2, text="暂无可视化数据，刷新后自动生成。", fill=theme["muted"], font=("Microsoft YaHei UI", 10))
            return
        all_values = list(primary_values)
        if secondary_values:
            all_values.extend([v for v in secondary_values if pd.notna(v)])
        lo = min(all_values)
        hi = max(all_values)
        if abs(hi - lo) < 1e-9:
            lo -= 1.0
            hi += 1.0
        for step in range(4):
            y = 42 + (height - 82) * step / 3
            canvas.create_line(32, y, width - 20, y, fill="#D8DDE8" if self.theme_var.get() == "light" else "#303640")
            value = hi - (hi - lo) * step / 3
            canvas.create_text(30, y, text=f"{value:.0f}", anchor="e", fill=theme["muted"], font=("Microsoft YaHei UI", 8))

        points = self._series_points(primary_values, width, height, pad=38)
        if len(points) >= 2:
            canvas.create_line(points, fill=theme["primary"], width=2, smooth=True)
        for x, y in points[-6:]:
            canvas.create_oval(x - 2, y - 2, x + 2, y + 2, fill=theme["primary"], outline=theme["primary"])

        if secondary_values:
            secondary_points = self._series_points(secondary_values, width, height, pad=38)
            if len(secondary_points) >= 2:
                canvas.create_line(secondary_points, fill="#F53F3F", width=2, dash=(4, 3), smooth=True)
            for x, y in secondary_points[-6:]:
                canvas.create_rectangle(x - 2, y - 2, x + 2, y + 2, fill="#F53F3F", outline="#F53F3F")

        canvas.create_text(42, height - 18, text=primary_label, anchor="w", fill=theme["primary"], font=("Microsoft YaHei UI", 9))
        if secondary_label:
            canvas.create_text(width - 20, height - 18, text=secondary_label, anchor="e", fill="#F53F3F", font=("Microsoft YaHei UI", 9))
        if footer:
            canvas.create_text(width / 2, height - 18, text=footer[:70], anchor="center", fill=theme["muted"], font=("Microsoft YaHei UI", 8))

    def _draw_health_chart(self, canvas: tk.Canvas, diagnostics: dict[str, object] | None, metrics: dict[str, object] | None) -> None:
        theme = self._chart_theme()
        canvas.delete("all")
        width = max(int(canvas.winfo_width() or 420), 320)
        height = max(int(canvas.winfo_height() or 210), 180)
        canvas.create_rectangle(0, 0, width, height, fill=theme["panel"], outline=theme["panel"])
        canvas.create_text(14, 16, text="模型健康度 / 回测诊断", anchor="w", fill=theme["text"], font=("Microsoft YaHei UI", 11, "bold"))

        rolling_rows = (diagnostics or {}).get("rolling_rows", []) if isinstance(diagnostics, dict) else []
        quality = (diagnostics or {}).get("quality", {}) if isinstance(diagnostics, dict) else {}
        latest_hit = 0.0
        learning_quality = 0.0
        latest_error = 0.0
        signal_rate = 0.0
        if isinstance(rolling_rows, list) and rolling_rows:
            weighted_hit = 0.0
            weighted_learning = 0.0
            total_weight = 0.0
            for row, weight in zip(rolling_rows[:3], (0.50, 0.32, 0.18)):
                if isinstance(row, dict):
                    weighted_hit += weight * float(row.get("direction_hit_rate", 0.0) or 0.0)
                    weighted_learning += weight * float(row.get("direction_learning_quality", row.get("direction_hit_rate", 0.0)) or 0.0)
                    total_weight += weight
            latest_hit = weighted_hit / max(total_weight, 1e-8)
            learning_quality = weighted_learning / max(total_weight, 1e-8)
            row = rolling_rows[0] if isinstance(rolling_rows[0], dict) else {}
            latest_error = float(row.get("avg_abs_error", 0.0) or 0.0)
            signal_rate = float(row.get("signal_rate", 0.0) or 0.0)
        sharpe = float((metrics or {}).get("sharpe", 0.0) or 0.0) if isinstance(metrics, dict) else 0.0
        drawdown = abs(float((metrics or {}).get("max_drawdown", 0.0) or 0.0)) if isinstance(metrics, dict) else 0.0
        stability = float((quality or {}).get("pnl_stability", 0.0) or 0.0) if isinstance(quality, dict) else 0.0
        values = [
            ("综合方向", max(0.0, min(latest_hit, 1.0)), "#165DFF"),
            ("学习质量", max(0.0, min(learning_quality, 1.0)), "#13C2C2"),
            ("误差控制", max(0.0, min(1.0 - latest_error / 0.06, 1.0)), "#00B42A"),
            ("夏普评分", max(0.0, min(sharpe / 2.8, 1.0)), "#722ED1"),
            ("回撤控制", max(0.0, min(1.0 - drawdown / 0.15, 1.0)), "#F53F3F"),
            ("收益稳定", max(0.0, min(stability, 1.0)), "#F7BA1E"),
            ("信号活跃", max(0.0, min(signal_rate / 0.35, 1.0)), "#14C9C9"),
        ]
        left = 24
        top = 48
        bar_w = max(22, (width - 60) / len(values) - 10)
        max_h = height - 98
        for idx, (label, score, color) in enumerate(values):
            x0 = left + idx * (bar_w + 10)
            x1 = x0 + bar_w
            y1 = height - 38
            y0 = y1 - max_h * score
            canvas.create_rectangle(x0, top, x1, y1, fill="#EEF2F8" if self.theme_var.get() == "light" else "#242B35", outline="")
            canvas.create_rectangle(x0, y0, x1, y1, fill=color, outline="")
            canvas.create_text((x0 + x1) / 2, y0 - 8, text=f"{score:.0%}", fill=theme["text"], font=("Microsoft YaHei UI", 8, "bold"))
            canvas.create_text((x0 + x1) / 2, height - 22, text=label, fill=theme["muted"], font=("Microsoft YaHei UI", 8))
        canvas.create_text(width / 2, height - 8, text="分数越高越稳健；仅用于投研诊断，不代表未来收益。", anchor="center", fill=theme["muted"], font=("Microsoft YaHei UI", 8))

    def _render_visual_charts(self, result: dict[str, object]) -> None:
        if not hasattr(self, "price_chart") or not hasattr(self, "forecast_chart"):
            return
        raw = result.get("raw") if isinstance(result, dict) else None
        predictions = result.get("predictions") if isinstance(result, dict) else None
        metrics = result.get("metrics", {}) if isinstance(result, dict) else {}
        history = self.current_prediction_history
        evaluation = self.current_prediction_evaluation
        if not isinstance(history, pd.DataFrame) or history.empty:
            history = load_prediction_history(self.paths.output_dir, max_rows=500)
            self.current_prediction_history = history
        eval_path = prediction_evaluation_path(self.paths.output_dir)
        if (not isinstance(evaluation, pd.DataFrame) or evaluation.empty) and eval_path.exists():
            try:
                evaluation = pd.read_csv(eval_path)
                self.current_prediction_evaluation = evaluation
            except Exception:
                evaluation = pd.DataFrame()

        close_values: list[float] = []
        pred_values: list[float] = []
        if isinstance(raw, pd.DataFrame) and not raw.empty:
            close_values = pd.to_numeric(raw["close"].tail(160), errors="coerce").dropna().astype(float).tolist()
        if isinstance(predictions, pd.DataFrame) and not predictions.empty:
            if "pred_center" in predictions.columns:
                pred_series = predictions["pred_center"].tail(160)
            elif {"pred_low", "pred_high"}.issubset(predictions.columns):
                pred_series = (predictions["pred_low"] + predictions["pred_high"]).tail(160) / 2.0
            else:
                pred_series = pd.Series(dtype=float)
            pred_values = pd.to_numeric(pred_series, errors="coerce").dropna().astype(float).tolist()
        self._draw_line_chart(
            self.price_chart,
            title="历史价格走势 + 模型历史中枢",
            primary_values=close_values,
            primary_label="真实收盘价",
            secondary_values=pred_values if pred_values else None,
            secondary_label="历史预测中枢" if pred_values else None,
            footer="使用真实行情缓存/实时叠加数据绘制",
        )

        tomorrow_history = pd.DataFrame()
        if isinstance(history, pd.DataFrame) and not history.empty and "horizon_key" in history.columns:
            tomorrow_history = history[history["horizon_key"].astype(str).eq("tomorrow")].tail(120).copy()
        center_values = pd.to_numeric(tomorrow_history.get("price_center", pd.Series(dtype=float)), errors="coerce").dropna().astype(float).tolist()
        realized_values: list[float] = []
        if isinstance(evaluation, pd.DataFrame) and not evaluation.empty and "horizon_key" in evaluation.columns:
            realized_frame = evaluation[evaluation["horizon_key"].astype(str).eq("tomorrow")].tail(120)
            realized_values = pd.to_numeric(realized_frame.get("realized_close", pd.Series(dtype=float)), errors="coerce").dropna().astype(float).tolist()
        footer = "预测会自动留痕；真实价格出现后自动评估并校准"
        if isinstance(evaluation, pd.DataFrame) and not evaluation.empty:
            recent = evaluation[evaluation["horizon_key"].astype(str).eq("tomorrow")].tail(80) if "horizon_key" in evaluation.columns else evaluation.tail(80)
            if not recent.empty:
                hit = pd.to_numeric(recent.get("direction_hit", pd.Series(dtype=float)), errors="coerce").mean()
                mae = pd.to_numeric(recent.get("center_error_pct", pd.Series(dtype=float)), errors="coerce").abs().mean()
                footer = f"下一交易日历史命中 {hit:.1%} | 中枢平均误差 {mae:.2%}"
        self._draw_line_chart(
            self.forecast_chart,
            title="预测价格中枢留痕 + 真实兑现",
            primary_values=center_values,
            primary_label="预测中枢",
            secondary_values=realized_values if realized_values else None,
            secondary_label="兑现收盘" if realized_values else None,
            footer=footer,
        )
        if hasattr(self, "health_chart"):
            self._draw_health_chart(self.health_chart, self.current_backtest_diagnostics, metrics if isinstance(metrics, dict) else {})

    def _render_live_predictions(self) -> None:
        cards = (self.current_live_predictions or {}).get("cards", {}) if isinstance(self.current_live_predictions, dict) else {}
        for key, label in HORIZON_ORDER:
            payload = cards.get(key, {}) if isinstance(cards, dict) else {}
            if not isinstance(payload, dict) or not payload:
                self.forecast_vars[key]["confidence"].set("置信度：--")
                self.forecast_vars[key]["target"].set("目标窗口：--")
                self.forecast_vars[key]["range"].set(f"{label}：暂无实时预测")
                self.forecast_vars[key]["prob"].set("上涨：-- | 下跌：--")
                self.forecast_vars[key]["driver"].set("核心驱动：尚未加载")
                continue
            calibration = payload.get("calibration", {}) if isinstance(payload.get("calibration"), dict) else {}
            calibration_badge = " | 历史误差校准" if calibration.get("enabled") else ""
            center = float(payload.get("price_center", 0.0) or 0.0)
            self.forecast_vars[key]["confidence"].set(f"置信度：{float(payload.get('confidence', 0.0) or 0.0):.1f}{calibration_badge}")
            self.forecast_vars[key]["target"].set(f"目标窗口：{payload.get('target_label', 'n/a')} | {payload.get('contract_code', 'SN')} | {payload.get('direction_label', 'n/a')}")
            self.forecast_vars[key]["range"].set(f"中枢 {center:.0f} | 区间 {float(payload.get('range_low', 0.0) or 0.0):.0f} - {float(payload.get('range_high', 0.0) or 0.0):.0f} 元/吨")
            self.forecast_vars[key]["prob"].set(f"上涨：{float(payload.get('prob_up', 0.0) or 0.0):.1%} | 下跌：{float(payload.get('prob_down', 0.0) or 0.0):.1%}")
            drivers = payload.get("core_drivers", [])
            driver_text = "，".join(str(item) for item in drivers[:2]) if isinstance(drivers, list) and drivers else "暂无驱动摘要"
            self.forecast_vars[key]["driver"].set(f"核心驱动：{driver_text}")

    def _show_forecast_detail(self, horizon_key: str) -> None:
        detail = build_prediction_detail_report(self.current_live_predictions, horizon_key)
        self._show_text_modal("预测归因详情", detail, width=900, height=680)

    @staticmethod
    def _display_float(value: object, default: float = 0.0) -> float:
        try:
            parsed = float(value)
        except Exception:
            return default
        if pd.isna(parsed):
            return default
        return parsed

    def _fill_tree(self, preds: pd.DataFrame | None = None) -> None:
        for item in self.pred_tree.get_children():
            self.pred_tree.delete(item)
        history = self.current_prediction_history
        if isinstance(history, pd.DataFrame) and not history.empty:
            work = history.copy()
            work["_generated_time"] = pd.to_datetime(work.get("generated_at", pd.Series(index=work.index, dtype=object)), errors="coerce")
            work["_target_time"] = pd.to_datetime(work.get("target_end", pd.Series(index=work.index, dtype=object)), errors="coerce")
            realized = pd.to_numeric(work.get("realized_close", pd.Series(index=work.index, dtype=float)), errors="coerce")
            verified = work[realized.notna()].sort_values("_target_time", ascending=False).head(80)
            pending = work[realized.isna()].sort_values("_generated_time", ascending=False).head(20)
            display = pd.concat([verified, pending], ignore_index=True) if not verified.empty else pending
            if display.empty:
                display = work.sort_values("_generated_time", ascending=False).head(100)
            for _, row in display.iterrows():
                verified_row = pd.notna(pd.to_numeric(pd.Series([row.get("realized_close")]), errors="coerce").iloc[0])
                generated_at = str(row.get("generated_at") or "")[:19].replace("T", " ")
                target_end = str(row.get("target_end") or "")
                anchor_date = str(row.get("anchor_date") or "")
                anchor = target_end if verified_row else generated_at or anchor_date
                target = str(row.get("target_label") or row.get("target_end") or "")
                status = "已验证" if verified_row else "待兑现"
                horizon = f"{row.get('horizon_label') or row.get('horizon_key') or row.get('contract_code') or ''} / {status}"
                conf = self._display_float(row.get("confidence", 0.0))
                prob = self._display_float(row.get("prob_up", 0.5), 0.5)
                expected_return = self._display_float(row.get("expected_return", 0.0))
                low = self._display_float(row.get("range_low", 0.0))
                high = self._display_float(row.get("range_high", 0.0))
                self.pred_tree.insert(
                    "",
                    "end",
                    values=(
                        anchor,
                        target,
                        horizon,
                        f"{conf:.1f}",
                        f"{prob:.1%}",
                        f"{expected_return:.2%}",
                        f"{low:.0f}",
                        f"{high:.0f}",
                    ),
                )
            return

        if not isinstance(preds, pd.DataFrame) or preds.empty:
            return
        for idx, row in preds[::-1].iterrows():
            conf = row.get("confidence_multimodal", row.get("confidence", 0.0))
            prob = row.get("prob_up_multimodal", row.get("prob_up", 0.5))
            target_date = (pd.Timestamp(idx) + pd.offsets.BDay(1)).date()
            self.pred_tree.insert(
                "",
                "end",
                values=(
                    idx.date(),
                    target_date,
                    row.get("regime", "n/a"),
                    f"{self._display_float(conf):.1f}",
                    f"{self._display_float(prob, 0.5):.1%}",
                    f"{self._display_float(row.get('predicted_return', 0.0)):.2%}",
                    f"{self._display_float(row.get('pred_low', 0.0)):.0f}",
                    f"{self._display_float(row.get('pred_high', 0.0)):.0f}",
                ),
            )

    def _factor_summary(
        self,
        features: list[str],
        optimization_summary: dict[str, object] | None = None,
        bandit_summary: dict[str, object] | None = None,
        backtest_diagnostics: dict[str, object] | None = None,
    ) -> str:
        preset = get_preset(self.preset_var.get())
        profile = get_risk_profile(self.profile_var.get())
        optimization_lines = ["自动选模：暂无结果。"]
        if isinstance(optimization_summary, dict) and optimization_summary:
            best = optimization_summary.get("best_config", {})
            optimization_lines = [
                "自动选模：",
                f"- 综合评分：{float(optimization_summary.get('best_score', 0.0) or 0.0):.3f}",
                f"- 训练窗口：{best.get('train_window', 'n/a')}",
                f"- 重训频率：{best.get('retrain_every', 'n/a')}",
                f"- 序列长度：{best.get('seq_len', 'n/a')}",
            ]
            if optimization_summary.get("rollback_applied"):
                optimization_lines.append(f"- 回滚状态：已采用历史最优配置复核回滚（{optimization_summary.get('rollback_reason', '本轮回测更稳')}）")
            else:
                optimization_lines.append(f"- 回滚状态：本轮新配置通过真实回测筛选（候选数 {optimization_summary.get('candidate_count', 'n/a')}）")
        bandit_lines = ["Bandit策略：暂无结果。"]
        if isinstance(bandit_summary, dict) and bandit_summary:
            bandit_lines = [
                "Bandit策略：",
                f"- 最新动作：{bandit_summary.get('latest_action', 'n/a')}",
                f"- 建议仓位系数：{float(bandit_summary.get('latest_position_scale', 1.0) or 1.0):.2f}",
                f"- 置信度阈值：{float(bandit_summary.get('latest_confidence_threshold', 0.0) or 0.0):.1f}",
                f"- 上涨阈值：{float(bandit_summary.get('latest_prob_up_threshold', 0.0) or 0.0):.2f}",
                f"- 下跌阈值：{float(bandit_summary.get('latest_prob_down_threshold', 0.0) or 0.0):.2f}",
            ]
        diagnostic_lines = ["回测诊断：暂无结果。"]
        if isinstance(backtest_diagnostics, dict) and backtest_diagnostics:
            rolling = backtest_diagnostics.get("rolling_rows", [])
            regimes = backtest_diagnostics.get("regime_rows", [])
            quality = backtest_diagnostics.get("quality", {})
            diagnostic_lines = ["回测诊断："]
            if isinstance(rolling, list) and rolling:
                for row in rolling[:3]:
                    if isinstance(row, dict):
                        diagnostic_lines.append(
                            f"- 近{row.get('window', '?')}样本：方向命中 {float(row.get('direction_hit_rate', 0.0) or 0.0):.1%} | "
                            f"学习质量 {float(row.get('direction_learning_quality', row.get('direction_hit_rate', 0.0)) or 0.0):.1%} | "
                            f"平均误差 {float(row.get('avg_abs_error', 0.0) or 0.0):.2%} | 信号率 {float(row.get('signal_rate', 0.0) or 0.0):.1%}"
                        )
            if isinstance(regimes, list) and regimes:
                best_regime = max((row for row in regimes if isinstance(row, dict)), key=lambda row: float(row.get("direction_hit_rate", 0.0) or 0.0), default=None)
                if best_regime:
                    diagnostic_lines.append(f"- 当前最稳状态：{best_regime.get('regime', 'n/a')} | 命中 {float(best_regime.get('direction_hit_rate', 0.0) or 0.0):.1%}")
            if isinstance(quality, dict) and quality:
                diagnostic_lines.append(f"- 月度收益稳定性：{float(quality.get('pnl_stability', 0.0) or 0.0):.1%} | 近10笔胜率：{float(quality.get('latest_10_trade_win_rate', 0.0) or 0.0):.1%}")
        return (
            f"参数模板：{preset.label}\n{preset.description}\n\n"
            f"风险画像：{profile.label}\n{profile.description}\n\n"
            + "\n".join(optimization_lines)
            + "\n\n"
            + "\n".join(bandit_lines)
            + "\n\n"
            + "\n".join(diagnostic_lines)
            + "\n\n"
            + "核心因子栈：\n- "
            + ("\n- ".join(features[:18]) if features else "尚未加载")
        )

    def _render_live_snapshot(self) -> None:
        self.live_text.delete("1.0", "end")
        snapshot = self.current_live_snapshot or {}
        if not snapshot:
            self.live_text.insert("1.0", "实时快照尚未加载。\n\n完成 API 配置或进入仅报价模式后，系统会自动拉取报价、宏观和新闻数据。")
            return

        text_summary = snapshot.get("text_summary", {})
        contract_meta = snapshot.get("contract_meta", {})
        lines = [
            f"生成时间：{snapshot.get('generated_at', 'n/a')}",
            (
                f"目标合约：{contract_meta.get('target_contract', 'n/a')} | 当前主力：{contract_meta.get('active_contract', 'n/a')} | 规则：{contract_meta.get('selection_rule', contract_meta.get('roll_rule', 'n/a'))}"
                if isinstance(contract_meta, dict)
                else "目标合约：n/a"
            ),
            (
                f"训练历史：{contract_meta.get('history_symbol', 'n/a')} | 请求目标：{contract_meta.get('requested_history_symbol', contract_meta.get('active_contract', contract_meta.get('target_contract', 'n/a')))}"
                if isinstance(contract_meta, dict)
                else "训练历史：n/a"
            ),
            f"主导维度：{text_summary.get('dominant_dimension', 'n/a')}",
            f"情绪均值：{float(text_summary.get('sentiment_mean', 0.0) or 0.0):.2f}",
            f"影响均值：{float(text_summary.get('impact_mean', 0.0) or 0.0):.2f}",
            f"热点热度：{float(text_summary.get('topic_heat_score', 0.0) or 0.0):.2f}",
            f"情绪一致性：{float(text_summary.get('news_consensus', 0.0) or 0.0):.2f}",
            "",
            "核心新闻：",
        ]
        hot_topics = text_summary.get("hot_topics", [])
        if isinstance(hot_topics, (list, tuple)) and hot_topics:
            lines.insert(-2, "热点关键词：" + " / ".join(str(item) for item in hot_topics[:6]))
        headlines = text_summary.get("top_headlines", [])
        if isinstance(headlines, (list, tuple)) and headlines:
            lines.extend(f"- {item}" for item in headlines[:3])
        else:
            lines.append("- 当前暂无实时新闻。")

        quotes = pd.DataFrame(snapshot.get("quotes", []))
        if not quotes.empty:
            lines.extend(["", "实时报价：", dataframe_to_text(quotes, index=False, columns=["symbol", "latest", "high", "low", "volume", "open_interest"])])

        liquidity_table = pd.DataFrame(contract_meta.get("liquidity_table", [])) if isinstance(contract_meta, dict) else pd.DataFrame()
        if not liquidity_table.empty:
            lines.extend(["", "主力合约流动性排名：", dataframe_to_text(liquidity_table, index=False, columns=["contract_code", "latest", "volume", "open_interest", "liquidity_score"])])

        v2 = self.current_v2_artifacts or {}
        if isinstance(v2, dict) and v2:
            watermark = v2.get("data_watermark", {}) if isinstance(v2.get("data_watermark"), dict) else {}
            lines.extend(
                [
                    "",
                    "V2 数据水位：",
                    f"- 最新日线：{watermark.get('latest_daily', 'n/a')}",
                    f"- 实时快照：{watermark.get('latest_realtime', 'n/a')}",
                    f"- 使用回退：{'是' if watermark.get('using_fallback') else '否'}",
                    f"- 数据质量分：{float(watermark.get('quality_score', 0.0) or 0.0):.1%}",
                ]
            )

        sources = pd.DataFrame(snapshot.get("source_status", []))
        if not sources.empty:
            lines.extend(["", "数据源状态：", dataframe_to_text(sources, index=False, columns=["name", "success", "from_cache", "message"])])

        lines.extend(["", COMPLIANCE_SMALL])
        self.live_text.insert("1.0", "\n".join(lines))

    def _render_bandit_panel(self) -> None:
        if not hasattr(self, "bandit_text"):
            return
        self.bandit_text.delete("1.0", "end")
        summary = self.current_bandit_summary or {}
        optimization = self.current_optimization_summary or {}
        live_cards = (self.current_live_predictions or {}).get("cards", {}) if isinstance(self.current_live_predictions, dict) else {}
        tomorrow_card = live_cards.get("tomorrow", {}) if isinstance(live_cards, dict) else {}
        lines = ["Bandit / 模型健康面板"]
        if isinstance(summary, dict) and summary:
            action_counts = summary.get("action_counts", {})
            reward_map = summary.get("action_mean_reward", {})
            lines.extend(
                [
                    f"- 最新动作：{summary.get('latest_action', 'n/a')}",
                    f"- 建议仓位系数：{float(summary.get('latest_position_scale', 1.0) or 1.0):.2f}",
                    f"- 置信度阈值：{float(summary.get('latest_confidence_threshold', 0.0) or 0.0):.1f}",
                    f"- 上涨阈值：{float(summary.get('latest_prob_up_threshold', 0.0) or 0.0):.2f}",
                    f"- 下跌阈值：{float(summary.get('latest_prob_down_threshold', 0.0) or 0.0):.2f}",
                ]
            )
            if isinstance(action_counts, dict) and action_counts:
                lines.append("- 动作样本数：" + " | ".join(f"{k}:{v}" for k, v in action_counts.items()))
            if isinstance(reward_map, dict) and reward_map:
                lines.append("- 动作平均奖励：" + " | ".join(f"{k}:{float(v):+.4f}" for k, v in reward_map.items()))
        else:
            lines.append("- 当前暂无 Bandit 结果。")

        if isinstance(optimization, dict) and optimization:
            best = optimization.get("best_config", {})
            lines.extend(
                [
                    "",
                    "自动选模：",
                    f"- 综合评分：{float(optimization.get('best_score', 0.0) or 0.0):.3f}",
                    f"- 训练窗口：{best.get('train_window', 'n/a')}",
                    f"- 重训频率：{best.get('retrain_every', 'n/a')}",
                    f"- 序列长度：{best.get('seq_len', 'n/a')}",
                ]
            )

        eval_summary = self.current_prediction_evaluation_summary or {}
        if isinstance(eval_summary, dict) and eval_summary.get("sample_count", 0):
            lines.extend(["", "预测留痕与自校准："])
            for row in list(eval_summary.get("by_horizon", []) or [])[:4]:
                if not isinstance(row, dict):
                    continue
                lines.append(
                    "- "
                    + f"{row.get('horizon_key', 'n/a')} | 样本 {int(row.get('sample_count', 0) or 0)} | "
                    + f"方向命中 {float(row.get('direction_hit_rate', 0.0) or 0.0):.1%} | "
                    + f"中枢误差 {float(row.get('center_mae_pct', 0.0) or 0.0):.2%}"
                )
        if isinstance(self.current_calibration_profile, dict) and self.current_calibration_profile:
            lines.append("- 校准层：已启用历史误差反馈，自动微调价格中枢、区间宽度与置信度。")

        diagnostics = self.current_backtest_diagnostics or {}
        if isinstance(diagnostics, dict) and diagnostics:
            rolling = diagnostics.get("rolling_rows", [])
            quality = diagnostics.get("quality", {})
            lines.extend(["", "回测健康诊断："])
            if isinstance(rolling, list) and rolling:
                for row in rolling[:3]:
                    if isinstance(row, dict):
                        lines.append(
                            f"- 近{row.get('window', '?')}样本：方向命中 {float(row.get('direction_hit_rate', 0.0) or 0.0):.1%} | "
                            f"误差 {float(row.get('avg_abs_error', 0.0) or 0.0):.2%} | 信号率 {float(row.get('signal_rate', 0.0) or 0.0):.1%}"
                        )
            if isinstance(quality, dict) and quality:
                lines.append(f"- 收益稳定性 {float(quality.get('pnl_stability', 0.0) or 0.0):.1%} | 近10笔交易胜率 {float(quality.get('latest_10_trade_win_rate', 0.0) or 0.0):.1%}")

        memory = self.current_model_memory or {}
        if isinstance(memory, dict) and memory:
            lines.extend(["", f"模型记忆更新时间：{memory.get('updated_at', 'n/a')}"])

        if isinstance(tomorrow_card, dict) and tomorrow_card:
            lines.extend(
                [
                    "",
                    "明日主预测：",
                    f"- 主力合约：{tomorrow_card.get('contract_code', 'SN')}",
                    f"- 目标窗口：{tomorrow_card.get('target_label', 'n/a')}",
                    f"- 中枢价格：{float(tomorrow_card.get('price_center', 0.0) or 0.0):.0f}",
                    f"- 上涨概率：{float(tomorrow_card.get('prob_up', 0.0) or 0.0):.2%}",
                    f"- 置信度：{float(tomorrow_card.get('confidence', 0.0) or 0.0):.1f}",
                ]
            )

        v2 = self.current_v2_artifacts or {}
        if isinstance(v2, dict) and v2:
            health = v2.get("model_health", {}) if isinstance(v2.get("model_health"), dict) else {}
            watermark = v2.get("data_watermark", {}) if isinstance(v2.get("data_watermark"), dict) else {}
            direction = v2.get("direction_first", {}) if isinstance(v2.get("direction_first"), dict) else {}
            registry = v2.get("model_registry", []) if isinstance(v2.get("model_registry"), list) else []
            model_status = registry[0].get("status", "n/a") if registry and isinstance(registry[0], dict) else "n/a"
            lines.extend(
                [
                    "",
                    "V2 研究流水线：",
                    f"- 模型注册状态：{model_status}",
                    f"- 综合健康度：{float(health.get('overall_score', 0.0) or 0.0):.1%}",
                    f"- 真实方向命中：{float(health.get('true_direction_hit_rate', 0.0) or 0.0):.1%}",
                    f"- 明确方向占比：{float(health.get('direction_active_rate', 0.0) or 0.0):.1%} | 中性占比：{float(health.get('neutral_rate', 0.0) or 0.0):.1%}",
                    f"- 区间覆盖率：{float(health.get('interval_coverage_rate', 0.0) or 0.0):.1%}",
                    f"- 中枢误差：{float(health.get('center_mae_pct', 0.0) or 0.0):.2%}",
                    f"- 数据质量：{float(watermark.get('quality_score', 0.0) or 0.0):.1%} | 最新日线：{watermark.get('latest_daily', 'n/a')}",
                    f"- 方向一致性闸门：{direction.get('latest_state', 'n/a')} | 候选：{direction.get('latest_candidate', 'n/a')}",
                ]
            )

        lines.extend(["", COMPLIANCE_SMALL])
        self.bandit_text.insert("1.0", "\n".join(lines))

    def _render_scenarios(self) -> None:
        self.scenario_text.delete("1.0", "end")
        if isinstance(self.current_scenario_matrix, pd.DataFrame) and not self.current_scenario_matrix.empty:
            show = self.current_scenario_matrix[["scenario_label", "expected_return", "prob_up", "confidence", "risk_level"]].copy()
            show["expected_return"] = show["expected_return"].map(lambda v: f"{v:.2%}")
            show["prob_up"] = show["prob_up"].map(lambda v: f"{v:.2%}")
            show["confidence"] = show["confidence"].map(lambda v: f"{v:.1f}")
            text = ["情景矩阵：", dataframe_to_text(show, index=False)]
            if self.current_position_risk:
                text.extend(
                    [
                        "",
                        f"95% VaR：{self.current_position_risk.get('var_95', 0.0):.0f}",
                        f"压力 VaR：{self.current_position_risk.get('stressed_var', 0.0):.0f}",
                        f"保证金占用率：{self.current_position_risk.get('margin_usage_ratio', 0.0):.2%}",
                    ]
                )
            text.extend(["", COMPLIANCE_SMALL])
            self.scenario_text.insert("1.0", "\n".join(text))
        else:
            self.scenario_text.insert("1.0", "情景矩阵暂不可用。\n\n请先运行一次完整或短刷新预测。")

    def _load_reports(self, manifest: list[dict[str, str]] | None = None) -> None:
        if manifest is None:
            manifest_path = self.paths.report_dir / "report_manifest.json"
            if manifest_path.exists():
                manifest = pd.read_json(manifest_path).to_dict(orient="records")
            else:
                manifest = []
        self.report_manifest = manifest
        for item in self.report_tree.get_children():
            self.report_tree.delete(item)
        type_map = {"daily": "日报", "weekly": "周报", "monthly": "月报", "event": "事件报告"}
        for i, item in enumerate(manifest):
            report_type = str(item.get("report_type", ""))
            self.report_tree.insert("", "end", iid=str(i), values=(type_map.get(report_type, report_type), item["generated_at"]))
        self._preview_report()

    def _preview_report(self) -> None:
        self.report_text.delete("1.0", "end")
        if not self.report_manifest:
            self.report_text.insert("1.0", "当前还没有生成报告。")
            return
        selection = self.report_tree.selection()
        item = self.report_manifest[int(selection[0])] if selection else self.report_manifest[0]
        path = Path(item["path"])
        self.report_text.insert("1.0", path.read_text(encoding="utf-8", errors="ignore") if path.exists() else "报告文件缺失。")

    def _load_docs(self) -> None:
        path = self.doc_paths[self.doc_choice.get()]
        self.docs_text.delete("1.0", "end")
        self.docs_text.insert("1.0", path.read_text(encoding="utf-8", errors="ignore"))

    def _load_existing_outputs(self) -> None:
        pred_path = self.output_dir / "sn_predictions.csv"
        live_path = self.output_dir / "sn_live_snapshot.json"
        scenario_path = self.output_dir / "sn_scenario_matrix.csv"
        bandit_path = self.output_dir / "sn_bandit_summary.json"
        live_predictions_path = self.paths.live_predictions_path
        evaluation_path = prediction_evaluation_path(self.paths.output_dir)
        memory_path = model_memory_path(self.paths.output_dir)
        self.current_v2_artifacts = load_v2_artifacts(self.paths.output_dir)

        if live_path.exists():
            try:
                self.current_live_snapshot = json.loads(live_path.read_text(encoding="utf-8"))
            except Exception:
                self.current_live_snapshot = None
        if live_predictions_path.exists():
            try:
                self.current_live_predictions = json.loads(live_predictions_path.read_text(encoding="utf-8"))
            except Exception:
                self.current_live_predictions = None
        if scenario_path.exists():
            try:
                self.current_scenario_matrix = pd.read_csv(scenario_path).set_index("scenario_key")
            except Exception:
                self.current_scenario_matrix = pd.DataFrame()
        if bandit_path.exists():
            try:
                self.current_bandit_summary = json.loads(bandit_path.read_text(encoding="utf-8"))
            except Exception:
                self.current_bandit_summary = None
        if memory_path.exists():
            try:
                self.current_model_memory = json.loads(memory_path.read_text(encoding="utf-8"))
                calibration = self.current_model_memory.get("calibration_profile", {}) if isinstance(self.current_model_memory, dict) else {}
                if isinstance(calibration, dict):
                    self.current_calibration_profile = calibration
            except Exception:
                self.current_model_memory = None
        self.current_prediction_history = load_prediction_history(self.paths.output_dir, max_rows=500)
        if evaluation_path.exists():
            try:
                self.current_prediction_evaluation = pd.read_csv(evaluation_path)
            except Exception:
                self.current_prediction_evaluation = pd.DataFrame()

        if pred_path.exists():
            preds = pd.read_csv(pred_path)
            preds["date"] = pd.to_datetime(preds["date"])
            preds = preds.set_index("date")
            self.current_result = {
                "predictions": preds,
                "metrics": {},
                "signals": pd.DataFrame(),
                "selected_features": [],
                "report_manifest": self.report_manifest,
                "live_snapshot": self.current_live_snapshot,
                "live_predictions": self.current_live_predictions,
                "scenario_matrix": self.current_scenario_matrix,
                "position_risk": self.current_position_risk,
                "prediction_history": self.current_prediction_history,
                "prediction_evaluation": self.current_prediction_evaluation,
                "calibration_profile": self.current_calibration_profile,
                "model_memory": self.current_model_memory,
                "v2_artifacts": self.current_v2_artifacts,
            }
            self._render_result(self.current_result)
            self.status_var.set("已从磁盘加载最近一次输出结果。")
        else:
            self._render_live_predictions()
            self._render_visual_charts({})
            self._render_live_snapshot()
            self._render_bandit_panel()
            self._render_scenarios()

    def _ask(self, preset_question: str | None = None) -> None:
        question = preset_question or self.question_entry.get().strip()
        self.answer_text.delete("1.0", "end")
        self.answer_text.insert("1.0", answer_question(question, self.current_result, self.doc_paths))
        if not preset_question:
            self.question_entry.delete(0, "end")

    def _save_ui_settings(self) -> None:
        refresh_minutes = max(10, self._safe_int_var(self.refresh_minutes_var, 10))
        stress_contracts = max(1, self._safe_int_var(self.stress_contracts_var, 1))
        font_scale = max(90, min(130, self._safe_int_var(self.font_scale_var, 100)))
        self.refresh_minutes_var.set(refresh_minutes)
        self.stress_contracts_var.set(stress_contracts)
        self.font_scale_var.set(font_scale)
        self.settings = AppSettings(
            theme=self.theme_var.get(),
            user_mode=self.mode_var.get(),
            selected_preset=self.preset_var.get(),
            selected_risk_profile=self.profile_var.get(),
            compute_profile=self.compute_profile_var.get(),
            default_report_type=self.report_type_var.get(),
            layout_locked=self.settings.layout_locked,
            auto_backup=bool(self.auto_backup_var.get()),
            qna_enabled=bool(self.qna_enabled_var.get()),
            voice_alerts=bool(self.voice_alerts_var.get()),
            font_scale=font_scale,
            live_data_enabled=bool(self.live_enabled_var.get()),
            cache_only_mode=bool(self.cache_only_var.get()),
            live_refresh_seconds=max(600, refresh_minutes * 60),
            stress_test_contracts=stress_contracts,
            sina_symbols=self.settings.sina_symbols,
        )
        save_settings(self.settings)
        self._apply_theme()
        self._apply_mode()
        self._refresh_settings_text()
        self._schedule_refresh_jobs()
        self.status_var.set("界面设置已保存。")

    @staticmethod
    def _safe_int_var(variable: tk.Variable, default: int) -> int:
        try:
            return int(variable.get())
        except Exception:
            return default

    def _selected_optimization_level(self) -> str:
        selected = str(self.compute_profile_var.get() or "auto").strip().lower()
        if selected in {"auto", "fast", "balanced", "full", "gpu_full"}:
            return selected
        return "auto"

    def _save_settings_and_refresh(self) -> None:
        self._save_ui_settings()
        self._start_live_prediction_pipeline(
            refresh_scope="all",
            reason="manual",
            csv_path=self.current_csv_path,
            optimization_level=self._selected_optimization_level(),
        )

    def _apply_mode(self) -> None:
        advanced = "normal" if self.mode_var.get() == "professional" else "disabled"
        self.nav_buttons["assistant"].configure(state=advanced)

    def _refresh_settings_text(self) -> None:
        backups = list_backups()
        api_state = missing_api_keys()
        disk_note = self._disk_space_note() or "未知"
        try:
            preset = get_preset(self.preset_var.get())
            self.preset_detail_var.set(
                f"参数模板：{preset.label} | 置信度≥{preset.confidence_threshold:.0f} | 上涨阈值 {preset.prob_up_threshold:.2f} | 单笔风险 {preset.single_trade_risk_pct:.2%}"
            )
        except Exception:
            self.preset_detail_var.set("参数模板：当前选择暂不可解析。")
        try:
            profile = get_risk_profile(self.profile_var.get())
            self.profile_detail_var.set(f"风险画像：{profile.label} | {profile.description}")
        except Exception:
            self.profile_detail_var.set("风险画像：当前选择暂不可解析。")
        compute_map = {
            "fast": "算力档位：快速，适合普通办公电脑；使用轻量候选和历史最优回滚，优先稳定不卡顿。",
            "balanced": "算力档位：平衡，默认使用快速刷新逻辑，但保留模型记忆与回滚校验。",
            "full": "算力档位：全量，适合高性能电脑；手动/定时刷新会跑更多回测候选，耗时更长。",
        }
        self.compute_detail_var.set(compute_map.get(self.compute_profile_var.get(), compute_map["balanced"]))
        self.settings_text.configure(state="normal")
        self.settings_text.delete("1.0", "end")
        self.settings_text.insert(
            "1.0",
            (
                f"主题: {self.theme_var.get()}\n"
                f"模式: {self.mode_var.get()}\n"
                f"参数模板: {self.preset_var.get()}\n"
                f"风险画像: {self.profile_var.get()}\n"
                f"算力档位: {self.compute_profile_var.get()}\n"
                f"自动备份: {bool(self.auto_backup_var.get())}\n"
                f"字体缩放: {self._safe_int_var(self.font_scale_var, 100)}%\n"
                f"启用实时数据: {bool(self.live_enabled_var.get())}\n"
                f"仅缓存模式: {bool(self.cache_only_var.get())}\n"
                f"下一小时刷新分钟数: {self._safe_int_var(self.refresh_minutes_var, 10)}\n"
                f"压力测试手数: {max(1, self._safe_int_var(self.stress_contracts_var, 1))}\n"
                f"输出目录: {self.output_dir}\n"
                f"磁盘空间: {disk_note}\n"
                f"缺失 API: {', '.join(api_state) if api_state else '无'}\n\n"
                "最近备份：\n- " + ("\n- ".join(path.name for path in backups) if backups else "无")
            ),
        )
        self.settings_text.configure(state="disabled")
        self.backup_list.delete(0, "end")
        for backup in backups:
            self.backup_list.insert("end", backup.name)

    def _schedule_refresh_jobs(self) -> None:
        if self.short_refresh_job is not None:
            self.after_cancel(self.short_refresh_job)
            self.short_refresh_job = None
        if self.daily_refresh_job is not None:
            self.after_cancel(self.daily_refresh_job)
            self.daily_refresh_job = None
        if not self.live_enabled_var.get():
            return
        short_ms = max(600, int(self.refresh_minutes_var.get()) * 60) * 1000
        self.short_refresh_job = self.after(short_ms, self._auto_refresh_short)
        now = datetime.now()
        target = now.replace(hour=15, minute=10, second=0, microsecond=0)
        if target <= now:
            target = target + timedelta(days=1)
        delay_ms = max(60_000, int((target - now).total_seconds() * 1000))
        self.daily_refresh_job = self.after(delay_ms, self._auto_refresh_daily)

    def _auto_refresh_short(self) -> None:
        self.short_refresh_job = None
        if not self.pipeline_busy and self.live_enabled_var.get():
            refresh_scope = "all" if self._should_force_full_refresh() else "short"
            self._start_live_prediction_pipeline(
                refresh_scope=refresh_scope,
                reason="scheduled",
                csv_path=self.current_csv_path,
                optimization_level=self._selected_optimization_level(),
            )
        self._schedule_refresh_jobs()

    def _auto_refresh_daily(self) -> None:
        self.daily_refresh_job = None
        if not self.pipeline_busy and self.live_enabled_var.get():
            self._start_live_prediction_pipeline(refresh_scope="all", reason="scheduled", csv_path=self.current_csv_path, optimization_level=self._selected_optimization_level())
        self._schedule_refresh_jobs()

    def _run_stress_test(self) -> None:
        if (
            not self.current_result
            or not isinstance(self.current_result.get("predictions"), pd.DataFrame)
            or not isinstance(self.current_result.get("raw"), pd.DataFrame)
        ):
            self.status_var.set("请先运行实时预测，再生成情景矩阵。")
            return
        self.current_scenario_matrix = build_scenario_matrix(
            self.current_result["predictions"],  # type: ignore[index]
            self.current_result["raw"],  # type: ignore[index]
            risk=self.current_result.get("risk_config"),  # type: ignore[arg-type]
            contracts=max(1, int(self.stress_contracts_var.get())),
            live_snapshot=self.current_live_snapshot,
        )
        self.current_position_risk = build_position_risk_snapshot(
            self.current_result["predictions"],  # type: ignore[index]
            risk=self.current_result.get("risk_config"),  # type: ignore[arg-type]
            contracts=max(1, int(self.stress_contracts_var.get())),
        )
        if isinstance(self.current_result, dict):
            self.current_result["scenario_matrix"] = self.current_scenario_matrix
            self.current_result["position_risk"] = self.current_position_risk
        self._render_scenarios()
        self.status_var.set("情景压力矩阵已刷新。")

    def _backup_data(self, silent: bool = False) -> None:
        if self._disk_space_is_low():
            if not silent:
                self.status_var.set(f"磁盘空间偏低，已跳过备份。{self._disk_space_note()}")
            return
        try:
            backup = create_backup("manual" if not silent else "autorun")
        except Exception as exc:
            if not silent:
                self.status_var.set(f"备份失败：{exc}")
            return
        self._refresh_settings_text()
        if not silent:
            self.status_var.set(f"备份已创建：{backup.name}")

    def _switch_best_preset(self) -> None:
        metrics = self.current_result.get("metrics", {}) if self.current_result else {}
        target = "balanced"
        if isinstance(metrics, dict) and metrics:
            if metrics.get("max_drawdown", 0.0) < -0.08 or metrics.get("win_rate", 0.0) < 0.52:
                target = "conservative"
            elif metrics.get("sharpe", 0.0) > 1.0 and metrics.get("reward_risk_ratio", 0.0) > 1.5:
                target = "aggressive"
        self.preset_var.set(target)
        self._save_ui_settings()
        self.status_var.set(f"已切换到启发式最优参数模板：{target}。")

    def _restore_defaults(self) -> None:
        self.theme_var.set("light")
        self.mode_var.set("ordinary")
        self.preset_var.set("balanced")
        self.profile_var.set("balanced")
        self.settings = AppSettings()
        self.compute_profile_var.set(self.settings.compute_profile)
        self.report_type_var.set(self.settings.default_report_type)
        self.auto_backup_var.set(self.settings.auto_backup)
        self.qna_enabled_var.set(self.settings.qna_enabled)
        self.voice_alerts_var.set(self.settings.voice_alerts)
        self.font_scale_var.set(self.settings.font_scale)
        self.live_enabled_var.set(self.settings.live_data_enabled)
        self.cache_only_var.set(self.settings.cache_only_mode)
        self.stress_contracts_var.set(self.settings.stress_test_contracts)
        self.refresh_minutes_var.set(int(self.settings.live_refresh_seconds // 60))
        self._save_ui_settings()
        self.status_var.set("默认设置已恢复。")

    def _toggle_focus(self) -> None:
        self.attributes("-fullscreen", not bool(self.attributes("-fullscreen")))

    def _show_text_modal(self, title: str, content: str, width: int = 760, height: int = 520) -> None:
        if self.generic_modal is not None and self.generic_modal.winfo_exists():
            self.generic_modal.destroy()
        modal = tk.Toplevel(self)
        modal.title(title)
        modal.transient(self)
        modal.geometry(f"{width}x{height}")
        modal.grab_set()
        body = tk.Frame(modal, padx=14, pady=14)
        body.pack(fill="both", expand=True)
        text_holder = ttk.Frame(body)
        text_holder.pack(fill="both", expand=True)
        text = tk.Text(text_holder, wrap="word", relief="solid")
        scroll = ttk.Scrollbar(text_holder, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        text.insert("1.0", content)
        text.configure(state="disabled")
        tk.Button(body, text="关闭", command=modal.destroy).pack(anchor="e", pady=(8, 0))
        self.generic_modal = modal
        self._apply_theme()

    def _shutdown_app(self) -> None:
        if self.pipeline_process is not None and self.pipeline_process.poll() is None:
            try:
                self.pipeline_process.kill()
            except Exception:
                pass
        self._cleanup_pipeline_files()
        self.destroy()

    @staticmethod
    def _open_path(path: str | Path) -> None:
        try:
            os.startfile(str(path))
        except Exception:
            pass


def main() -> None:
    if "--live-worker" in os.sys.argv:
        code = run_live_worker_from_argv(os.sys.argv)
        os._exit(code)
    if "--smoke-test" in os.sys.argv:
        marker = get_user_output_dir().parent / "smoke_test_ok.txt"
        marker.write_text(f"ok {datetime.now().isoformat()}", encoding="utf-8")
        os._exit(0)
    if "--headless-run-demo" in os.sys.argv:
        run_pipeline()
        os._exit(0)
    app = SNInsightTerminal()
    app.mainloop()
