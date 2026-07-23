from __future__ import annotations

import argparse
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.model.agri_park_profiles import (  # noqa: E402
    generate_agri_park_profiles,
    summarize_agri_park_profiles,
    validate_agri_park_profiles,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="导出第一阶段农业园区连续全年演示时序")
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--resolution-minutes", type=int, choices=(15, 30, 60), default=60)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    output = args.output or Path(
        f"data/demo/phase1_agri_park_{args.year}_{args.resolution_minutes}min.csv"
    )
    profiles = generate_agri_park_profiles(args.year, args.resolution_minutes)
    issues = validate_agri_park_profiles(profiles)
    if issues:
        for issue in issues:
            print(f"[FAIL] {issue}")
        return 1
    output.parent.mkdir(parents=True, exist_ok=True)
    profiles.to_csv(output, index=False, encoding="utf-8-sig")
    summary_output = output.with_name(f"{output.stem}_summary.csv")
    summarize_agri_park_profiles(profiles).to_csv(summary_output, index=False, encoding="utf-8-sig")
    print(f"已导出全年时序：{output}")
    print(f"已导出负荷汇总：{summary_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
