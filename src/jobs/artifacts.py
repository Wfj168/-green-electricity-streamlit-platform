from __future__ import annotations

import hashlib
import os
from pathlib import Path


class LocalArtifactStore:
    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root or os.getenv("PLATFORM_ARTIFACT_DIR", "var/artifacts"))
        self.root.mkdir(parents=True, exist_ok=True)

    def write_result_bundle(self, job_id: str, content: bytes) -> tuple[str, str]:
        checksum = hashlib.sha256(content).hexdigest()
        target = self.root / f"{job_id}.zip"
        temporary = self.root / f".{job_id}.tmp"
        temporary.write_bytes(content)
        temporary.replace(target)
        return target.resolve().as_uri(), checksum
