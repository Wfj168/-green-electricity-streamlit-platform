from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import shutil
import sqlite3
import zipfile


def main() -> None:
    parser = argparse.ArgumentParser(description="Back up the platform SQLite database and result artifacts")
    parser.add_argument("--database", default="var/platform.db")
    parser.add_argument("--artifacts", default="var/artifacts")
    parser.add_argument("--output-dir", default="var/backups")
    args = parser.parse_args()

    database_path = Path(args.database).resolve()
    artifacts_path = Path(args.artifacts).resolve()
    output_dir = Path(args.output_dir).resolve()
    if not database_path.exists():
        raise SystemExit(f"Database not found: {database_path}")
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    database_backup = output_dir / f"platform-{timestamp}.db"
    with sqlite3.connect(database_path) as source, sqlite3.connect(database_backup) as target:
        source.backup(target)

    archive_path = output_dir / f"platform-backup-{timestamp}.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(database_backup, "platform.db")
        if artifacts_path.exists():
            for artifact in artifacts_path.rglob("*"):
                if artifact.is_file():
                    archive.write(artifact, Path("artifacts") / artifact.relative_to(artifacts_path))
    database_backup.unlink()
    print(archive_path)


if __name__ == "__main__":
    main()
