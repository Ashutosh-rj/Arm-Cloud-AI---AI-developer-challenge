#!/usr/bin/env bash
# ==============================================================================
# InferaV22 Arm Performance Execution Script
# Handles NUMA binding, HugePages reservation, thread affinity & KleidiAI.
# ==============================================================================

set -euo pipefail

MODEL_PATH="${1:-/models/model-q4km.gguf}"
DRAFT_MODEL_PATH="${2:-}"
PORT="${PORT:-8080}"

echo "⚡ [InferaV22] Initializing Arm Hardware Optimization Pass..."

# 1. HugePages Configuration (2MB pages)
HUGEPAGES_SYS="/sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages"
if [ -w "$HUGEPAGES_SYS" ]; then
    echo "  -> Allocating 4096 HugePages (8GB memory pool for weight mapping)..."
    echo 4096 > "$HUGEPAGES_SYS" || echo "  ⚠️ HugePages allocation skipped (insufficient permissions)"
fi

# 2. NUMA Topology & Thread Discovery
NUMA_NODES=$(numactl --hardware 2>/dev/null | grep "available:" | awk '{print $2}' || echo "1")
TOTAL_CORES=$(nproc)
THREADS_PER_NODE=$((TOTAL_CORES / NUMA_NODES))

echo "  -> Topology detected: ${TOTAL_CORES} total cores across ${NUMA_NODES} NUMA node(s)."
echo "  -> Optimal thread count per socket: ${THREADS_PER_NODE}"

# 3. Environment variables for KleidiAI
export GGML_USE_KLEIDIAI=1
export OMP_NUM_THREADS="${THREADS_PER_NODE}"

# 4. Construct Execution Command
NUMA_CMD=""
if [ "$NUMA_NODES" -gt 1 ]; then
    echo "  -> Multi-socket NUMA system detected. Binding to Node 0 for cache locality."
    NUMA_CMD="numactl --cpunodebind=0 --membind=0"
fi

LLAMA_SERVER="./llama-server"
if [ ! -f "$LLAMA_SERVER" ]; then
    LLAMA_SERVER="llama-server"
fi

EXTRA_FLAGS=""
if [ -n "$DRAFT_MODEL_PATH" ] && [ -f "$DRAFT_MODEL_PATH" ]; then
    echo "  -> Enabling Speculative Decoding with draft model: ${DRAFT_MODEL_PATH}"
    EXTRA_FLAGS="--model-draft ${DRAFT_MODEL_PATH}"
fi

echo "🚀 [InferaV22] Launching Inference Server on Arm64..."
echo "Command: ${NUMA_CMD} ${LLAMA_SERVER} --model ${MODEL_PATH} --threads ${THREADS_PER_NODE} --ctx-size 4096 --batch-size 512 --port ${PORT} ${EXTRA_FLAGS}"

exec ${NUMA_CMD} ${LLAMA_SERVER} \
    --model "${MODEL_PATH}" \
    --threads "${THREADS_PER_NODE}" \
    --threads-batch "${THREADS_PER_NODE}" \
    --ctx-size 4096 \
    --batch-size 512 \
    --parallel 16 \
    --port "${PORT}" \
    --host "0.0.0.0" \
    ${EXTRA_FLAGS}
