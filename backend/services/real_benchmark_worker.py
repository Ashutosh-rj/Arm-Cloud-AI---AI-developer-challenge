"""
Real HTTP-based benchmark worker.
Issues actual concurrent requests to a running llama-server endpoint
and measures real P50/P95/P99 latency and TPS.

Requires: GRAVITON4_INFERENCE_URL, COBALT100_INFERENCE_URL, or AXION_INFERENCE_URL
env vars pointing to running llama-server instances.
"""
import asyncio
import logging
import os
import statistics
import time
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# Standard inference prompts for reproducible benchmarks
BENCHMARK_PROMPTS = [
    "Explain quantum entanglement in one sentence.",
    "What is the capital of France?",
    "Write a haiku about Arm Neoverse processors.",
    "What does SVE stand for in Arm Neoverse architecture?",
    "Explain NUMA memory locality in one paragraph.",
    "What is speculative decoding in LLM inference?",
    "Describe KleidiAI in two sentences.",
    "What is INT4 quantization?",
    "Explain the difference between TTFT and TPS metrics.",
    "What is the Arm Graviton4 processor?",
]

CLOUD_ENV_MAP = {
    "graviton4": "GRAVITON4_INFERENCE_URL",
    "cobalt100": "COBALT100_INFERENCE_URL",
    "axion": "AXION_INFERENCE_URL",
}

CLOUD_HOURLY_COST = {
    "graviton4": float(os.getenv("GRAVITON4_HOURLY_COST", "0.46")),
    "cobalt100": float(os.getenv("COBALT100_HOURLY_COST", "0.48")),
    "axion": float(os.getenv("AXION_HOURLY_COST", "0.49")),
    "x86_xeon": float(os.getenv("X86_XEON_HOURLY_COST", "0.85")),
}


async def _single_inference_request(
    client,
    base_url: str,
    prompt: str,
    max_tokens: int = 64,
) -> Dict[str, Any]:
    """Issue a single completion request to llama-server and measure latency."""
    import httpx
    start = time.perf_counter()
    try:
        response = await client.post(
            f"{base_url}/completion",
            json={
                "prompt": prompt,
                "n_predict": max_tokens,
                "stream": False,
                "temperature": 0.0,
                "seed": 42,
            },
            timeout=httpx.Timeout(30.0, connect=5.0),
        )
        elapsed_ms = (time.perf_counter() - start) * 1000
        response.raise_for_status()
        data = response.json()
        timings = data.get("timings", {})
        return {
            "success": True,
            "ttft_ms": timings.get("prompt_ms", elapsed_ms),
            "generation_ms": timings.get("predicted_ms", 0),
            "tps": timings.get("predicted_per_second", 0),
            "tokens_generated": timings.get("predicted_n", 0),
            "total_ms": elapsed_ms,
        }
    except Exception as exc:
        return {
            "success": False,
            "error": str(exc),
            "ttft_ms": 0,
            "tps": 0,
            "total_ms": (time.perf_counter() - start) * 1000,
        }


def _percentile(sorted_data: List[float], p: float) -> float:
    """Calculate the p-th percentile of a sorted list."""
    if not sorted_data:
        return 0.0
    idx = max(0, int(len(sorted_data) * p / 100) - 1)
    return sorted_data[min(idx, len(sorted_data) - 1)]


async def run_benchmark(
    cloud: str,
    quant_level: str,
    model_url: str = "",
    concurrency: int = 16,
    duration_seconds: int = 30,
    max_tokens: int = 64,
) -> Dict[str, Any]:
    """
    Run a real load benchmark against a llama-server inference endpoint.
    Returns actual measured metrics.

    If no inference URL is configured for the given cloud, raises RuntimeError
    (never silently falls back to formulas).
    """
    import httpx

    env_key = CLOUD_ENV_MAP.get(cloud.lower())
    if not env_key:
        raise ValueError(f"Unknown cloud '{cloud}'. Must be one of: {list(CLOUD_ENV_MAP.keys())}")

    inference_url = os.getenv(env_key, "").rstrip("/")
    if not inference_url:
        raise RuntimeError(
            f"No inference endpoint configured for cloud '{cloud}'. "
            f"Set the {env_key} environment variable to a running llama-server URL "
            f"(e.g., http://your-arm-instance:8080). "
            f"Deploy llama-server using deploy/Dockerfile.llamacpp-arm."
        )

    logger.info(
        f"Starting benchmark: cloud={cloud} quant={quant_level} "
        f"concurrency={concurrency} duration={duration_seconds}s url={inference_url}"
    )

    ttft_samples: List[float] = []
    tps_samples: List[float] = []
    errors = 0
    total_requests = 0

    async with httpx.AsyncClient() as client:
        # Warmup: 3 sequential requests
        logger.info("Running warmup requests...")
        for i in range(3):
            await _single_inference_request(client, inference_url, "warmup", max_tokens=8)

        # Real load test: concurrent waves over duration_seconds
        logger.info(f"Starting load test ({duration_seconds}s)...")
        end_time = time.time() + duration_seconds

        while time.time() < end_time:
            batch_prompts = [
                BENCHMARK_PROMPTS[i % len(BENCHMARK_PROMPTS)]
                for i in range(concurrency)
            ]
            batch_tasks = [
                _single_inference_request(client, inference_url, prompt, max_tokens)
                for prompt in batch_prompts
            ]
            results = await asyncio.gather(*batch_tasks, return_exceptions=True)

            for r in results:
                total_requests += 1
                if isinstance(r, dict) and r.get("success"):
                    ttft_samples.append(r["ttft_ms"])
                    if r["tps"] > 0:
                        tps_samples.append(r["tps"])
                else:
                    errors += 1

    if not ttft_samples:
        raise RuntimeError(
            f"All {total_requests} requests to {inference_url} failed. "
            f"Is llama-server running and the model loaded?"
        )

    ttft_sorted = sorted(ttft_samples)
    tps_sorted = sorted(tps_samples) if tps_samples else [0.0]

    hourly_cost = CLOUD_HOURLY_COST.get(cloud.lower(), 0.5)
    avg_tps = statistics.mean(tps_sorted) if tps_sorted else 0
    # Cost per 1M tokens: (hourly_cost / tokens_per_hour) * 1_000_000
    cost_per_1m = round(
        (hourly_cost / max(avg_tps * 3600, 1)) * 1_000_000, 4
    ) if avg_tps > 0 else None

    result = {
        "cloud": cloud,
        "quant_level": quant_level,
        "inference_url": inference_url,
        "model_url": model_url,
        "concurrency": concurrency,
        "duration_seconds": duration_seconds,
        "total_requests": total_requests,
        "successful_requests": len(ttft_samples),
        "error_count": errors,
        "error_rate_pct": round(errors / max(total_requests, 1) * 100, 2),
        "ttft_p50_ms": round(_percentile(ttft_sorted, 50), 1),
        "ttft_p95_ms": round(_percentile(ttft_sorted, 95), 1),
        "ttft_p99_ms": round(_percentile(ttft_sorted, 99), 1),
        "ttft_mean_ms": round(statistics.mean(ttft_samples), 1),
        "tps_p50": round(_percentile(tps_sorted, 50), 2),
        "tps_p95": round(_percentile(tps_sorted, 95), 2),
        "tps_mean": round(avg_tps, 2),
        "hourly_instance_cost_usd": hourly_cost,
        "cost_per_1m_tokens_usd": cost_per_1m,
        "measured": True,
    }

    logger.info(
        f"Benchmark complete: tps_p50={result['tps_p50']} "
        f"ttft_p99={result['ttft_p99_ms']}ms "
        f"errors={errors}/{total_requests}"
    )
    return result
