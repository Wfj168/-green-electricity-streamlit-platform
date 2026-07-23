from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.application.agri_strategy_service import AgriStrategyService  # noqa: E402
from src.model.agri_park_profiles import generate_agri_park_profiles  # noqa: E402


def main() -> None:
    profiles = generate_agri_park_profiles(2025, 60)
    result = AgriStrategyService().compare(profiles)
    output = ROOT / "data" / "demo" / "phase1_strategy_comparison.csv"
    result.comparison.to_csv(output, index=False, encoding="utf-8-sig")
    print(f"已导出三策略对比：{output.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
