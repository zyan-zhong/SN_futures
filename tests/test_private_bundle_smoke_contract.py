from __future__ import annotations

import unittest
from pathlib import Path


class InstallerSmokeContractTest(unittest.TestCase):
    def test_smoke_script_uses_isolated_data_dir_and_no_private_bundle_success_path(self) -> None:
        script = Path("packaging/smoke_installed.ps1").read_text(encoding="utf-8")

        self.assertIn("[string]$InstalledRoot", script)
        self.assertIn("[string]$DataDir", script)
        self.assertIn("[switch]$UseTempDataDir", script)
        self.assertIn("[int]$ApiPort", script)
        self.assertIn("[int]$TimeoutSeconds", script)
        self.assertIn("SN_DATA_DIR", script)
        self.assertIn("SN_INSIGHT_DATA_DIR", script)
        self.assertIn("SN_DISABLE_AUTO_SCHEDULER", script)
        self.assertIn("SN_LOCAL_API_PROVIDER_ENABLED", script)
        self.assertIn("ExpectPrivateBundleKeys is disabled", script)
        self.assertNotIn("private bundle Alpha Vantage key is configured", script)
        self.assertNotIn("reset restores or retains Alpha Vantage private default", script)
        self.assertNotIn("/api/terminal/newsapi/test", script)

    def test_smoke_script_checks_empty_unconfigured_terminal_contract(self) -> None:
        script = Path("packaging/smoke_installed.ps1").read_text(encoding="utf-8")

        self.assertIn("/api/terminal/docs", script)
        self.assertIn("/terminal", script)
        self.assertIn("/api/terminal/data-status", script)
        self.assertIn("/api/terminal/settings/status", script)
        self.assertIn("/api/terminal/predictions", script)
        self.assertIn("alpha_vantage_configured", script)
        self.assertIn("newsapi_configured", script)
        self.assertIn("tushare_configured", script)
        self.assertIn("local_api_provider_configured", script)
        self.assertIn("predictions blocked or empty without provider keys", script)
        self.assertIn("sample_data_used", script)
        self.assertIn("baseline_used", script)
        self.assertIn("customer_prediction_generated", script)
        self.assertIn("/api/terminal/system/shutdown", script)
        self.assertIn("if ($CreatedTempDataDir", script)
        self.assertNotIn("Remove-Item -LiteralPath $UserData -Recurse -Force", script)


if __name__ == "__main__":
    unittest.main()
