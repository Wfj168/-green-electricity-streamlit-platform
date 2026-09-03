CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    legal_name TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'disabled')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (name)
);

CREATE TABLE IF NOT EXISTS parks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    timezone TEXT NOT NULL DEFAULT 'Asia/Shanghai',
    area_mu NUMERIC(14, 2),
    location JSONB NOT NULL DEFAULT '{}'::jsonb,
    data_status TEXT NOT NULL DEFAULT 'not_connected'
        CHECK (data_status IN ('realtime', 'delayed', 'demo', 'estimated', 'not_connected')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (organization_id, code)
);

CREATE TABLE IF NOT EXISTS park_zones (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    park_id UUID NOT NULL REFERENCES parks(id) ON DELETE CASCADE,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    zone_type TEXT NOT NULL,
    boundary_geojson JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (park_id, code)
);

CREATE TABLE IF NOT EXISTS accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    username TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    display_name TEXT NOT NULL,
    email TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'locked', 'disabled')),
    password_changed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (organization_id, username)
);

CREATE TABLE IF NOT EXISTS roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    permissions JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS account_roles (
    account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    role_id UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    park_id UUID REFERENCES parks(id) ON DELETE CASCADE,
    valid_until TIMESTAMPTZ,
    PRIMARY KEY (account_id, role_id, park_id)
);

CREATE TABLE IF NOT EXISTS data_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    park_id UUID NOT NULL REFERENCES parks(id) ON DELETE CASCADE,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    source_type TEXT NOT NULL,
    endpoint_masked TEXT NOT NULL DEFAULT '',
    owner_name TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'not_connected',
    last_seen_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (park_id, code)
);

CREATE TABLE IF NOT EXISTS source_evidence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    park_id UUID NOT NULL REFERENCES parks(id) ON DELETE CASCADE,
    source_id UUID REFERENCES data_sources(id),
    evidence_type TEXT NOT NULL,
    title TEXT NOT NULL,
    storage_uri TEXT NOT NULL,
    checksum_sha256 TEXT NOT NULL,
    source_grade TEXT NOT NULL CHECK (source_grade IN ('A', 'B', 'C', 'D', 'E')),
    valid_from TIMESTAMPTZ,
    valid_to TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by UUID REFERENCES accounts(id),
    reviewed_by UUID REFERENCES accounts(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS assets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    park_id UUID NOT NULL REFERENCES parks(id) ON DELETE CASCADE,
    zone_id UUID REFERENCES park_zones(id),
    parent_asset_id UUID REFERENCES assets(id),
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    asset_type TEXT NOT NULL,
    rated_power_kw NUMERIC(16, 4),
    rated_energy_kwh NUMERIC(16, 4),
    status TEXT NOT NULL DEFAULT 'active',
    commissioned_on DATE,
    attributes JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (park_id, code)
);

CREATE TABLE IF NOT EXISTS asset_relations (
    source_asset_id UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    target_asset_id UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    relation_type TEXT NOT NULL,
    attributes JSONB NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (source_asset_id, target_asset_id, relation_type)
);

CREATE TABLE IF NOT EXISTS measurement_points (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    park_id UUID NOT NULL REFERENCES parks(id) ON DELETE CASCADE,
    asset_id UUID REFERENCES assets(id) ON DELETE SET NULL,
    source_id UUID REFERENCES data_sources(id),
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    metric TEXT NOT NULL,
    unit TEXT NOT NULL,
    direction TEXT NOT NULL DEFAULT 'none',
    sample_period_seconds INTEGER NOT NULL CHECK (sample_period_seconds > 0),
    multiplier NUMERIC(18, 8) NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'active',
    attributes JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (park_id, code)
);

CREATE TABLE IF NOT EXISTS measurements (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    park_id UUID NOT NULL REFERENCES parks(id) ON DELETE CASCADE,
    point_id UUID NOT NULL REFERENCES measurement_points(id) ON DELETE CASCADE,
    measured_at TIMESTAMPTZ NOT NULL,
    value NUMERIC(22, 8) NOT NULL,
    quality_code TEXT NOT NULL DEFAULT 'good',
    data_status TEXT NOT NULL DEFAULT 'realtime'
        CHECK (data_status IN ('realtime', 'delayed', 'demo', 'estimated')),
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (point_id, measured_at)
);

CREATE TABLE IF NOT EXISTS agricultural_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    park_id UUID NOT NULL REFERENCES parks(id) ON DELETE CASCADE,
    zone_id UUID REFERENCES park_zones(id),
    task_type TEXT NOT NULL CHECK (task_type IN ('irrigation', 'processing_drying', 'cold_storage', 'public_auxiliary')),
    name TEXT NOT NULL,
    external_ref TEXT,
    earliest_start TIMESTAMPTZ NOT NULL,
    latest_finish TIMESTAMPTZ NOT NULL,
    required_energy_kwh NUMERIC(18, 4) NOT NULL CHECK (required_energy_kwh >= 0),
    minimum_power_kw NUMERIC(18, 4) NOT NULL DEFAULT 0,
    maximum_power_kw NUMERIC(18, 4) NOT NULL CHECK (maximum_power_kw >= 0),
    interruption_allowed BOOLEAN NOT NULL DEFAULT false,
    production_loss_cny_per_kwh NUMERIC(18, 6) NOT NULL DEFAULT 0,
    constraints JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'planned',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (latest_finish > earliest_start),
    CHECK (maximum_power_kw >= minimum_power_kw)
);

CREATE TABLE IF NOT EXISTS green_power_contracts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    park_id UUID NOT NULL REFERENCES parks(id) ON DELETE CASCADE,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    supplier TEXT NOT NULL,
    contract_type TEXT NOT NULL,
    valid_from DATE NOT NULL,
    valid_to DATE NOT NULL,
    contracted_capacity_kw NUMERIC(18, 4) NOT NULL CHECK (contracted_capacity_kw >= 0),
    minimum_take_ratio NUMERIC(8, 6) NOT NULL DEFAULT 0 CHECK (minimum_take_ratio BETWEEN 0 AND 1),
    energy_price_cny_per_kwh NUMERIC(18, 6) NOT NULL,
    transmission_fee_cny_per_kwh NUMERIC(18, 6) NOT NULL DEFAULT 0,
    auxiliary_fee_cny_per_kwh NUMERIC(18, 6) NOT NULL DEFAULT 0,
    capacity_fee_cny_per_kw_month NUMERIC(18, 6) NOT NULL DEFAULT 0,
    deviation_penalty_cny_per_kwh NUMERIC(18, 6) NOT NULL DEFAULT 0,
    nominal_line_loss_ratio NUMERIC(8, 6) NOT NULL DEFAULT 0 CHECK (nominal_line_loss_ratio BETWEEN 0 AND 1),
    availability_target NUMERIC(8, 6) NOT NULL DEFAULT 1 CHECK (availability_target BETWEEN 0 AND 1),
    currency CHAR(3) NOT NULL DEFAULT 'CNY' CHECK (currency = 'CNY'),
    source_evidence_id UUID REFERENCES source_evidence(id),
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (valid_to >= valid_from),
    UNIQUE (park_id, code)
);

CREATE TABLE IF NOT EXISTS green_contract_schedule (
    contract_id UUID NOT NULL REFERENCES green_power_contracts(id) ON DELETE CASCADE,
    interval_start TIMESTAMPTZ NOT NULL,
    interval_minutes SMALLINT NOT NULL CHECK (interval_minutes IN (15, 30, 60)),
    injection_plan_kwh NUMERIC(18, 6) NOT NULL CHECK (injection_plan_kwh >= 0),
    availability_ratio NUMERIC(8, 6) NOT NULL DEFAULT 1 CHECK (availability_ratio BETWEEN 0 AND 1),
    PRIMARY KEY (contract_id, interval_start)
);

CREATE TABLE IF NOT EXISTS parameter_sets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    park_id UUID NOT NULL REFERENCES parks(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    version INTEGER NOT NULL CHECK (version > 0),
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'reviewed', 'published', 'retired')),
    effective_from TIMESTAMPTZ,
    effective_to TIMESTAMPTZ,
    checksum_sha256 TEXT NOT NULL,
    created_by UUID REFERENCES accounts(id),
    reviewed_by UUID REFERENCES accounts(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (park_id, name, version)
);

CREATE TABLE IF NOT EXISTS parameter_values (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parameter_set_id UUID NOT NULL REFERENCES parameter_sets(id) ON DELETE CASCADE,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    value_json JSONB NOT NULL,
    unit TEXT NOT NULL DEFAULT '',
    source_evidence_id UUID REFERENCES source_evidence(id),
    source_grade TEXT NOT NULL CHECK (source_grade IN ('A', 'B', 'C', 'D', 'E')),
    uncertainty_low NUMERIC(22, 8),
    uncertainty_high NUMERIC(22, 8),
    rationale TEXT NOT NULL DEFAULT '',
    UNIQUE (parameter_set_id, code)
);

CREATE TABLE IF NOT EXISTS model_registry (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    engine TEXT NOT NULL,
    code_commit TEXT NOT NULL,
    input_schema JSONB NOT NULL DEFAULT '{}'::jsonb,
    output_schema JSONB NOT NULL DEFAULT '{}'::jsonb,
    validation_report_uri TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (code, version)
);

CREATE TABLE IF NOT EXISTS scenarios_v2 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    park_id UUID NOT NULL REFERENCES parks(id) ON DELETE CASCADE,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    scenario_type TEXT NOT NULL,
    baseline_scenario_id UUID REFERENCES scenarios_v2(id),
    parameter_set_id UUID NOT NULL REFERENCES parameter_sets(id),
    assumptions JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by UUID REFERENCES accounts(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (park_id, code)
);

CREATE TABLE IF NOT EXISTS optimization_runs_v2 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    park_id UUID NOT NULL REFERENCES parks(id) ON DELETE CASCADE,
    scenario_id UUID NOT NULL REFERENCES scenarios_v2(id),
    model_id UUID NOT NULL REFERENCES model_registry(id),
    parameter_set_id UUID NOT NULL REFERENCES parameter_sets(id),
    run_type TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')),
    progress NUMERIC(6, 3) NOT NULL DEFAULT 0 CHECK (progress BETWEEN 0 AND 100),
    requested_by UUID REFERENCES accounts(id),
    request_snapshot JSONB NOT NULL,
    input_checksum_sha256 TEXT NOT NULL,
    error_code TEXT,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS run_metrics (
    run_id UUID NOT NULL REFERENCES optimization_runs_v2(id) ON DELETE CASCADE,
    metric_code TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    value NUMERIC(24, 8) NOT NULL,
    unit TEXT NOT NULL,
    currency CHAR(3) CHECK (currency IS NULL OR currency = 'CNY'),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (run_id, metric_code)
);

CREATE TABLE IF NOT EXISTS energy_flow_intervals (
    run_id UUID NOT NULL REFERENCES optimization_runs_v2(id) ON DELETE CASCADE,
    interval_start TIMESTAMPTZ NOT NULL,
    interval_minutes SMALLINT NOT NULL CHECK (interval_minutes IN (15, 30, 60)),
    local_pv_kwh NUMERIC(22, 8) NOT NULL DEFAULT 0,
    direct_injected_kwh NUMERIC(22, 8) NOT NULL DEFAULT 0,
    direct_delivered_kwh NUMERIC(22, 8) NOT NULL DEFAULT 0,
    grid_import_kwh NUMERIC(22, 8) NOT NULL DEFAULT 0,
    storage_charge_kwh NUMERIC(22, 8) NOT NULL DEFAULT 0,
    storage_discharge_kwh NUMERIC(22, 8) NOT NULL DEFAULT 0,
    agricultural_load_kwh NUMERIC(22, 8) NOT NULL DEFAULT 0,
    grid_export_kwh NUMERIC(22, 8) NOT NULL DEFAULT 0,
    curtailed_kwh NUMERIC(22, 8) NOT NULL DEFAULT 0,
    line_loss_kwh NUMERIC(22, 8) NOT NULL DEFAULT 0,
    storage_loss_kwh NUMERIC(22, 8) NOT NULL DEFAULT 0,
    balance_error_kwh NUMERIC(22, 10) NOT NULL DEFAULT 0,
    PRIMARY KEY (run_id, interval_start)
);

CREATE TABLE IF NOT EXISTS dispatch_intervals (
    run_id UUID NOT NULL REFERENCES optimization_runs_v2(id) ON DELETE CASCADE,
    task_id UUID REFERENCES agricultural_tasks(id),
    asset_id UUID NOT NULL REFERENCES assets(id),
    interval_start TIMESTAMPTZ NOT NULL,
    planned_power_kw NUMERIC(22, 8) NOT NULL,
    actual_power_kw NUMERIC(22, 8),
    command_status TEXT NOT NULL DEFAULT 'planned',
    PRIMARY KEY (run_id, asset_id, interval_start)
);

CREATE TABLE IF NOT EXISTS forecast_series (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    park_id UUID NOT NULL REFERENCES parks(id) ON DELETE CASCADE,
    forecast_type TEXT NOT NULL,
    model_id UUID REFERENCES model_registry(id),
    issued_at TIMESTAMPTZ NOT NULL,
    horizon_start TIMESTAMPTZ NOT NULL,
    horizon_end TIMESTAMPTZ NOT NULL,
    interval_minutes SMALLINT NOT NULL CHECK (interval_minutes IN (15, 30, 60)),
    quality_metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
    source_ids UUID[] NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS forecast_values (
    series_id UUID NOT NULL REFERENCES forecast_series(id) ON DELETE CASCADE,
    interval_start TIMESTAMPTZ NOT NULL,
    point_value NUMERIC(22, 8) NOT NULL,
    lower_bound NUMERIC(22, 8),
    upper_bound NUMERIC(22, 8),
    unit TEXT NOT NULL,
    PRIMARY KEY (series_id, interval_start)
);

CREATE TABLE IF NOT EXISTS storage_source_ledger (
    run_id UUID NOT NULL REFERENCES optimization_runs_v2(id) ON DELETE CASCADE,
    asset_id UUID NOT NULL REFERENCES assets(id),
    interval_start TIMESTAMPTZ NOT NULL,
    pv_soc_kwh NUMERIC(22, 8) NOT NULL DEFAULT 0,
    direct_soc_kwh NUMERIC(22, 8) NOT NULL DEFAULT 0,
    grid_soc_kwh NUMERIC(22, 8) NOT NULL DEFAULT 0,
    unverifiable_soc_kwh NUMERIC(22, 8) NOT NULL DEFAULT 0,
    discharge_pv_kwh NUMERIC(22, 8) NOT NULL DEFAULT 0,
    discharge_direct_kwh NUMERIC(22, 8) NOT NULL DEFAULT 0,
    discharge_grid_kwh NUMERIC(22, 8) NOT NULL DEFAULT 0,
    loss_kwh NUMERIC(22, 8) NOT NULL DEFAULT 0,
    PRIMARY KEY (run_id, asset_id, interval_start)
);

CREATE TABLE IF NOT EXISTS carbon_ledger (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    park_id UUID NOT NULL REFERENCES parks(id) ON DELETE CASCADE,
    run_id UUID REFERENCES optimization_runs_v2(id) ON DELETE CASCADE,
    period_start TIMESTAMPTZ NOT NULL,
    period_end TIMESTAMPTZ NOT NULL,
    scope_code TEXT NOT NULL,
    activity_type TEXT NOT NULL,
    activity_value NUMERIC(22, 8) NOT NULL,
    activity_unit TEXT NOT NULL,
    emission_factor NUMERIC(22, 10) NOT NULL,
    factor_unit TEXT NOT NULL,
    emissions_kgco2e NUMERIC(24, 8) NOT NULL,
    source_evidence_id UUID REFERENCES source_evidence(id),
    status TEXT NOT NULL DEFAULT 'calculated',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (period_end > period_start)
);

CREATE TABLE IF NOT EXISTS green_power_ledger (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    park_id UUID NOT NULL REFERENCES parks(id) ON DELETE CASCADE,
    run_id UUID REFERENCES optimization_runs_v2(id) ON DELETE CASCADE,
    interval_start TIMESTAMPTZ NOT NULL,
    source_type TEXT NOT NULL CHECK (source_type IN ('local_pv', 'direct_green', 'certificate', 'other_right')),
    source_ref UUID,
    generated_or_delivered_kwh NUMERIC(22, 8) NOT NULL DEFAULT 0,
    consumed_kwh NUMERIC(22, 8) NOT NULL DEFAULT 0,
    stored_kwh NUMERIC(22, 8) NOT NULL DEFAULT 0,
    exported_kwh NUMERIC(22, 8) NOT NULL DEFAULT 0,
    retired_kwh NUMERIC(22, 8) NOT NULL DEFAULT 0,
    verification_status TEXT NOT NULL DEFAULT 'unverified',
    evidence_id UUID REFERENCES source_evidence(id)
);

CREATE TABLE IF NOT EXISTS alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    park_id UUID NOT NULL REFERENCES parks(id) ON DELETE CASCADE,
    source_type TEXT NOT NULL,
    source_id UUID,
    severity TEXT NOT NULL CHECK (severity IN ('info', 'minor', 'major', 'critical')),
    code TEXT NOT NULL,
    title TEXT NOT NULL,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'acknowledged', 'assigned', 'closed')),
    occurred_at TIMESTAMPTZ NOT NULL,
    acknowledged_at TIMESTAMPTZ,
    closed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS report_exports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    park_id UUID NOT NULL REFERENCES parks(id) ON DELETE CASCADE,
    run_id UUID REFERENCES optimization_runs_v2(id),
    report_type TEXT NOT NULL,
    format TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    storage_uri TEXT,
    checksum_sha256 TEXT,
    requested_by UUID REFERENCES accounts(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS audit_events (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    organization_id UUID REFERENCES organizations(id),
    park_id UUID REFERENCES parks(id),
    actor_id UUID REFERENCES accounts(id),
    request_id TEXT NOT NULL,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    before_state JSONB,
    after_state JSONB,
    client_ip INET,
    user_agent TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_measurements_park_time ON measurements (park_id, measured_at DESC);
CREATE INDEX IF NOT EXISTS idx_measurements_time_brin ON measurements USING BRIN (measured_at);
CREATE INDEX IF NOT EXISTS idx_tasks_park_window ON agricultural_tasks (park_id, earliest_start, latest_finish);
CREATE INDEX IF NOT EXISTS idx_runs_park_status ON optimization_runs_v2 (park_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_energy_flow_interval ON energy_flow_intervals (interval_start DESC);
CREATE INDEX IF NOT EXISTS idx_forecasts_park_type ON forecast_series (park_id, forecast_type, issued_at DESC);
CREATE INDEX IF NOT EXISTS idx_carbon_park_period ON carbon_ledger (park_id, period_start DESC);
CREATE INDEX IF NOT EXISTS idx_green_park_interval ON green_power_ledger (park_id, interval_start DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_open ON alerts (park_id, status, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_park_time ON audit_events (park_id, created_at DESC);

INSERT INTO roles (code, name, permissions)
VALUES
    ('admin', '系统管理员', '["*"]'::jsonb),
    ('engineer', '规划与调度工程师', '["model:run", "data:write", "report:export"]'::jsonb),
    ('operator', '运行值班员', '["dispatch:read", "dispatch:command", "alarm:handle"]'::jsonb),
    ('viewer', '只读用户', '["*:read"]'::jsonb),
    ('auditor', '审计用户', '["audit:read", "report:read"]'::jsonb)
ON CONFLICT (code) DO NOTHING;
