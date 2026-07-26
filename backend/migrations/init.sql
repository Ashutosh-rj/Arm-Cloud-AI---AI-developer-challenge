-- InferaV22 Database Schema Initialization (TimescaleDB / PostgreSQL 16)

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Organizations
CREATE TABLE IF NOT EXISTS organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 2. Optimization runs
CREATE TABLE IF NOT EXISTS optimization_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES organizations(id),
    model_url TEXT NOT NULL,
    model_hash TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('queued','running','completed','failed','rolled_back')),
    sla_spec JSONB NOT NULL,
    target_clouds TEXT[] NOT NULL,
    quality_floor FLOAT NOT NULL DEFAULT 0.98,
    plan JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ
);

-- 3. Agent execution events
CREATE TABLE IF NOT EXISTS agent_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES optimization_runs(id),
    agent_name TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_agent_events_run_id ON agent_events(run_id, created_at DESC);

-- 4. Benchmark results
CREATE TABLE IF NOT EXISTS benchmark_results (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES optimization_runs(id),
    cloud TEXT NOT NULL,
    quant_level TEXT NOT NULL,
    concurrency INT NOT NULL,
    ttft_p50_ms FLOAT,
    ttft_p95_ms FLOAT,
    ttft_p99_ms FLOAT,
    tps_p50 FLOAT,
    memory_gb FLOAT,
    cpu_pct FLOAT,
    cost_per_1m FLOAT,
    measured_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 5. Quality reports
CREATE TABLE IF NOT EXISTS quality_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES optimization_runs(id),
    quant_level TEXT NOT NULL,
    eval_dataset TEXT NOT NULL,
    score_baseline FLOAT NOT NULL,
    score_optimized FLOAT NOT NULL,
    score_delta FLOAT GENERATED ALWAYS AS (score_optimized - score_baseline) STORED,
    gate_passed BOOLEAN NOT NULL,
    per_category JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 6. Optimization certificates
CREATE TABLE IF NOT EXISTS certificates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES optimization_runs(id),
    model_hash TEXT NOT NULL,
    optimal_config JSONB NOT NULL,
    score INT NOT NULL CHECK (score BETWEEN 0 AND 100),
    signature TEXT NOT NULL,
    pdf_url TEXT,
    public_url TEXT,
    issued_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL DEFAULT (now() + interval '1 year')
);
CREATE INDEX IF NOT EXISTS idx_certificates_model_hash ON certificates(model_hash);

-- 7. ARM topology profiles (cache)
CREATE TABLE IF NOT EXISTS arm_topology_profiles (
    instance_type TEXT NOT NULL,
    cloud TEXT NOT NULL,
    numa_nodes INT NOT NULL,
    cores_per_numa INT NOT NULL,
    sve_width_bits INT,
    l3_cache_mb INT,
    hugepages BOOLEAN NOT NULL,
    kleidiAI BOOLEAN NOT NULL,
    profiled_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (instance_type, cloud)
);
