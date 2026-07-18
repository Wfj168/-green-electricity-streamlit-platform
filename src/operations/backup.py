from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import tempfile
from typing import Any
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile

from src.version import PLATFORM_VERSION


BACKUP_FORMAT = "platform-backup-v2"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_archive_name(name: str) -> bool:
    path = PurePosixPath(name)
    return (
        not path.is_absolute()
        and ".." not in path.parts
        and not name.startswith(("/", "\\"))
        and "\\" not in name
        and not any(":" in part for part in path.parts)
    )


def create_backup(
    database_path: str | Path,
    artifacts_path: str | Path,
    output_dir: str | Path,
    *,
    label: str = "platform-backup",
) -> Path:
    database = Path(database_path).resolve()
    artifacts = Path(artifacts_path).resolve()
    output = Path(output_dir).resolve()
    if not database.exists():
        raise FileNotFoundError(f"数据库不存在：{database}")
    output.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    archive_path = output / f"{label}-{timestamp}-{uuid4().hex[:8]}.zip"

    with tempfile.TemporaryDirectory() as temporary:
        database_copy = Path(temporary) / "platform.db"
        source = sqlite3.connect(database)
        target = sqlite3.connect(database_copy)
        try:
            source.backup(target)
        finally:
            target.close()
            source.close()
        files: list[tuple[Path, str]] = [(database_copy, "platform.db")]
        if artifacts.exists():
            files.extend(
                (path, (PurePosixPath("artifacts") / PurePosixPath(path.relative_to(artifacts).as_posix())).as_posix())
                for path in sorted(artifacts.rglob("*"))
                if path.is_file()
            )
        entries = {
            archive_name: {"sha256": _sha256(path), "size": path.stat().st_size}
            for path, archive_name in files
        }
        manifest = {
            "format": BACKUP_FORMAT,
            "platform_version": PLATFORM_VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "entries": entries,
        }
        with ZipFile(archive_path, "w", ZIP_DEFLATED) as archive:
            for path, archive_name in files:
                archive.write(path, archive_name)
            archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    verify_backup(archive_path)
    return archive_path


def verify_backup(backup_path: str | Path) -> dict[str, Any]:
    backup = Path(backup_path).resolve()
    if not backup.exists():
        raise FileNotFoundError(f"备份文件不存在：{backup}")
    with ZipFile(backup) as archive:
        names = archive.namelist()
        unsafe = [name for name in names if not _safe_archive_name(name)]
        if unsafe:
            raise ValueError(f"备份包含不安全路径：{unsafe[0]}")
        if "manifest.json" not in names:
            raise ValueError("备份缺少manifest.json")
        manifest = json.loads(archive.read("manifest.json"))
        if manifest.get("format") != BACKUP_FORMAT:
            raise ValueError("不支持的备份格式")
        entries = manifest.get("entries", {})
        if "platform.db" not in entries:
            raise ValueError("备份缺少platform.db校验记录")
        for name, expected in entries.items():
            if name not in names:
                raise ValueError(f"备份缺少文件：{name}")
            content = archive.read(name)
            if len(content) != int(expected["size"]):
                raise ValueError(f"备份文件大小不匹配：{name}")
            if hashlib.sha256(content).hexdigest() != expected["sha256"]:
                raise ValueError(f"备份校验和不匹配：{name}")
        if archive.testzip() is not None:
            raise ValueError("ZIP完整性检查失败")
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "platform.db"
            database.write_bytes(archive.read("platform.db"))
            connection = sqlite3.connect(database)
            try:
                integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
            finally:
                connection.close()
            if integrity != "ok":
                raise ValueError(f"数据库完整性检查失败：{integrity}")
    return {**manifest, "database_integrity": "ok", "archive": str(backup)}


def restore_backup(
    backup_path: str | Path,
    target_dir: str | Path,
    *,
    force: bool = False,
    create_rollback: bool = True,
) -> dict[str, Any]:
    backup = Path(backup_path).resolve()
    target = Path(target_dir).resolve()
    manifest = verify_backup(backup)
    database_target = target / "platform.db"
    artifacts_target = target / "artifacts"
    if database_target.exists() and not force:
        raise FileExistsError("目标数据库已存在；停止服务并使用force执行受控恢复")

    rollback_path: Path | None = None
    if database_target.exists() and force and create_rollback:
        rollback_path = create_backup(
            database_target,
            artifacts_target,
            target / "backups" / "pre-restore",
            label="pre-restore",
        )

    target.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        extracted = Path(temporary)
        with ZipFile(backup) as archive:
            for name in manifest["entries"]:
                destination = extracted / Path(PurePosixPath(name))
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(archive.read(name))

        database_temporary = target / f".platform-{uuid4().hex}.restore.tmp"
        shutil.copy2(extracted / "platform.db", database_temporary)
        database_temporary.replace(database_target)
        artifact_source = extracted / "artifacts"
        if artifact_source.exists():
            artifacts_target.mkdir(parents=True, exist_ok=True)
            shutil.copytree(artifact_source, artifacts_target, dirs_exist_ok=True)

    return {
        "restored_from": str(backup),
        "target_dir": str(target),
        "rollback_backup": str(rollback_path) if rollback_path else None,
        "manifest": manifest,
    }
