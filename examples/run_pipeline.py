from __future__ import annotations

import sys
import os
import warnings
from pathlib import Path

os.environ.setdefault("LOKY_MAX_CPU_COUNT", "1")
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sn_futures import run_pipeline


def main() -> None:
    result = run_pipeline(use_demo=True)
    print("SN pipeline finished.")
    print(f"Output directory: {result['output_dir']}")
    print("Selected features:")
    for feature in result["selected_features"]:
        print(f" - {feature}")
    print("Key metrics:")
    for key, value in result["metrics"].items():
        print(f" - {key}: {value}")


if __name__ == "__main__":
    main()
