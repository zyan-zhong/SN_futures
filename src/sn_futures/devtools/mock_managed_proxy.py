from __future__ import annotations

import json
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


def _rows(symbol: str = "SN") -> list[dict[str, object]]:
    today = date.today()
    rows: list[dict[str, object]] = []
    for idx in range(90):
        day = today - timedelta(days=90 - idx)
        rows.append(
            {
                "trade_date": day.isoformat(),
                "symbol": symbol,
                "spot_price": 260000 + idx,
                "spot_premium": 500 + idx,
                "spot_futures_basis": 300 + idx,
                "shfe_inventory": 8000 + idx,
                "shfe_warehouse_receipt": 4200 + idx,
                "lme_tin_close": 33500 + idx,
                "lme_inventory": 4700 + idx,
                "near_contract": "SN2606",
                "far_contract": "SN2607",
                "near_contract_close": 259800 + idx,
                "far_contract_close": 259200 + idx,
                "near_open_interest": 42000 + idx,
                "far_open_interest": 36000 + idx,
                "main_contract": "SN2606",
                "main_contract_switch_flag": 0,
            }
        )
    return rows


class MockManagedProxyHandler(BaseHTTPRequestHandler):
    def _send(self, payload: dict[str, object], status: int = 200) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:  # noqa: N802
        token = self.headers.get("X-SN-License-Token", "")
        if not token:
            self._send({"status": "token_missing", "message_zh": "missing license token"}, status=401)
            return
        parsed = urlparse(self.path)
        if parsed.path == "/api/sn/status":
            self._send({"status": "success", "service": "mock_managed_proxy", "sample_data_used": True})
            return
        if parsed.path == "/api/sn/fundamentals/latest":
            self._send({"status": "success", "rows": _rows()[-1:]})
            return
        if parsed.path == "/api/sn/fundamentals/history":
            query = parse_qs(parsed.query)
            symbol = str((query.get("symbol") or ["SN"])[0]).upper()
            self._send({"status": "success", "rows": _rows(symbol)})
            return
        self._send({"status": "not_found"}, status=404)

    def log_message(self, format: str, *args: object) -> None:
        return


def run(host: str = "127.0.0.1", port: int = 8788) -> None:
    server = ThreadingHTTPServer((host, port), MockManagedProxyHandler)
    print(f"mock managed proxy listening on http://{host}:{port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Start local mock managed data proxy for development tests.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8788)
    args = parser.parse_args()
    run(host=args.host, port=args.port)
