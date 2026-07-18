from __future__ import annotations

import argparse
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.api.client import ApiClientError, PlatformApiClient  # noqa: E402
from src.deployment import DeploymentCheck, collect_deployment_checks  # noqa: E402


SYMBOLS = {"ok": "PASS", "warning": "WARN", "error": "FAIL"}


def print_check(check: DeploymentCheck) -> None:
    print(f"[{SYMBOLS[check.level]}] {check.title}: {check.detail}")


def main() -> int:
    parser = argparse.ArgumentParser(description="部署前检查运行时、环境变量、权限和后台连通性")
    parser.add_argument("--profile", choices=("ui", "api", "all"), default="all")
    parser.add_argument("--require-api", action="store_true", help="前台必须连接后台服务")
    parser.add_argument("--check-api", action="store_true", help="实际调用后台健康检查")
    args = parser.parse_args()

    checks = collect_deployment_checks(args.profile, require_api=args.require_api)
    for check in checks:
        print_check(check)

    failed = any(check.failed for check in checks)
    if args.check_api and args.profile in {"ui", "all"}:
        client = PlatformApiClient(timeout=5.0)
        try:
            health = client.health()
            print(f"[PASS] 后台连通性: status={health.get('status', 'unknown')}")
        except ApiClientError as exc:
            print(f"[FAIL] 后台连通性: {exc}")
            failed = True

    print("部署前检查未通过。" if failed else "部署前检查通过。")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
