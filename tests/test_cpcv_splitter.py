from __future__ import annotations

import math
import sys
import unittest

sys.path.insert(0, "src")

from sn_futures.services.cpcv_validation_service import build_cpcv_splits


class CPCVSplitterTest(unittest.TestCase):
    def test_builds_combinatorial_purged_validation_paths(self) -> None:
        splits = build_cpcv_splits(sample_count=60, n_groups=6, test_group_count=2, purge=1, embargo=1)

        self.assertEqual(len(splits), math.comb(6, 2))
        self.assertEqual({split["mode"] for split in splits}, {"cpcv_like_combinatorial_purged"})
        for split in splits:
            self.assertIn("path_id", split)
            self.assertEqual(len(split["test_groups"]), 2)
            self.assertGreater(len(split["test_indices"]), 0)
            self.assertGreater(len(split["train_indices"]), 0)
            self.assertTrue(set(split["test_indices"]).isdisjoint(set(split["train_indices"])))
            self.assertTrue(set(split["purged_indices"]).isdisjoint(set(split["train_indices"])))
            self.assertTrue(set(split["embargo_indices"]).isdisjoint(set(split["train_indices"])))


if __name__ == "__main__":
    unittest.main()
