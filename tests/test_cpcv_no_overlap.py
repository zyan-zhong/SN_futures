from __future__ import annotations

import sys
import unittest

sys.path.insert(0, "src")

from sn_futures.services.cpcv_validation_service import build_cpcv_splits


class CPCVNoOverlapTest(unittest.TestCase):
    def test_train_indices_respect_purge_and_embargo_around_validation(self) -> None:
        splits = build_cpcv_splits(sample_count=50, n_groups=5, test_group_count=1, purge=2, embargo=2)

        for split in splits:
            train = set(split["train_indices"])
            test = set(split["test_indices"])
            self.assertTrue(test.isdisjoint(train))
            blocked = set()
            for idx in test:
                blocked.update(range(max(0, idx - 2), min(50, idx + 3)))
            self.assertTrue(train.isdisjoint(blocked), f"{split['path_id']} leaked purge/embargo indices")
            self.assertTrue(split["no_overlap"])
            self.assertTrue(split["purge_embargo_applied"])


if __name__ == "__main__":
    unittest.main()
