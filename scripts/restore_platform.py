from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import tempfile
import zipfile


def main() -> None:
    parser = argparse.ArgumentParser(description="Restore a platform backup into an offline data directory")
    parser.add_argument("backup")
    parser.add_argument("--target-dir", default="var")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    backup_path = Path(args.backup).resolve()
    target_dir = Path(args.target_dir).resolve()
    database_target = target_dir / "platform.db"
    if database_target.exists() and not args.force:
        raise SystemExit("Target database already exists. Stop services and pass --force to replace it.")
    target_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        extracted = Path(temporary)
        with zipfile.ZipFile(backup_path) as archive:
            archive.extractall(extracted)
        if not (extracted / "platform.db").exists():
            raise SystemExit("Backup does not contain platform.db")
        shutil.copy2(extracted / "platform.db", database_target)
        artifact_source = extracted / "artifacts"
        artifact_target = target_dir / "artifacts"
        if artifact_source.exists():
            artifact_target.mkdir(parents=True, exist_ok=True)
            shutil.copytree(artifact_source, artifact_target, dirs_exist_ok=True)
    print(target_dir)


if __name__ == "__main__":
    main()
