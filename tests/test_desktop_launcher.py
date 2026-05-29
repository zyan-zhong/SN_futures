from __future__ import annotations

import os
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sn_futures.server_runtime import choose_available_port
from sn_futures.user_data import initialize_user_data_dir


class DesktopLauncherTest(unittest.TestCase):
    def test_user_data_initialization_creates_expected_dirs_and_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            info = initialize_user_data_dir()
            root = Path(info["root"])
            for name in ("data", "cache", "logs", "reports", "models", "config", "registry", "outputs"):
                self.assertTrue((root / name).exists(), name)
            self.assertTrue((root / "config" / "settings.json").exists())
            self.assertTrue((root / "config" / "user_config.json").exists())
            self.assertTrue((root / "config" / "secrets.example.json").exists())
            self.assertFalse((root / "config" / "secrets.json").exists())

    def test_choose_available_port_skips_used_port(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        used = sock.getsockname()[1]
        try:
            selected = choose_available_port("127.0.0.1", preferred=used, end=used + 1)
        finally:
            sock.close()
        self.assertEqual(selected, used + 1)

    def test_user_data_does_not_require_install_dir_writable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            info = initialize_user_data_dir()
            self.assertTrue(Path(info["root"]).exists())


if __name__ == "__main__":
    unittest.main()
