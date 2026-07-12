CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    owner_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scenario_versions (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    version INTEGER NOT NULL CHECK (version > 0),
    input_json TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(project_id, name, version)
);

CREATE TABLE IF NOT EXISTS dataset_versions (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    version INTEGER NOT NULL CHECK (version > 0),
    schema_version TEXT NOT NULL,
    checksum_sha256 TEXT NOT NULL,
    storage_uri TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(project_id, name, version)
);

CREATE TABLE IF NOT EXISTS model_versions (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    engine TEXT NOT NULL,
    code_commit TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(name, version)
);

CREATE TABLE IF NOT EXISTS optimization_jobs (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    scenario_version_id TEXT NOT NULL REFERENCES scenario_versions(id),
    model_version_id TEXT NOT NULL REFERENCES model_versions(id),
    status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')),
    request_json TEXT NOT NULL,
    progress REAL NOT NULL DEFAULT 0 CHECK (progress >= 0 AND progress <= 100),
    error_code TEXT,
    error_message TEXT,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT
);

CREATE TABLE IF NOT EXISTS optimization_results (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL UNIQUE REFERENCES optimization_jobs(id) ON DELETE CASCADE,
    summary_json TEXT NOT NULL,
    metrics_json TEXT NOT NULL,
    artifact_uri TEXT,
    checksum_sha256 TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_id TEXT NOT NULL,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_scenarios_project ON scenario_versions(project_id, name, version DESC);
CREATE INDEX IF NOT EXISTS idx_datasets_project ON dataset_versions(project_id, name, version DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_project_status ON optimization_jobs(project_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_logs(entity_type, entity_id, created_at DESC);
