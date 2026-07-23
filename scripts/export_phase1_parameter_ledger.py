from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.agri_parameter_registry import PHASE1_PARAMETER_REGISTRY  # noqa: E402


DEFAULT_OUTPUT = Path("data/templates/phase1_parameter_ledger.csv")


def export_parameter_ledger(output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "code",
        "name",
        "group",
        "unit",
        "value",
        "minimum",
        "maximum",
        "source_grade",
        "verification_status",
        "source_reference",
        "setting_method",
        "formal_required",
    ]
    with output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for parameter in sorted(PHASE1_PARAMETER_REGISTRY, key=lambda item: (item.group, item.code)):
            writer.writerow(parameter.to_payload())


def main() -> None:
    parser = argparse.ArgumentParser(description="导出第一阶段农业零碳园区参数台账")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    export_parameter_ledger(args.output)
    print(f"已导出参数台账：{args.output}")


if __name__ == "__main__":
    main()
