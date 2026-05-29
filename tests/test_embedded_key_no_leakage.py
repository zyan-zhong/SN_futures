from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, "src")

from sn_futures.utils.secret_sanitizer import sanitize_mapping, sanitize_text


class EmbeddedKeyNoLeakageTest(unittest.TestCase):
    def test_provider_error_and_url_are_sanitized(self) -> None:
        fake_key = "LEAK_TEST_PRIVATE_KEY_123456"
        message = f"remote error: apikey={fake_key}; Authorization: Bearer {fake_key}"
        sanitized = sanitize_text(message, extra_secrets=[fake_key])
        self.assertNotIn(fake_key, sanitized)
        self.assertIn("***", sanitized)

    def test_nested_mapping_is_sanitized(self) -> None:
        fake_key = "LEAK_TEST_PRIVATE_KEY_abcdef"
        payload = {"headers": {"X-Api-Key": fake_key}, "url": f"https://example.test?a=1&apikey={fake_key}"}
        sanitized = sanitize_mapping(payload, extra_secrets=[fake_key])
        dumped = str(sanitized)
        self.assertNotIn(fake_key, dumped)

    def test_runtime_scan_script_distinguishes_private_seed_and_config(self) -> None:
        script = Path("scripts/scan_runtime_secrets.ps1").read_text(encoding="utf-8")
        self.assertIn("private_bundle_seed_present", script)
        self.assertIn("private_release_keys_present", script)
        self.assertIn("AllowPrivateBundleSeed", script)
        self.assertIn("config_file_present", script)


if __name__ == "__main__":
    unittest.main()
