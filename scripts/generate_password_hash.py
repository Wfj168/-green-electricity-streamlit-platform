from __future__ import annotations

import argparse
from getpass import getpass

from src.security.auth import AuthService


def main() -> None:
    parser = argparse.ArgumentParser(description="生成平台账号PBKDF2密码哈希")
    parser.add_argument("--password", help="不建议在共享终端历史中传入；省略后安全输入")
    args = parser.parse_args()
    password = args.password or getpass("请输入至少10位密码：")
    print(AuthService.hash_password(password))


if __name__ == "__main__":
    main()
