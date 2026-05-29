from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

if __name__ == "__main__":
    if "--api-server" in sys.argv:
        import os

        from sn_futures.api_server import run_api_server

        if "--api-port" in sys.argv:
            index = sys.argv.index("--api-port")
            if index + 1 < len(sys.argv):
                os.environ["SN_TERMINAL_API_PORT"] = sys.argv[index + 1]
        run_api_server()
    elif "--live-worker" in sys.argv:
        from sn_futures.desktop_app import main

        main()
    else:
        import ctypes
        import atexit

        from sn_futures.bootstrap.runtime_guard import SingleInstanceLock, read_runtime_state

        lock = SingleInstanceLock()
        if not lock.acquire():
            state = read_runtime_state()
            message = (
                "SNInsightTerminal 已经在运行。\n\n"
                f"PID：{state.get('active_pid', '未知')}\n"
                f"端口：{state.get('api_port', '未知')}\n"
                f"版本：{state.get('build_id', '未知')}\n\n"
                "请先关闭已有窗口，或使用当前正在运行的终端。"
            )
            try:
                ctypes.windll.user32.MessageBoxW(None, message, "SNInsightTerminal 单实例保护", 0x40)
            except Exception:
                print(message)
            sys.exit(0)
        atexit.register(lock.release)
        from sn_futures.desktop_app import main

        main()
