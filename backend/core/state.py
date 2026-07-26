from typing import List, Dict, Any, Optional, Literal
from typing_extensions import TypedDict
from pydantic import BaseModel, Field
from datetime import datetime

class SLASpec(BaseModel):
    max_p99_latency_ms: float = Field(default=500.0, description="Maximum P99 latency in ms")
    min_tps: float = Field(default=30.0, description="Minimum tokens per second")
    max_cost_per_1m_tokens_usd: float = Field(default=0.60, description="Maximum cost per 1M tokens in USD")
    target_concurrency: int = Field(default=16, description="Target concurrent requests")

class ArmTopologyProfile(BaseModel):
    cloud: str
    instance_type: str
    numa_nodes: int = 1
    cores_per_numa: int = 16
    sve_width_bits: int = 256
    l3_cache_mb: int = 32
    hugepages_available: bool = True
    kleidi_ai_supported: bool = True
    features: List[str] = Field(default=["FEAT_I8MM", "FEAT_DotProd", "FEAT_SVE2", "FEAT_BF16"])

class OptimizationPlan(BaseModel):
    tasks: List[str]
    estimated_cost_usd: float
    estimated_duration_minutes: int
    recommended_quantization: str = "INT4"
    architecture_notes: str = ""

class BenchmarkReport(BaseModel):
    cloud: str
    quant_level: str
    concurrency: int
    ttft_p50_ms: float
    ttft_p95_ms: float
    ttft_p99_ms: float
    tps_p50: float
    memory_gb: float
    cpu_pct: float
    cost_per_1m: float
    numa_locality_pct: float = 98.4

class QualityReport(BaseModel):
    quant_level: str
    eval_dataset: str
    score_baseline: float
    score_optimized: float
    score_delta: float
    gate_passed: bool
    category_scores: Dict[str, float] = Field(default_factory=dict)

class SpeculativeConfig(BaseModel):
    target_model: str
    draft_model: str
    projected_tps_gain_pct: float
    acceptance_rate_pct: float
    speculative_enabled: bool = True

class DeploymentResult(BaseModel):
    helm_release_name: str
    namespace: str
    replica_count: int
    numa_pinned: bool
    hugepages_mounted: bool
    manifest_summary: Dict[str, Any]

class VerificationReport(BaseModel):
    sla_passed: bool
    smoke_test_tps: float
    smoke_test_p99_ms: float
    error_rate_pct: float = 0.0
    recommendation: str

class OptimizationCertificate(BaseModel):
    inferav22_version: str = "1.0.0"
    tagline: str = "Every Version. Faster. Smarter. Optimized."
    model: str
    timestamp: str
    certification_id: str
    arm_targets: List[str]
    overall_score: int
    optimal_config: Dict[str, Any]
    benchmarks: Dict[str, Any]
    quality_delta: Dict[str, Any]
    signature: str
    public_url: str

class InferaV22State(TypedDict):
    # Inputs
    run_id: str
    model_url: str
    sla_spec: Dict[str, Any]
    target_clouds: List[str]
    quality_floor: float

    # Pipeline tracking
    phase: Literal[
        "planning", "profiling", "optimizing", "benchmarking",
        "qualifying", "speculative", "deploying", "verifying",
        "certifying", "monitoring", "completed", "failed"
    ]
    current_quant_level: Literal["fp16", "int8", "int4"]
    quality_gate_passed: bool
    human_approval_required: bool
    human_approved: bool

    # Agent Outputs
    plan: Optional[Dict[str, Any]]
    topology: Dict[str, Any]
    benchmark_results: List[Dict[str, Any]]
    quality_reports: List[Dict[str, Any]]
    speculative_config: Optional[Dict[str, Any]]
    deployment: Optional[Dict[str, Any]]
    verification: Optional[Dict[str, Any]]
    certificate: Optional[Dict[str, Any]]

    # Observability & Log Tracking
    logs: List[Dict[str, Any]]

    # Error handling
    errors: List[str]
    error_count: int
    status: str
