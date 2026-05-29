from __future__ import annotations

import sys
import unittest

sys.path.insert(0, "src")

from sn_futures.diagnostics.resource_profile_audit import audit_resource_profile


class ResourceProfileAuditTest(unittest.TestCase):
    def test_cuda_profile_reports_gpu_strategy(self) -> None:
        audit = audit_resource_profile(
            {
                "cpu_logical_cores": 24,
                "memory_gb": 32,
                "torch_cuda_available": True,
                "gpu_name": "NVIDIA GeForce RTX 4060 Laptop GPU",
                "gpu_memory_gb": 8,
                "actual_training_device": "cuda:0",
                "current_profile": "gpu_full",
                "recommended_profile": "gpu_full",
            }
        )
        self.assertTrue(audit["ok"])
        self.assertIn("GPU-Standard", audit["strategy"])

    def test_gpu_profile_without_cuda_warns(self) -> None:
        audit = audit_resource_profile(
            {
                "cpu_logical_cores": 16,
                "memory_gb": 32,
                "torch_cuda_available": False,
                "actual_training_device": "cpu",
                "current_profile": "gpu_full",
            }
        )
        self.assertFalse(audit["ok"])
        self.assertTrue(audit["warnings"])


if __name__ == "__main__":
    unittest.main()
