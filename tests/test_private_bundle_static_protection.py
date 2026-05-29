from __future__ import annotations

import sys
import unittest

sys.path.insert(0, "src")

from sn_futures.api_server import _is_private_bundle_static_path


class PrivateBundleStaticProtectionTest(unittest.TestCase):
    def test_private_bundle_paths_are_blocked(self) -> None:
        blocked = [
            "/terminal/../private/private_bundle_seed.json",
            "/private/private_bundle_seed.json",
            "/_internal/private/private_bundle_seed.json",
            "/terminal/assets/private_bundle_seed.json",
        ]
        for path in blocked:
            with self.subTest(path=path):
                self.assertTrue(_is_private_bundle_static_path(path))

    def test_normal_terminal_assets_are_not_blocked(self) -> None:
        self.assertFalse(_is_private_bundle_static_path("/terminal/assets/index.js"))
        self.assertFalse(_is_private_bundle_static_path("/legacy"))


if __name__ == "__main__":
    unittest.main()
