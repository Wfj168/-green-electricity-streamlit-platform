from __future__ import annotations

import argparse
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.operations import restore_backup, verify_backup  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="校验并恢复平台备份；覆盖前自动生成回滚备份")
    parser.add_argument("backup")
    parser.add_argument("--target-dir", default="var")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.verify_only:
        print(verify_backup(args.backup))
        return
    print(restore_backup(args.backup, args.target_dir, force=args.force))


if __name__ == "__main__":
    main()
