from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.api.json_utils import safe_json_dumps
from sn_futures.api.terminal_api import TERMINAL_API_DOCS, handle_terminal_api


class TerminalCandidateDiagnosticsApiTest(unittest.TestCase):
    def test_candidate_diagnostics_endpoint_is_available_and_json_safe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = Path(tmp) / "outputs" / "model_registry"
            output.mkdir(parents=True, exist_ok=True)
            (output / "candidate_training_status.json").write_text(
                json.dumps({"status": "success", "metrics_by_horizon": {}, "records": []}, ensure_ascii=False),
                encoding="utf-8",
            )
            status, payload = handle_terminal_api("/api/terminal/models/candidate-diagnostics", "GET", {}, None)
        self.assertEqual(status, 200)
        self.assertIn("horizons", payload)
        dumped = safe_json_dumps(payload)
        self.assertNotIn("NaN", dumped)

    def test_docs_include_candidate_diagnostics_endpoint(self) -> None:
        paths = {row["path"] for row in TERMINAL_API_DOCS["endpoints"]}
        self.assertIn("/api/terminal/models/candidate-diagnostics", paths)


if __name__ == "__main__":
    unittest.main()
