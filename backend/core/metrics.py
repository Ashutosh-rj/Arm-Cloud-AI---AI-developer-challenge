"""
Prometheus metrics for InferaV22.
All counters/histograms are defined here and instrumented in agents and API routes.
"""
import os
from prometheus_client import (
    Counter, Histogram, Gauge, Info,
    CollectorRegistry, make_asgi_app, REGISTRY
)

# ── Optimization Runs ──────────────────────────────────────────────────────────
optimization_runs_total = Counter(
    "inferav22_optimization_runs_total",
    "Total number of optimization runs started",
    ["status", "cloud"],
)

optimization_run_duration_seconds = Histogram(
    "inferav22_optimization_run_duration_seconds",
    "Duration of complete optimization pipeline runs",
    ["cloud", "status"],
    buckets=[30, 60, 120, 300, 600, 900, 1800],
)

# ── Benchmark Metrics ──────────────────────────────────────────────────────────
benchmark_tps = Histogram(
    "inferav22_benchmark_tps",
    "Measured tokens per second from real benchmark runs",
    ["cloud", "quant_level"],
    buckets=[5, 10, 20, 50, 100, 200, 500, 1000],
)

benchmark_ttft_ms = Histogram(
    "inferav22_benchmark_ttft_ms",
    "Time to first token in milliseconds from real benchmark runs",
    ["cloud", "quant_level"],
    buckets=[50, 100, 200, 300, 500, 1000, 2000, 5000],
)

benchmark_cost_per_1m = Histogram(
    "inferav22_benchmark_cost_per_1m_usd",
    "Cost per 1M tokens in USD from real benchmark runs",
    ["cloud", "quant_level"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0],
)

# ── Quality Gate ───────────────────────────────────────────────────────────────
quality_gate_results_total = Counter(
    "inferav22_quality_gate_results_total",
    "Quality gate pass/fail counts",
    ["result", "quant_level"],  # result: pass | fail
)

quality_score_delta = Histogram(
    "inferav22_quality_score_delta",
    "MMLU accuracy delta (quantized vs baseline)",
    ["quant_level"],
    buckets=[-0.05, -0.02, -0.01, -0.005, -0.001, 0.0, 0.001],
)

# ── Cache ─────────────────────────────────────────────────────────────────────
cache_hit_rate_gauge = Gauge(
    "inferav22_cache_hit_rate_pct",
    "Current semantic cache hit rate as a percentage"
)

cache_operations_total = Counter(
    "inferav22_cache_operations_total",
    "Total cache operations",
    ["operation"],  # operation: exact_hit | semantic_hit | miss
)

# ── API ───────────────────────────────────────────────────────────────────────
api_requests_total = Counter(
    "inferav22_api_requests_total",
    "Total API requests",
    ["method", "endpoint", "status_code"],
)

api_request_duration_seconds = Histogram(
    "inferav22_api_request_duration_seconds",
    "API request duration in seconds",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

# ── Worker ────────────────────────────────────────────────────────────────────
worker_queue_depth = Gauge(
    "inferav22_worker_queue_depth",
    "Number of optimization runs currently queued"
)

certificates_issued_total = Counter(
    "inferav22_certificates_issued_total",
    "Total optimization certificates issued",
    ["cloud", "quant_level"],
)

# ── System Info ───────────────────────────────────────────────────────────────
app_info = Info("inferav22_app", "InferaV22 application information")
app_info.info({"version": os.getenv("APP_VERSION", "0.1.0"), "environment": os.getenv("ENVIRONMENT", "development")})

# ASGI app to mount at /metrics
metrics_asgi_app = make_asgi_app()
