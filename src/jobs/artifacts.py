from __future__ import annotations

import hashlib
import os
from pathlib import Path
from urllib.parse import unquote, urlparse


def file_uri_to_path(uri: str) -> Path:
    """Convert a local ``file:`` URI to a path on Windows or POSIX."""
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        raise ValueError(f"Only file URIs are supported, received: {parsed.scheme or 'no scheme'}")

    path = unquote(parsed.path)
    if os.name == "nt" and len(path) >= 3 and path[0] == "/" and path[2] == ":":
        path = path[1:]
    if parsed.netloc and parsed.netloc != "localhost":
        path = f"//{parsed.netloc}{path}"
    return Path(path)


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
