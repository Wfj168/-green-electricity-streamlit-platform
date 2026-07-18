from __future__ import annotations

import json
from zipfile import ZipFile

import pytest

from src.operations import create_backup, restore_backup, verify_backup
from src.persistence import Database, PlatformRepository


def test_backup_verify_restore_and_rollback_drill(tmp_path) -> None:
    target = tmp_path / "platform-data"
    database_path = target / "platform.db"
    artifacts = target / "artifacts"
    artifacts.mkdir(parents=True)
    artifacts.joinpath("result.zip").write_bytes(b"original-artifact")
    repository = PlatformRepository(Database(database_path))
    original_project = repository.create_project("恢复前项目", "admin")

    backup = create_backup(database_path, artifacts, tmp_path / "backups")
    verified = verify_backup(backup)
    assert verified["format"] == "platform-backup-v2"
    assert verified["database_integrity"] == "ok"
    assert {"platform.db", "artifacts/result.zip"}.issubset(verified["entries"])

    repository.create_project("备份后新增项目", "admin")
    artifacts.joinpath("result.zip").write_bytes(b"mutated-artifact")
    restored = restore_backup(backup, target, force=True)

    assert restored["rollback_backup"] is not None
    assert verify_backup(restored["rollback_backup"])["database_integrity"] == "ok"
    restored_repository = PlatformRepository(Database(database_path))
    assert [project["id"] for project in restored_repository.list_projects()] == [original_project["id"]]
    assert artifacts.joinpath("result.zip").read_bytes() == b"original-artifact"


def test_restore_refuses_overwrite_without_force(tmp_path) -> None:
    target = tmp_path / "data"
    repository = PlatformRepository(Database(target / "platform.db"))
    repository.create_project("项目", "admin")
    backup = create_backup(target / "platform.db", target / "artifacts", tmp_path / "backups")
    with pytest.raises(FileExistsError, match="force"):
        restore_backup(backup, target)


def test_backup_verification_rejects_unsafe_archive_path(tmp_path) -> None:
    backup = tmp_path / "unsafe.zip"
    with ZipFile(backup, "w") as archive:
        archive.writestr("../outside.txt", "unsafe")
        archive.writestr(
            "manifest.json",
            json.dumps({"format": "platform-backup-v2", "entries": {}}),
        )
    with pytest.raises(ValueError, match="不安全路径"):
        verify_backup(backup)
