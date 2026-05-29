from __future__ import annotations

import tempfile
import threading
import unittest
from contextlib import contextmanager
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import urlopen

from sn_futures import api_server


@contextmanager
def running_server(**patches):
    patchers = [patch(f"sn_futures.api_server.{name}", value) for name, value in patches.items()]
    for item in patchers:
        item.start()
    server = ThreadingHTTPServer(("127.0.0.1", 0), api_server.V2ApiHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        for item in reversed(patchers):
            item.stop()


class TerminalStaticHostingTest(unittest.TestCase):
    def test_terminal_missing_dist_returns_chinese_hint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with running_server(_frontend_dist_root=lambda: root) as base:
                with urlopen(f"{base}/terminal", timeout=10) as response:
                    body = response.read().decode("utf-8")
            self.assertIn("专业前端尚未构建", body)
            self.assertIn("/api/terminal/docs", body)
            self.assertIn("/legacy", body)

    def test_terminal_slash_missing_dist_returns_hint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with running_server(_frontend_dist_root=lambda: root) as base:
                with urlopen(f"{base}/terminal/", timeout=10) as response:
                    body = response.read().decode("utf-8")
            self.assertIn("专业前端尚未构建", body)

    def test_legacy_route_returns_old_ui(self) -> None:
        with running_server() as base:
            with urlopen(f"{base}/legacy", timeout=10) as response:
                body = response.read().decode("utf-8")
        self.assertIn("<html", body.lower())

    def test_path_traversal_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "index.html").write_text("<html>ok</html>", encoding="utf-8")
            with running_server(_frontend_dist_root=lambda: root) as base:
                with self.assertRaises(HTTPError) as caught:
                    urlopen(f"{base}/terminal/%2e%2e/.env", timeout=10)
            self.assertEqual(caught.exception.code, 403)
            body = caught.exception.read().decode("utf-8")
        self.assertNotIn(str(Path.cwd()), body)
        self.assertNotIn("SN_ALPHA_VANTAGE_KEY", body)

    def test_static_mime_type_mapping(self) -> None:
        cases = {
            "index.html": "text/html; charset=utf-8",
            "app.js": "application/javascript; charset=utf-8",
            "style.css": "text/css; charset=utf-8",
            "data.json": "application/json; charset=utf-8",
            "icon.svg": "image/svg+xml",
            "image.png": "image/png",
            "favicon.ico": "image/x-icon",
        }
        for name, expected in cases.items():
            self.assertEqual(api_server._static_mime_type(Path(name)), expected)

    def test_terminal_can_serve_fake_dist_index_and_asset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "assets").mkdir()
            (root / "index.html").write_text("<html><body>fake terminal</body></html>", encoding="utf-8")
            (root / "assets" / "app.js").write_text("console.log('ok')", encoding="utf-8")
            with running_server(_frontend_dist_root=lambda: root) as base:
                with urlopen(f"{base}/terminal", timeout=10) as response:
                    index_body = response.read().decode("utf-8")
                    index_type = response.headers.get("Content-Type")
                with urlopen(f"{base}/terminal/assets/app.js", timeout=10) as response:
                    asset_body = response.read().decode("utf-8")
                    asset_type = response.headers.get("Content-Type")
        self.assertIn("fake terminal", index_body)
        self.assertIn("text/html", index_type or "")
        self.assertIn("console.log", asset_body)
        self.assertIn("application/javascript", asset_type or "")

    def test_terminal_docs_still_available(self) -> None:
        with running_server() as base:
            with urlopen(f"{base}/api/terminal/docs", timeout=10) as response:
                body = response.read().decode("utf-8")
        self.assertIn("/api/terminal/summary", body)


if __name__ == "__main__":
    unittest.main()
