from __future__ import annotations

import argparse
import os
import socket
import time

from src.jobs import JobRunner
from src.jobs.artifacts import LocalArtifactStore
from src.persistence import Database, PlatformRepository


def main() -> None:
    parser = argparse.ArgumentParser(description="Optimization job worker")
    parser.add_argument("--once", action="store_true", help="Process at most one queued job and exit")
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    parser.add_argument(
        "--worker-id",
        default=os.getenv("PLATFORM_WORKER_ID", f"{socket.gethostname()}-{os.getpid()}"),
    )
    parser.add_argument(
        "--lease-seconds",
        type=int,
        default=int(os.getenv("PLATFORM_JOB_LEASE_SECONDS", "3600")),
    )
    args = parser.parse_args()

    runner = JobRunner(
        PlatformRepository(Database()),
        LocalArtifactStore(),
        worker_id=args.worker_id,
        lease_seconds=args.lease_seconds,
    )
    while True:
        job = runner.run_once()
        if args.once:
            return
        if job is None:
            time.sleep(max(args.poll_seconds, 0.2))


if __name__ == "__main__":
    main()
