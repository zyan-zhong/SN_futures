from __future__ import annotations

import builtins
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.services import market_data_service as svc


class AkshareDependencyPackagingStatusTest(unittest.TestCase):
    def test_mini_racer_dependency_failure_is_optional_and_path_sanitized(self) -> None:
        original_import = builtins.__import__
        raw_error = (
            r"Native library dependency not available: "
            r"C:\Users\Henry Austin\AppData\Local\Temp\_MEI12345\py_mini_racer\mini_racer.dll"
        )

        def guarded_import(name: str, *args: object, **kwargs: object) -> object:
            if name == "akshare":
                raise OSError(raw_error)
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=guarded_import):
            result = svc.refresh_market_history()

        self.assertFalse(result["success"])
        attempt = result["attempts"][0]
        self.assertEqual(attempt["provider_name"], "akshare_history")
        self.assertEqual(attempt["status_code"], "optional_failed")
        self.assertTrue(attempt["optional"])
        self.assertFalse(attempt["blocking"])
        message = attempt["error_message_zh"]
        self.assertIn("mini_racer.dll", message)
        self.assertNotIn(r"C:\Users", message)
        self.assertNotIn("Henry Austin", message)
        self.assertNotIn("_MEI12345", message)


if __name__ == "__main__":
    unittest.main()
