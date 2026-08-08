import logging
from typing import Dict, Any, Literal
from langgraph.graph import StateGraph, END
from core.state import InferaV22State

from services.arm_profiler import ArmProfiler
from services.llama_builder import LlamaArmBuilder
from services.real_quality_eval import RealQualityEvaluator
from services.real_benchmark_worker import run_benchmark, CLOUD_ENV_MAP
from services.certificate_service import CertificateService
from services.helm_generator import HelmGenerator
from services.speculative_engine import SpeculativeEngine

logger = logging.getLogger("inferav22-orchestrator")

# ------------------------------------------------------------------
# 10-Agent Swarm Node Implementations
# ------------------------------------------------------------------

async def planner_agent(state: InferaV22State) -> Dict[str, Any]:
    logger.info(f"[{state['run_id']}] 1/10 Planner Agent: Decomposing strategy for {state['model_url']}")
    plan = {
        "tasks": [
            "profile_hardware", "quantize_int4", "evaluate_quality_gate",
            "run_multi_cloud_benchmarks", "evaluate_speculative_pairing",
            "generate_helm_deployment", "verify_sla", "issue_signed_certificate"
        ],
        "estimated_cost_usd": 12.50,
        "estimated_duration_minutes": 15,
        "recommended_quantization": "Q4_K_M",
        "architecture_notes": "SVE 256-bit accelerated INT4 superblock packing"
    }
    return {
        "phase": "profiling",
        "plan": plan,
        "human_approval_required": False
    }

async def profiler_agent(state: InferaV22State) -> Dict[str, Any]:
    logger.info(f"[{state['run_id']}] 2/10 Profiler Agent: Inspecting Arm hardware topology...")
    topology = {}
    for cloud in state.get("target_clouds", ["graviton4"]):
        profile = ArmProfiler.profile_node(cloud=cloud)
        topology[cloud] = profile
    return {
        "phase": "optimizing",
        "topology": topology
    }

async def optimizer_agent(state: InferaV22State) -> Dict[str, Any]:
    current_level = state.get("current_quant_level", "fp16")
    next_level = "int8" if current_level == "fp16" else "int4"
    logger.info(f"[{state['run_id']}] 3/10 Optimizer Agent: Applying pass {next_level} with KleidiAI & Q4_K_M cache block size")
    
    builder = LlamaArmBuilder()
    builder.quantize_model("model-fp16.gguf", f"model-{next_level}.gguf", target_quant="Q4_K_M")
    
    return {
        "phase": "qualifying",
        "current_quant_level": next_level
    }

async def quality_agent(state: InferaV22State) -> Dict[str, Any]:
    quant_level = state.get("current_quant_level", "int4")
    logger.info(f"[{state['run_id']}] 4/10 Quality Agent: Running MMLU regression suite for {quant_level}")
    
    evaluator = RealQualityEvaluator(quality_floor=state.get("quality_floor", 0.98))
    
    import os
    primary_cloud = state.get("target_clouds", ["graviton4"])[0]
    env_key = CLOUD_ENV_MAP.get(primary_cloud.lower())
    inference_url = os.getenv(env_key, "").rstrip("/")

    if not inference_url:
        logger.warning(f"No inference URL available for {primary_cloud}. Cannot run real MMLU quality evaluation.")
        raise RuntimeError("No inference URL configured for real quality evaluation.")

    quality_report = evaluator.evaluate(
        inference_url=inference_url,
        model_name=state["model_url"], 
        quant_level=quant_level.upper()
    )

    reports = state.get("quality_reports", [])
    reports.append(quality_report)

    return {
        "quality_reports": reports,
        "quality_gate_passed": quality_report["gate_passed"],
        "phase": "benchmarking" if quality_report["gate_passed"] else "optimizing"
    }

async def benchmarker_agent(state: InferaV22State) -> Dict[str, Any]:
    logger.info(f"[{state['run_id']}] 5/10 Benchmark Agent: Executing multi-cloud concurrent load tests...")
    results = []
    for cloud in state.get("target_clouds", ["graviton4", "cobalt100", "axion"]):
        res = await run_benchmark(
            cloud=cloud,
            quant_level=state.get("current_quant_level", "INT4"),
            model_url=state.get("model_url", ""),
            concurrency=16,
            duration_seconds=30
        )
        results.append(res)

    return {
        "phase": "speculative",
        "benchmark_results": results
    }

async def speculative_agent(state: InferaV22State) -> Dict[str, Any]:
    logger.info(f"[{state['run_id']}] 6/10 Speculative Agent: Orchestrating draft model pairing...")
    spec_res = SpeculativeEngine.evaluate_speculative_pair(state["model_url"])
    return {
        "phase": "deploying",
        "speculative_config": spec_res
    }

async def deployer_agent(state: InferaV22State) -> Dict[str, Any]:
    logger.info(f"[{state['run_id']}] 7/10 Deployment Agent: Generating Helm Chart values for Arm64 K8s pool...")
    helm_manifest = HelmGenerator.generate_helm_manifests(
        state["model_url"], 
        state.get("current_quant_level", "INT4")
    )
    deploy_result = {
        "helm_release_name": f"inferav22-{state['run_id'][:8]}",
        "namespace": "production",
        "replica_count": 3,
        "numa_pinned": True,
        "hugepages_mounted": True,
        "manifest_summary": helm_manifest
    }
    return {
        "phase": "verifying",
        "deployment": deploy_result
    }

async def verifier_agent(state: InferaV22State) -> Dict[str, Any]:
    logger.info(f"[{state['run_id']}] 8/10 Verification Agent: Validating SLA requirements (P99 < 500ms)...")
    import os
    from services.real_benchmark_worker import CLOUD_ENV_MAP, run_benchmark
    
    primary_cloud = state.get("target_clouds", ["graviton4"])[0]
    env_key = CLOUD_ENV_MAP.get(primary_cloud.lower())
    inference_url = os.getenv(env_key, "").rstrip("/")
    
    if inference_url:
        try:
            res = await run_benchmark(
                cloud=primary_cloud,
                quant_level=state.get("current_quant_level", "INT4"),
                concurrency=4,
                duration_seconds=15
            )
            sla_spec = state.get("sla_spec", {})
            p99_limit = sla_spec.get("max_ttft_p99_ms", 500.0)
            tps_limit = sla_spec.get("min_tps_p50", 10.0)
            
            p99_actual = res.get("ttft_p99_ms", 9999)
            tps_actual = res.get("tps_p50", 0)
            
            sla_passed = (p99_actual <= p99_limit) and (tps_actual >= tps_limit)
            
            verification = {
                "sla_passed": sla_passed,
                "smoke_test_tps": tps_actual,
                "smoke_test_p99_ms": p99_actual,
                "error_rate_pct": res.get("error_rate_pct", 100.0),
                "measured": True,
                "recommendation": "SLA Verified" if sla_passed else "SLA Failed"
            }
        except Exception as e:
            verification = {
                "sla_passed": False,
                "measured": False,
                "error": str(e),
                "recommendation": "Benchmark failed"
            }
    else:
        verification = {
            "sla_passed": False,
            "measured": False,
            "error": f"No inference URL configured for {primary_cloud}",
            "recommendation": "Missing configuration"
        }
    return {
        "phase": "certifying",
        "verification": verification
    }

async def certifier_agent(state: InferaV22State) -> Dict[str, Any]:
    logger.info(f"[{state['run_id']}] 9/10 Certification Agent: Issuing signed Optimization Certificate...")
    
    if not state.get("verification", {}).get("sla_passed", False):
        return {
            "phase": "monitoring",
            "certificate": None,
            "error": "Cannot certify: SLA verification failed or was not run."
        }

    benchmarks_list = state.get("benchmark_results", [])
    if not benchmarks_list:
        raise ValueError("No benchmark results found to certify.")
    benchmarks = benchmarks_list[0]
    
    quality_reports = state.get("quality_reports", [])
    if not quality_reports:
        raise ValueError("No quality reports found to certify.")
    quality = quality_reports[-1]

    topology = state.get("topology", {})
    primary_cloud = state.get("target_clouds", ["graviton4"])[0]
    topo = topology.get(primary_cloud, {})

    threads = topo.get("recommended_threads_per_numa", topo.get("total_cores", 16))
    kleidiAI = topo.get("kleidi_ai_compatible", False) or topo.get("sve_width_bits", 0) >= 128
    hugepages = topo.get("hugepages", {}).get("enabled", False) or topo.get("hugepages_enabled", False)
    numa_strategy = "distribute" if topo.get("numa_nodes", 1) > 1 else "single"
    speculative_draft = state.get("speculative_config", {}).get("draft_model", "none")

    cert = CertificateService.generate_certificate(
        run_id=state["run_id"],
        model_url=state["model_url"],
        optimal_config={
            "quantization": state.get("current_quant_level", "INT4"),
            "threads": threads,
            "kleidiAI": kleidiAI,
            "hugepages": hugepages,
            "numa_strategy": numa_strategy,
            "speculative_draft": speculative_draft
        },
        benchmarks=benchmarks,
        quality_delta={"score_delta": quality.get("score_delta"), "gate": "PASS" if quality.get("gate_passed") else "FAIL"}
    )
    return {
        "phase": "monitoring",
        "certificate": cert
    }

async def monitor_agent(state: InferaV22State) -> Dict[str, Any]:
    logger.info(f"[{state['run_id']}] 10/10 Monitor Agent: Activating continuous metric drift monitoring.")
    return {
        "phase": "completed",
        "status": "COMPLETED"
    }

# ------------------------------------------------------------------
# Conditional Edge Routing
# ------------------------------------------------------------------

def route_after_quality(state: InferaV22State) -> Literal["benchmarker", "optimizer", "END"]:
    if state.get("quality_gate_passed", False):
        return "benchmarker"
    
    if state.get("current_quant_level") == "int8":
        return "optimizer"
    
    logger.warning(f"[{state['run_id']}] Quality floor violated at final level. Halting.")
    return END

# ------------------------------------------------------------------
# StateGraph Construction
# ------------------------------------------------------------------

def build_inferav22_graph():
    workflow = StateGraph(InferaV22State)

    workflow.add_node("planner", planner_agent)
    workflow.add_node("profiler", profiler_agent)
    workflow.add_node("optimizer", optimizer_agent)
    workflow.add_node("quality", quality_agent)
    workflow.add_node("benchmarker", benchmarker_agent)
    workflow.add_node("speculative", speculative_agent)
    workflow.add_node("deployer", deployer_agent)
    workflow.add_node("verifier", verifier_agent)
    workflow.add_node("certifier", certifier_agent)
    workflow.add_node("monitor", monitor_agent)

    workflow.set_entry_point("planner")

    workflow.add_edge("planner", "profiler")
    workflow.add_edge("profiler", "optimizer")
    workflow.add_edge("optimizer", "quality")

    workflow.add_conditional_edges(
        "quality",
        route_after_quality,
        {
            "benchmarker": "benchmarker",
            "optimizer": "optimizer",
            END: END
        }
    )

    workflow.add_edge("benchmarker", "speculative")
    workflow.add_edge("speculative", "deployer")
    workflow.add_edge("deployer", "verifier")
    workflow.add_edge("verifier", "certifier")
    workflow.add_edge("certifier", "monitor")
    workflow.add_edge("monitor", END)

    return workflow.compile()

app_graph = build_inferav22_graph()
