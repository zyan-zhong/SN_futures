from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import datetime
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.services.alpha_rate_limit_policy import (
    classify_alpha_response,
    is_invalid_key,
    is_rate_limited,
    next_retry_time,
    record_alpha_attempt,
    should_skip_due_to_cooldown,
)


class AlphaRateLimitPolicyTest(unittest.TestCase):
    def test_note_payload_is_rate_limited_with_cooldown(self) -> None:
        result = classify_alpha_response({"Note": "Thank you for using Alpha Vantage. API call frequency is 5 calls per minute."})

        self.assertEqual(result["status"], "rate_limited")
        self.assertFalse(result["safe_to_retry_now"])
        self.assertTrue(result["cooldown_until"])
        self.assertTrue(is_rate_limited({"Information": "rate limit reached"}))

    def test_invalid_key_payload_is_key_invalid(self) -> None:
        payload = {"Error Message": "Invalid API key. Please visit Alpha Vantage."}

        self.assertTrue(is_invalid_key(payload))
        self.assertEqual(classify_alpha_response(payload)["status"], "key_invalid")

    def test_recorded_rate_limit_blocks_immediate_retry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            record_alpha_attempt("fx_daily", "rate_limited")

            self.assertTrue(should_skip_due_to_cooldown("fx_daily"))
            retry_time = next_retry_time("fx_daily", datetime.now())

        self.assertTrue(retry_time)


if __name__ == "__main__":
    unittest.main()
