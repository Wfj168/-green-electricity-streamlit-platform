from __future__ import annotations

import argparse
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.operations import create_backup, verify_backup  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="备份平台SQLite数据库和结果文件并生成校验清单")
    parser.add_argument("--database", default="var/platform.db")
    parser.add_argument("--artifacts", default="var/artifacts")
    parser.add_argument("--output-dir", default="var/backups")
    parser.add_argument("--verify", help="只校验指定备份文件")
    args = parser.parse_args()
    if args.verify:
        print(verify_backup(args.verify))
        return
    print(create_backup(args.database, args.artifacts, args.output_dir))


if __name__ == "__main__":
    main()
