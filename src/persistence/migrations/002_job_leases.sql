ALTER TABLE optimization_jobs ADD COLUMN worker_id TEXT;
ALTER TABLE optimization_jobs ADD COLUMN lease_expires_at TEXT;
ALTER TABLE optimization_jobs ADD COLUMN heartbeat_at TEXT;
ALTER TABLE optimization_jobs ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0);
ALTER TABLE optimization_jobs ADD COLUMN max_attempts INTEGER NOT NULL DEFAULT 3 CHECK (max_attempts > 0);
ALTER TABLE optimization_jobs ADD COLUMN idempotency_key TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS idx_jobs_idempotency
ON optimization_jobs(project_id, idempotency_key)
WHERE idempotency_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_jobs_lease
ON optimization_jobs(status, lease_expires_at, attempt_count);
