from __future__ import annotations

import argparse
import logging
import os
import sys
import threading
import time
import webbrowser
from pathlib import Path

if __package__ in {None, ""}:  # PyInstaller/script entry compatibility.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from sn_futures.private_bundle_keys import import_private_bundle_keys_if_needed
    from sn_futures.server_runtime import choose_available_port, run_server, wait_for_server
    from sn_futures.user_data import initialize_user_data_dir, settings_path, user_config_path, user_path
else:
    from .private_bundle_keys import import_private_bundle_keys_if_needed
    from .server_runtime import choose_available_port, run_server, wait_for_server
    from .user_data import initialize_user_data_dir, settings_path, user_config_path, user_path


def _configure_logging(debug: bool = False) -> Path:
    initialize_user_data_dir()
    log_path = user_path("logs", "launcher.log")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=str(log_path),
        level=logging.DEBUG if debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        encoding="utf-8",
        force=True,
    )
    return log_path


def _reset_default_config_files() -> None:
    """Reset non-secret user config files while preserving secrets and runtime data."""
    for path in (settings_path(), user_config_path()):
        if path.exists():
            path.unlink()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SNInsightTerminal 桌面启动器")
    parser.add_argument("--port", type=int, default=0, help="指定 API 端口；默认自动选择 8765-8769")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    parser.add_argument("--reset-config", action="store_true", help="重新初始化默认配置")
    parser.add_argument("--legacy", action="store_true", help="打开旧版终端")
    parser.add_argument("--debug", action="store_true", help="启用调试日志")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.reset_config:
        _reset_default_config_files()
    info = initialize_user_data_dir()
    log_path = _configure_logging(args.debug)
    logging.info("启动 SNInsightTerminal，用户数据目录：%s", info.get("root"))
    bundle_import = import_private_bundle_keys_if_needed()
    if isinstance(bundle_import, dict):
        for item in bundle_import.get("imported", []):
            if isinstance(item, dict):
                logging.info("已导入发行方预配置 key：%s %s", item.get("name"), item.get("masked"))

    host = "127.0.0.1"
    try:
        port = args.port or choose_available_port(host=host, preferred=8765, end=8769)
    except Exception as exc:
        print(f"端口选择失败：{exc}", file=sys.stderr)
        logging.exception("端口选择失败")
        return 2
    os.environ["SN_TERMINAL_HOST"] = host
    os.environ["SN_TERMINAL_PORT"] = str(port)
    os.environ["SN_TERMINAL_API_BASE_URL"] = f"http://{host}:{port}"

    thread = threading.Thread(target=run_server, kwargs={"host": host, "port": port}, daemon=True)
    thread.start()

    docs_url = f"http://{host}:{port}/api/terminal/docs"
    health_url = f"http://{host}:{port}/api/terminal/system-health"
    target_path = "/legacy" if args.legacy else "/terminal"
    target_url = f"http://{host}:{port}{target_path}"

    # The docs endpoint is the hard readiness gate. System-health can be slower on
    # packaged cold starts, so a delayed health response must not terminate the app.
    if not wait_for_server(docs_url, timeout=60):
        print(f"后端启动超时，请查看日志：{log_path}", file=sys.stderr)
        logging.error("后端 API 文档检查超时：%s", docs_url)
        return 3
    if not wait_for_server(health_url, timeout=30):
        logging.warning("系统健康接口暂未就绪，但 API 已启动，将继续运行：%s", health_url)

    print("SNInsightTerminal 已启动")
    print(f"专业终端：{target_url}")
    print(f"Terminal API 文档：{docs_url}")
    print(f"日志文件：{log_path}")
    if not args.no_browser:
        webbrowser.open(target_url)

    try:
        while thread.is_alive():
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("收到退出请求，正在关闭。")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
